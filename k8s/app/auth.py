"""Аутентификация: bcrypt, JWT (PyJWT), сессии в httpOnly cookies, роли.

ЛР8: токены живут в httpOnly cookies (JavaScript их не видит — XSS не может их украсть):
  access_token  — path=/,             15 минут
  refresh_token — path=/auth/refresh,  7 дней (браузер отправляет его только на обновление)
Заголовок Authorization: Bearer по-прежнему принимается (Swagger, curl, мобильные клиенты).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import STAFF_ROLES, Role, User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth/refresh"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, hashed: Optional[str]) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), (hashed or _DUMMY_HASH).encode()) and hashed is not None
    except ValueError:
        return False


def _encode(payload: dict, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires, "iss": settings.jwt_issuer}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, family_id: Optional[str] = None) -> str:
    return _encode(
        {"sub": str(user.id), "username": user.username, "role": user.role,
         "ver": user.token_version, "type": "access", "fam": family_id},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user: User, family_id: Optional[str] = None) -> tuple[str, str, str, datetime]:
    jti = uuid.uuid4().hex
    family_id = family_id or uuid.uuid4().hex
    expires = timedelta(days=settings.refresh_token_expire_days)
    token = _encode({"sub": str(user.id), "jti": jti, "fam": family_id, "type": "refresh"}, expires)
    return token, jti, family_id, datetime.now(timezone.utc) + expires


def create_purpose_token(user: User, purpose: str, minutes: int) -> str:
    """Короткоживущий токен одного назначения: '2fa' (второй шаг входа), 'registration'."""
    return _encode({"sub": str(user.id), "type": purpose, "ver": user.token_version}, timedelta(minutes=minutes))


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR from None
    if payload.get("type") != expected_type:
        raise CREDENTIALS_ERROR
    return payload


# ---------- cookies ----------
def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": settings.cookie_samesite,
              "domain": settings.cookie_domain}
    response.set_cookie(ACCESS_COOKIE, access, max_age=settings.access_token_expire_minutes * 60, path="/", **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=settings.refresh_token_expire_days * 86400,
                        path=REFRESH_COOKIE_PATH, **common)


def clear_auth_cookies(response: Response) -> None:
    # Те же атрибуты, что при установке: иначе браузер может не сопоставить и не удалить cookie
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": settings.cookie_samesite,
              "domain": settings.cookie_domain}
    response.delete_cookie(ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **common)


def access_token_from(request: Request, bearer: Optional[str]) -> Optional[str]:
    return bearer or request.cookies.get(ACCESS_COOKIE)


async def _user_from_payload(payload: dict, db: AsyncSession) -> User:
    try:
        user = await db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        raise CREDENTIALS_ERROR from None
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise CREDENTIALS_ERROR
    return user


async def get_token_payload(request: Request, bearer: Optional[str] = Depends(oauth2_scheme)) -> dict:
    token = access_token_from(request, bearer)
    if not token:
        raise CREDENTIALS_ERROR
    return decode_token(token, "access")


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _user_from_payload(payload, db)


async def get_optional_user(
    request: Request,
    bearer: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Пользователь, если вошёл; для публичных эндпоинтов, ответ которых зависит от пользователя."""
    token = access_token_from(request, bearer)
    if not token:
        return None
    try:
        return await _user_from_payload(decode_token(token, "access"), db)
    except HTTPException:
        return None


def require_role(*roles: Role):
    allowed = {r.value for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return dependency


require_admin = require_role(Role.ADMIN)
require_staff = require_role(*STAFF_ROLES)   # модератор или администратор: контент и статусы заказов


def is_staff(user: Optional[User]) -> bool:
    return user is not None and user.role in {r.value for r in STAFF_ROLES}
