from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.order import utcnow


class Role(str, Enum):
    ADMIN = "admin"           # администратор: всё, включая пользователей и роли
    MODERATOR = "moderator"   # менеджер ресторана: меню, фото, статусы заказов
    CLIENT = "client"         # клиент: меню и только свои заказы


STAFF_ROLES = (Role.ADMIN, Role.MODERATOR)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.CLIENT.value, server_default=Role.CLIENT.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    # Меняется при смене пароля/роли и блокировке: все ранее выданные access-токены
    # с другой версией перестают приниматься (мгновенный отзыв без чёрного списка).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # --- ЛР8: двухфакторная аутентификация (TOTP, RFC 6238) ---
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # --- профиль ---
    display_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    avatar_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    username_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # --- подтверждение email: хранится только SHA-256 токена ---
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    email_verification_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # --- возрастная верификация (Self.xyz): храним только результат, не дату рождения ---
    is_age_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    age_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    age_verification_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    def __str__(self) -> str:
        return self.username


class RefreshToken(Base):
    """Выданный refresh-токен. В БД хранится только jti (идентификатор), не сам токен.

    family_id объединяет цепочку ротаций одного входа: при повторном использовании уже
    заменённого токена (признак кражи) отзывается вся семья — reuse detection.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
