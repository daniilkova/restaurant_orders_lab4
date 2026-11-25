from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.order import utcnow


class Role(str, Enum):
    ADMIN = "admin"   # персонал ресторана: меню, все заказы, статусы, пользователи
    USER = "user"     # клиент: меню и только свои заказы


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.USER.value, server_default=Role.USER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    # Меняется при смене пароля/роли и блокировке: все ранее выданные access-токены
    # с другой версией перестают приниматься (мгновенный отзыв без чёрного списка).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

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
