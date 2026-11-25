"""Пробы Kubernetes.

/health — liveness: процесс жив и обрабатывает запросы. Зависимости НЕ проверяются,
иначе падение PostgreSQL привело бы к перезапуску всех подов API (каскадный рестарт).
/ready  — readiness: под готов принимать трафик, только если доступны БД и Redis.
Пока /ready отвечает 503, Service не направляет на под запросы, но под не перезапускается.
"""
import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal
from app.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


async def check_database() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))


async def check_redis() -> None:
    await get_redis().ping()


CHECKS = {"database": check_database, "redis": check_redis}


@router.get("/health", summary="Liveness-проба")
async def health():
    return {"status": "ok"}


@router.get("/ready", summary="Readiness-проба (БД и Redis)")
async def ready():
    results = {}
    for name, check in CHECKS.items():
        try:
            await asyncio.wait_for(check(), timeout=settings.ready_check_timeout)
            results[name] = "ok"
        except Exception as exc:  # любая ошибка зависимости = под не готов
            logger.warning("readiness: %s недоступен: %r", name, exc)
            results[name] = "unavailable"
    if all(value == "ok" for value in results.values()):
        return {"status": "ready", "checks": results}
    return JSONResponse(status_code=503, content={"status": "not ready", "checks": results})
