"""Регистрация, вход (в том числе второй шаг 2FA), обновление и отзыв сессий, подтверждение email."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app import tasks
from app.auth import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_access_token,
    create_purpose_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_token_payload,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.metrics import AUTH_EVENTS
from app.models import RefreshToken, Role, User
from app.redis_client import get_redis
from app.schemas.user import (
    EmailRequest,
    LoginResult,
    PasswordChange,
    RefreshRequest,
    RegisterResult,
    SessionOut,
    TwoFactorVerify,
    UserMe,
    UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.security")

INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",  # одинаковый ответ: нельзя узнать, существует ли логин
    headers={"WWW-Authenticate": "Bearer"},
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- сессии ----------
async def start_session(
    db: AsyncSession, user: User, request: Request, response: Response, family_id: Optional[str] = None
) -> str:
    """Создаёт (или продолжает при ротации) сессию: запись refresh-токена в БД и cookies. Возвращает access."""
    access, _ = await _start_session(db, user, request, response, family_id)
    return access


async def _start_session(db, user, request, response, family_id=None) -> tuple[str, str]:
    refresh, jti, family, expires_at = create_refresh_token(user, family_id)
    db.add(RefreshToken(
        jti=jti, family_id=family, user_id=user.id, expires_at=expires_at,
        user_agent=(request.headers.get("user-agent") or "")[:255], ip=client_ip(request),
    ))
    await db.flush()
    access = create_access_token(user, family)
    set_auth_cookies(response, access, refresh)
    return access, jti


def unauthorized(detail: str) -> JSONResponse:
    """401 с очисткой cookies (у исключения HTTPException cookies ответа не сохраняются)."""
    response = JSONResponse({"detail": detail}, status_code=401)
    clear_auth_cookies(response)
    return response


async def revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all(db: AsyncSession, user_id: int, except_family: Optional[str] = None) -> None:
    query = update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    if except_family:
        query = query.where(RefreshToken.family_id != except_family)
    await db.execute(query.values(revoked_at=utcnow()))


# ---------- ограничение подбора (пароль и коды 2FA) ----------
def _fail_keys(kind: str, subject: str, ip: str) -> list[str]:
    return [f"{kind}_fail:user:{subject.lower()}", f"{kind}_fail:ip:{ip}"]


async def check_attempts(redis: Redis, kind: str, subject: str, ip: str) -> None:
    try:
        counts = [int(v or 0) for v in await redis.mget(_fail_keys(kind, subject, ip))]
    except RedisError:
        return
    if max(counts) >= settings.login_max_attempts:
        AUTH_EVENTS.labels(event="login_blocked").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts, try again later",
            headers={"Retry-After": str(settings.login_window_seconds)},
        )


async def register_failure(redis: Redis, kind: str, subject: str, ip: str) -> None:
    try:
        for key in _fail_keys(kind, subject, ip):
            if await redis.incr(key) == 1:
                await redis.expire(key, settings.login_window_seconds)
    except RedisError:
        pass


async def reset_failures(redis: Redis, kind: str, subject: str) -> None:
    try:
        await redis.delete(f"{kind}_fail:user:{subject.lower()}")
    except RedisError:
        pass


# ---------- подтверждение email ----------
async def send_verification(db: AsyncSession, user: User) -> None:
    token = secrets.token_urlsafe(32)
    user.email_verification_token = hash_token(token)  # в БД — только хэш: утечка БД не даёт ссылок
    user.email_verification_expires_at = utcnow() + timedelta(hours=settings.email_token_ttl_hours)
    await db.commit()
    link = f"{settings.frontend_url}/verify-email?token={token}"
    await run_in_threadpool(tasks.queue_verification_email, user.email, link)


# ---------- регистрация и вход ----------
@router.post("/register", response_model=RegisterResult, status_code=201, summary="Регистрация клиента")
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    exists = await db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if exists:
        field = "email" if exists.email == payload.email else "username"
        raise HTTPException(status_code=409, detail={"field": field, "message": f"{field} already registered"})
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=Role.CLIENT.value,
        age_verification_required=settings.age_verification_on_register,
    )
    db.add(user)
    await db.commit()
    AUTH_EVENTS.labels(event="register").inc()
    result = RegisterResult(
        id=user.id, username=user.username, email=user.email,
        requires_age_verification=user.age_verification_required,
    )
    if user.age_verification_required:
        # Письмо уйдёт после возрастной верификации (POST /auth/complete-registration)
        result.registration_token = create_purpose_token(user, "registration", 30)
    else:
        await send_verification(db, user)
    return result


@router.post("/token", response_model=LoginResult, response_model_by_alias=True, summary="Вход (OAuth2 password flow)")
async def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip = client_ip(request)
    await check_attempts(redis, "login", form.username, ip)
    user = await db.scalar(select(User).where(User.username == form.username))
    password_ok = verify_password(form.password, user.hashed_password if user else None)
    if not user or not password_ok or not user.is_active:
        await register_failure(redis, "login", form.username, ip)
        AUTH_EVENTS.labels(event="login_failed").inc()
        logger.warning("Неудачный вход", extra={"event": "login_failed", "username": form.username, "client": ip})
        raise INVALID_LOGIN
    await reset_failures(redis, "login", form.username)
    # Пароль верный — только теперь сообщаем, чего не хватает (иначе это утечка о существовании логина)
    if user.age_verification_required and not user.is_age_verified:
        raise HTTPException(status_code=403, detail="age_verification_required")
    if not user.is_email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")
    if user.totp_enabled:
        # Пароль верный, но сессии ещё нет: temp_token годится только для /auth/2fa/verify и 5 минут
        return LoginResult(
            twofa_required=True,
            temp_token=create_purpose_token(user, "2fa", settings.twofa_temp_token_minutes),
            token_type="2fa",
        )
    access = await start_session(db, user, request, response)
    await db.commit()
    AUTH_EVENTS.labels(event="login").inc()
    return LoginResult(access_token=access)


@router.post(
    "/2fa/verify", response_model=LoginResult, response_model_by_alias=True, summary="Вход: второй шаг (код TOTP)"
)
async def verify_2fa(
    body: TwoFactorVerify,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    payload = decode_token(body.temp_token, "2fa")
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or not user.totp_enabled or payload.get("ver") != user.token_version:
        raise HTTPException(status_code=401, detail="Invalid temporary token")
    ip = client_ip(request)
    await check_attempts(redis, "totp", user.username, ip)
    # valid_window=1: принимаем соседний 30-секундный интервал (расхождение часов, задержка ввода)
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        await register_failure(redis, "totp", user.username, ip)
        AUTH_EVENTS.labels(event="login_failed").inc()
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    await reset_failures(redis, "totp", user.username)
    access = await start_session(db, user, request, response)
    await db.commit()
    AUTH_EVENTS.labels(event="login").inc()
    return LoginResult(access_token=access)


@router.post("/refresh", status_code=204, summary="Обновить сессию (ротация refresh-токена)")
async def refresh(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token, "refresh")
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if stored is None:
        return unauthorized("Invalid refresh token")
    if stored.revoked_at is not None:
        if stored.replaced_by:
            # Уже обменянный токен предъявлен повторно — признак кражи: отзываем всю цепочку
            await revoke_family(db, stored.family_id)
            await db.commit()
            AUTH_EVENTS.labels(event="refresh_reuse").inc()
            logger.warning("Повторное использование refresh-токена, сессия отозвана",
                           extra={"event": "refresh_reuse", "user_id": stored.user_id, "client": client_ip(request)})
        return unauthorized("Refresh token revoked")
    if aware(stored.expires_at) <= utcnow():
        return unauthorized("Refresh token expired")
    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        return unauthorized("User is inactive")
    stored.revoked_at = utcnow()
    _, new_jti = await _start_session(db, user, request, response, family_id=stored.family_id)
    stored.replaced_by = new_jti
    await db.commit()
    AUTH_EVENTS.labels(event="refresh").inc()
    response.status_code = 204
    return response


@router.post("/logout", status_code=204, summary="Выход: отзыв сессии и очистка cookies")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    family = None
    candidates = ((request.cookies.get("access_token"), "access"), (request.cookies.get(REFRESH_COOKIE), "refresh"))
    for cookie, kind in candidates:
        if cookie and not family:
            try:
                family = decode_token(cookie, kind).get("fam")
            except HTTPException:
                pass
    if family:
        await revoke_family(db, family)
        await db.commit()
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserMe, summary="Текущий пользователь")
async def me(user: User = Depends(get_current_user)):
    return user


# ---------- email ----------
@router.get("/verify-email", summary="Подтверждение email по ссылке из письма")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email_verification_token == hash_token(token)))
    if user is None or not user.email_verification_expires_at or aware(user.email_verification_expires_at) < utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    user.is_email_verified = True
    user.email_verification_token = None  # одноразовая ссылка
    user.email_verification_expires_at = None
    await db.commit()
    return {"verified": True, "username": user.username}


@router.post("/resend-verification", status_code=202, summary="Отправить письмо ещё раз")
async def resend_verification(body: EmailRequest, request: Request,
                              db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    try:
        key = f"resend:{body.email.lower()}"
        if await redis.incr(key) == 1:
            await redis.expire(key, 3600)
        if int(await redis.get(key) or 0) > 3:
            raise HTTPException(status_code=429, detail="Too many requests")
    except RedisError:
        pass
    user = await db.scalar(select(User).where(User.email == body.email))
    if user and not user.is_email_verified and not (user.age_verification_required and not user.is_age_verified):
        await send_verification(db, user)
    # Ответ одинаковый для любых email: нельзя проверить, зарегистрирован ли адрес
    return {"detail": "If the address is registered and not verified, a new email has been sent"}


# ---------- пароль и сессии ----------
@router.post("/change-password", status_code=204, summary="Смена пароля (нужен текущий)")
async def change_password(body: PasswordChange, request: Request, response: Response,
                          user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail={"field": "current_password", "message": "Wrong current password"})
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail={"field": "new_password", "message": "New password equals current"})
    user.hashed_password = hash_password(body.new_password)
    user.token_version += 1           # все access-токены перестают действовать
    await revoke_all(db, user.id)     # и все refresh-токены: украденная сессия больше не продлится
    await start_session(db, user, request, response)  # текущее устройство остаётся в системе
    await db.commit()
    AUTH_EVENTS.labels(event="password_changed").inc()
    response.status_code = 204
    return response


@router.get("/sessions", response_model=list[SessionOut], summary="Активные сессии (устройства)")
async def sessions(payload: dict = Depends(get_token_payload), user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id).order_by(RefreshToken.id)
    )).scalars().all()
    families: dict[str, list[RefreshToken]] = {}
    for row in rows:
        families.setdefault(row.family_id, []).append(row)
    result = []
    for family, tokens in families.items():
        last = tokens[-1]
        if last.revoked_at is not None or aware(last.expires_at) <= utcnow():
            continue
        result.append(SessionOut(
            id=family, created_at=aware(tokens[0].created_at), last_used_at=aware(last.created_at),
            user_agent=last.user_agent, ip=last.ip, current=family == payload.get("fam"),
        ))
    return sorted(result, key=lambda s: (not s.current, -s.last_used_at.timestamp()))


@router.delete("/sessions/{session_id}", status_code=204, summary="Завершить сессию")
async def revoke_session(session_id: str, response: Response, payload: dict = Depends(get_token_payload),
                         user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    owned = await db.scalar(select(RefreshToken.id).where(
        RefreshToken.family_id == session_id, RefreshToken.user_id == user.id).limit(1))
    if not owned:
        raise HTTPException(status_code=404, detail="Session not found")  # чужая сессия = не существует
    await revoke_family(db, session_id)
    if session_id == payload.get("fam"):
        user.token_version += 1  # текущая сессия: access-токен тоже перестаёт работать
        clear_auth_cookies(response)
    await db.commit()
    response.status_code = 204
    return response


@router.post("/sessions/revoke-others", status_code=204, summary="Завершить все другие сессии")
async def revoke_other_sessions(payload: dict = Depends(get_token_payload), user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    await revoke_all(db, user.id, except_family=payload.get("fam"))
    await db.commit()
    return None
