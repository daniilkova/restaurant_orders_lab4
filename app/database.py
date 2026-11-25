"""Асинхронное подключение к БД (SQLite для разработки, PostgreSQL для production)."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.sql_echo)

# expire_on_commit=False — чтобы после commit() объекты можно было читать без нового запроса
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость: одна сессия на запрос. commit() вызывается явно в эндпоинтах."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
