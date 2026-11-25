"""Cloudflare Turnstile: проверка токена капчи на сервере (siteverify).

Без TURNSTILE_SECRET_KEY проверка выключена (локальная разработка и тесты).
Тестовые ключи Cloudflare: secret 1x0000000000000000000000000000000AA всегда «успех»,
2x0000000000000000000000000000000AA — всегда «провал».
"""
import logging
from typing import Optional

import httpx
from fastapi import Header, HTTPException, Request

from app.config import settings

logger = logging.getLogger("app.security")
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def client_ip(request: Request) -> str:
    """IP клиента. За Cloudflare request.client.host — адрес узла Cloudflare, реальный —
    в CF-Connecting-IP; за Nginx/ingress-nginx — в X-Real-IP. Заголовку доверяем, только
    если его задаёт наш прокси (CLIENT_IP_HEADER), иначе клиент подставит любой адрес."""
    if settings.client_ip_header:
        value = request.headers.get(settings.client_ip_header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_turnstile(token: Optional[str], ip: str) -> bool:
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                SITEVERIFY_URL,
                data={"secret": settings.turnstile_secret_key, "response": token, "remoteip": ip},
            )
        result = response.json()
    except (httpx.HTTPError, ValueError):
        logger.exception("Turnstile siteverify недоступен")
        return False  # fail-closed: без проверки капчи регистрация и вход не проходят
    if not result.get("success"):
        logger.warning("Капча не пройдена", extra={"event": "captcha_failed", "codes": result.get("error-codes")})
    return bool(result.get("success"))


async def require_captcha(request: Request, x_turnstile_token: Optional[str] = Header(None)) -> None:
    """Зависимость для /auth/register и /auth/token: токен виджета — в заголовке X-Turnstile-Token."""
    if not await verify_turnstile(x_turnstile_token, client_ip(request)):
        raise HTTPException(status_code=400, detail="captcha_failed")
