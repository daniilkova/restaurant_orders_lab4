"""Регистрация, вход, обновление и отзыв токенов."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.metrics import AUTH_EVENTS
from app.models import RefreshToken, Role, User
from app.redis_client import get_redis
from app.schemas.user import RefreshRequest, TokenPair, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.security")

INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",  # одинаковый ответ: нельзя узнать, существует ли логин
    headers={"WWW-Authenticate": "Bearer"},
)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def issue_tokens(db: AsyncSession, user: User, request: Request, family_id: str | None = None) -> TokenPair:
    refresh, jti, family, expires_at = create_refresh_token(user, family_id)
    db.add(
        RefreshToken(
            jti=jti,
            family_id=family,
            user_id=user.id,
            expires_at=expires_at,
            user_agent=(request.headers.get("user-agent") or "")[:255],
            ip=client_ip(request),
        )
    )
    await db.flush()
    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ---------- ограничение подбора пароля (OWASP API2: Broken Authentication) ----------
def _login_keys(username: str, ip: str) -> list[str]:
    return [f"login_fail:user:{username.lower()}", f"login_fail:ip:{ip}"]


async def check_login_allowed(redis: Redis, username: str, ip: str) -> None:
    try:
        counts = [int(v or 0) for v in await redis.mget(_login_keys(username, ip))]
    except RedisError:
        return  # fail-open, как и у остальных лимитов
    if max(counts) >= settings.login_max_attempts:
        AUTH_EVENTS.labels(event="login_blocked").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts, try again later",
            headers={"Retry-After": str(settings.login_window_seconds)},
        )


async def register_login_failure(redis: Redis, username: str, ip: str) -> None:
    try:
        for key in _login_keys(username, ip):
            if await redis.incr(key) == 1:
                await redis.expire(key, settings.login_window_seconds)
    except RedisError:
        pass


@router.post("/register", response_model=UserOut, status_code=201, summary="Регистрация клиента")
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    conditions = [User.username == payload.username]
    if payload.email:
        conditions.append(User.email == payload.email)
    if await db.scalar(select(User.id).where(or_(*conditions))):
        raise HTTPException(status_code=409, detail="User with this username or email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=Role.USER.value,  # роль задаёт сервер, не клиент
    )
    db.add(user)
    await db.commit()
    AUTH_EVENTS.labels(event="register").inc()
    return user


@router.post("/token", response_model=TokenPair, summary="Вход (OAuth2 password flow)")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip = client_ip(request)
    await check_login_allowed(redis, form.username, ip)
    user = await db.scalar(select(User).where(User.username == form.username))
    password_ok = verify_password(form.password, user.hashed_password if user else None)
    if not user or not password_ok or not user.is_active:
        await register_login_failure(redis, form.username, ip)
        AUTH_EVENTS.labels(event="login_failed").inc()
        logger.warning("Неудачный вход", extra={"event": "login_failed", "username": form.username, "client": ip})
        raise INVALID_LOGIN
    try:
        await redis.delete(f"login_fail:user:{form.username.lower()}")
    except RedisError:
        pass
    tokens = await issue_tokens(db, user, request)
    await db.commit()
    AUTH_EVENTS.labels(event="login").inc()
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="Новая пара токенов (ротация refresh)")
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    now = datetime.now(timezone.utc)
    if stored is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored.revoked_at is not None:
        if stored.replaced_by:
            # Токен уже был обменян — его предъявили повторно. Это признак кражи:
            # отзываем всю цепочку, и злоумышленник, и пользователь должны войти заново.
            await revoke_family(db, stored.family_id)
            await db.commit()
            AUTH_EVENTS.labels(event="refresh_reuse").inc()
            logger.warning(
                "Повторное использование refresh-токена, семья отозвана",
                extra={"event": "refresh_reuse", "user_id": stored.user_id, "client": client_ip(request)},
            )
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    expires_at = stored.expires_at if stored.expires_at.tzinfo else stored.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    tokens = await issue_tokens(db, user, request, family_id=stored.family_id)
    new_jti = decode_token(tokens.refresh_token, "refresh")["jti"]
    stored.revoked_at = now
    stored.replaced_by = new_jti
    await db.commit()
    AUTH_EVENTS.labels(event="refresh").inc()
    return tokens


async def revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


@router.post("/logout", status_code=204, summary="Выход: отзыв refresh-токена")
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except HTTPException:
        return None  # выход идемпотентен
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if stored is not None:
        await revoke_family(db, stored.family_id)
        await db.commit()
    return None


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def me(user: User = Depends(get_current_user)):
    return user
