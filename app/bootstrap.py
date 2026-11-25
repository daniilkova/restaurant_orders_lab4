"""Создание первого администратора (иначе некому назначать роли)."""
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth import hash_password
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Role, User

logger = logging.getLogger(__name__)


async def ensure_admin(username: str, password: str, session_factory=AsyncSessionLocal) -> bool:
    """Создаёт администратора, если в БД нет ни одного. True — если создан."""
    async with session_factory() as db:
        if await db.scalar(select(User.id).where(User.role == Role.ADMIN.value).limit(1)):
            return False
        if await db.scalar(select(User.id).where(User.username == username)):
            logger.warning("Пользователь %s уже есть, но не администратор — bootstrap пропущен", username)
            return False
        db.add(User(username=username, hashed_password=hash_password(password), role=Role.ADMIN.value))
        await db.commit()
        logger.info("Создан первый администратор %s", username)
        return True


async def bootstrap() -> None:
    if not (settings.bootstrap_admin_username and settings.bootstrap_admin_password):
        return
    try:
        await ensure_admin(settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    except SQLAlchemyError:
        logger.exception("Bootstrap администратора не выполнен (БД недоступна или нет миграций)")
