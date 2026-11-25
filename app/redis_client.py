"""Redis: кэширование (cache-aside с TTL) и rate limiting (INCR + EXPIRE).

Если Redis недоступен, приложение продолжает работать: кэш пропускается,
а ограничение частоты временно не применяется (fail-open).
"""
import json
import logging
from typing import Any, Awaitable, Callable

from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

DISHES_CACHE_KEY = "dishes:list"

# Клиент создаётся лениво: реальное соединение открывается при первой команде.
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> Redis:
    """Зависимость FastAPI. В тестах подменяется через app.dependency_overrides."""
    return redis_client


async def get_cached(
    redis: Redis,
    key: str,
    fetcher: Callable[[], Awaitable[Any]],
    ttl: int,
) -> Any:
    """Cache-aside: вернуть значение из кэша, а при промахе взять из fetcher и положить на ttl секунд."""
    try:
        cached = await redis.get(key)
        if cached is not None:
            return json.loads(cached)
    except RedisError:
        logger.warning("Redis недоступен при чтении кэша, идём в БД", exc_info=True)
        return await fetcher()

    data = await fetcher()
    try:
        await redis.setex(key, ttl, json.dumps(data, default=str))
    except RedisError:
        logger.warning("Redis недоступен при записи кэша", exc_info=True)
    return data


async def invalidate_cache(redis: Redis, *keys: str) -> None:
    """Инвалидация: удалить ключи кэша после изменения данных."""
    try:
        await redis.delete(*keys)
    except RedisError:
        logger.warning("Не удалось инвалидировать кэш %s", keys, exc_info=True)


def rate_limit(max_requests: int, window_seconds: int):
    """Фабрика зависимости-ограничителя: не более max_requests за window_seconds с одного IP.

    У каждого эндпоинта свой лимит: достаточно указать
    dependencies=[Depends(rate_limit(N, T))] в декораторе маршрута.
    """

    async def dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{request.method}:{request.url.path}:{client_ip}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_seconds)
            ttl = await redis.ttl(key)
        except RedisError:
            logger.warning("Redis недоступен, rate limit пропущен", exc_info=True)
            return

        if count > max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Limit: {max_requests} per {window_seconds} seconds.",
                headers={"Retry-After": str(max(ttl, 1))},
            )

    return dependency
