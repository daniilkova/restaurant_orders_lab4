"""Возрастная верификация через Self.xyz (zero-knowledge proof: «старше 18» без даты рождения).

Сохраняется только результат — is_age_verified и время проверки.
"""
import hashlib
import hmac
import html
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_purpose_token, decode_token, get_optional_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.routers.auth import send_verification
from app.schemas.user import StrictModel
from app.self_verifier import agent_auth

router = APIRouter(prefix="/auth", tags=["age-verification"])
logger = logging.getLogger("app.security")


class RegistrationToken(StrictModel):
    registration_token: str


async def user_for_age_flow(
    x_registration_token: Optional[str] = Header(None),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Вошедший пользователь или (при регистрации, до входа) владелец registration_token."""
    if user is not None:
        return user
    if x_registration_token:
        payload = decode_token(x_registration_token, "registration")
        found = await db.get(User, int(payload["sub"]))
        if found is not None and found.is_active:
            return found
    raise HTTPException(status_code=401, detail="Could not validate credentials")


async def mark_age_verified(db: AsyncSession, user: User) -> None:
    user.is_age_verified = True
    user.age_verified_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Возраст подтверждён", extra={"event": "age_verified", "user_id": user.id})


def frontend_return(outcome: str, registration: bool) -> str:
    query = {"age": outcome}
    if registration:
        query["registration"] = "true"
    return f"{settings.frontend_url}/verify-age?{urlencode(query)}"


@router.post("/age-session", summary="Начать возрастную верификацию: адрес страницы Self")
async def create_age_session(request: Request, user: User = Depends(user_for_age_flow)):
    if user.is_age_verified:
        raise HTTPException(status_code=400, detail="Age is already verified")
    registration = not user.is_email_verified
    if settings.self_api_base and settings.self_api_key:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.self_api_base.rstrip('/')}/sessions",
                headers={"Authorization": f"Bearer {settings.self_api_key}"},
                json={
                    "flowId": settings.self_age_flow_id,
                    "externalUuid": str(user.id),
                    "successUrl": frontend_return("success", registration),
                    "failureUrl": frontend_return("failure", registration),
                },
            )
        if response.status_code >= 400:
            logger.error("Self API вернул %s", response.status_code)
            raise HTTPException(status_code=502, detail="Age verification provider error")
        return {"verificationUrl": response.json()["verificationUrl"]}
    if settings.age_verification_mock:
        session = create_purpose_token(user, "age-mock", 10)
        return {"verificationUrl": f"{str(request.base_url).rstrip('/')}/auth/age-mock?session={session}"}
    raise HTTPException(status_code=503, detail="Age verification is not configured")


@router.post("/verify-age", summary="Proof от агента Self (SDK AgentAuth)")
async def verify_age(agent=Depends(agent_auth), user: User = Depends(user_for_age_flow),
                     db: AsyncSession = Depends(get_db)):
    """Запрос подписан агентом Self; SDK проверил подпись и регистрацию агента в реестре
    (иначе 401). Раскрытые данные — в agent.credentials, возраст — older_than (0, 18 или 21)."""
    credentials = getattr(agent, "credentials", None)
    if not credentials or getattr(credentials, "older_than", 0) < 18:
        raise HTTPException(status_code=403, detail="Age requirement not met")
    await mark_age_verified(db, user)
    return {"verified": True, "agent_id": agent.agent_id}


@router.post("/self-webhook", include_in_schema=False)
async def self_webhook(request: Request, x_self_signature: str = Header(...), db: AsyncSession = Depends(get_db)):
    """Результат hosted-сессии Self. Подпись HMAC-SHA256 тела секретом SELF_WEBHOOK_SECRET."""
    body = await request.body()
    expected = hmac.new(settings.self_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not settings.self_webhook_secret or not hmac.compare_digest(expected, x_self_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    data = json.loads(body)
    user = await db.get(User, int(data.get("externalUuid", 0)))
    if user and data.get("isMinimumAgeValid"):
        await mark_age_verified(db, user)
    return {"ok": True}


@router.post("/complete-registration", summary="После возрастной верификации — отправить письмо")
async def complete_registration(body: RegistrationToken, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.registration_token, "registration")
    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_age_verified:
        raise HTTPException(status_code=403, detail="age_verification_required")
    if not user.is_email_verified:
        await send_verification(db, user)
    return {"email_sent": True, "email": user.email}


# ---------- учебная заглушка Self (AGE_VERIFICATION_MOCK=true, только разработка) ----------
MOCK_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Self — проверка возраста (заглушка)</title>
<style>body{{font-family:system-ui,sans-serif;background:#0b0b0f;color:#f2f2f2;display:grid;place-items:center;min-height:100vh;margin:0}}
.box{{max-width:420px;padding:32px;border-radius:16px;background:#17171f;text-align:center}}
.note{{font-size:13px;color:#f5b041;margin-bottom:16px}}a{{display:block;margin:10px 0;padding:12px;border-radius:10px;text-decoration:none;font-weight:600}}
.ok{{background:#3ddc97;color:#0b0b0f}}.no{{background:#2a2a35;color:#f2f2f2}}</style></head><body><div class="box">
<p class="note">Учебная заглушка (AGE_VERIFICATION_MOCK=true). В production здесь страница Self с QR-кодом.</p>
<h1>Подтверждение возраста 18+</h1><p>Пользователь: <b>{user}</b>. Дата рождения не передаётся — только факт «старше 18».</p>
<a class="ok" href="{ok}">Подтвердить (mock-паспорт, 18+)</a><a class="no" href="{no}">Отказаться</a></div></body></html>"""


@router.get("/age-mock", include_in_schema=False)
async def age_mock(session: str, outcome: Optional[str] = Query(None, pattern="^(success|failure)$"),
                   db: AsyncSession = Depends(get_db)):
    if not settings.age_verification_mock:
        raise HTTPException(status_code=404)
    payload = decode_token(session, "age-mock")
    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=404)
    registration = not user.is_email_verified
    if outcome is None:
        base = f"/auth/age-mock?session={session}&outcome="
        return HTMLResponse(MOCK_PAGE.format(user=html.escape(user.username), ok=base + "success", no=base + "failure"))
    if outcome == "success":
        await mark_age_verified(db, user)
    return RedirectResponse(frontend_return(outcome, registration), status_code=303)
