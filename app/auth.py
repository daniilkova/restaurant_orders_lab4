"""Аутентификация: bcrypt для паролей, JWT (PyJWT) для access/refresh-токенов, роли.

Отличия от шаблона методички:
* python-jose и passlib не поддерживаются (у python-jose есть CVE, passlib ломается с bcrypt>=4.1),
  поэтому используются PyJWT и bcrypt напрямую;
* роль и активность пользователя берутся из БД при каждом запросе, а не из токена:
  разжалованный или заблокированный пользователь теряет доступ сразу, а не через 15 минут
  (token_version в токене сверяется с БД);
* refresh-токены хранятся в БД (jti) с ротацией и обнаружением повторного использования.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# Хэш для сравнения, когда пользователя нет: время ответа одинаковое (нет утечки логинов по таймингу)
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
    except ValueError:  # пароль длиннее 72 байт или битый хэш
        return False


def _encode(payload: dict, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires, "iss": settings.jwt_issuer}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User) -> str:
    return _encode(
        {"sub": str(user.id), "username": user.username, "role": user.role,
         "ver": user.token_version, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user: User, family_id: Optional[str] = None) -> tuple[str, str, str, datetime]:
    """Возвращает (токен, jti, family_id, expires_at)."""
    jti = uuid.uuid4().hex
    family_id = family_id or uuid.uuid4().hex
    expires = timedelta(days=settings.refresh_token_expire_days)
    token = _encode({"sub": str(user.id), "jti": jti, "fam": family_id, "type": "refresh"}, expires)
    return token, jti, family_id, datetime.now(timezone.utc) + expires


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],  # явный список: защита от alg=none и подмены алгоритма
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR from None
    if payload.get("type") != expected_type:
        raise CREDENTIALS_ERROR
    return payload


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise CREDENTIALS_ERROR
    payload = decode_token(token, "access")
    try:
        user = await db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        raise CREDENTIALS_ERROR from None
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise CREDENTIALS_ERROR
    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Пользователь, если токен передан; для публичных эндпоинтов с расширенным ответом."""
    if not token:
        return None
    return await get_current_user(token, db)


def require_role(*roles: Role):
    allowed = {r.value for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return dependency


require_admin = require_role(Role.ADMIN)
