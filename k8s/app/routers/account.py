"""Аккаунт: профиль (имя, логин, аватар) и двухфакторная аутентификация."""
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
import segno
from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, verify_password
from app.config import settings
from app.database import get_db
from app.metrics import AUTH_EVENTS, FILES_UPLOADED
from app.models import User
from app.s3_client import S3Storage, get_storage
from app.schemas.user import ProfileUpdate, TotpCode, TotpDisable, UserMe, UsernameChange
from app.uploads import EXTENSIONS, read_limited, require_image

router = APIRouter(tags=["account"])


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- профиль ----------
@router.patch("/users/me", response_model=UserMe, summary="Отображаемое имя")
async def update_profile(body: ProfileUpdate, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    user.display_name = (body.display_name or "").strip() or None
    await db.commit()
    return user


@router.patch("/users/me/username", response_model=UserMe, summary="Сменить логин (раз в 6 месяцев)")
async def change_username(body: UsernameChange, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    if user.username_changed_at:
        next_allowed = aware(user.username_changed_at) + timedelta(days=settings.username_change_cooldown_days)
        if now < next_allowed:
            raise HTTPException(status_code=429, detail={
                "message": "Username can be changed once in 6 months", "next_change_at": next_allowed.isoformat()})
    if body.username == user.username:
        raise HTTPException(status_code=400, detail="This is your current username")
    if await db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail={"field": "username", "message": "username already taken"})
    user.username = body.username
    user.username_changed_at = now
    await db.commit()
    return user


@router.put("/users/me/avatar", response_model=UserMe, summary="Загрузить аватар (JPEG/PNG/WebP, до 2 МБ)")
async def upload_avatar(file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db), storage: S3Storage = Depends(get_storage)):
    data = await read_limited(file, settings.max_avatar_mb)
    content_type = require_image(data)  # по сигнатуре: SVG (XML со скриптами) и «картинки-скрипты» отклоняются
    key = f"avatars/{user.id}/{uuid.uuid4().hex}{EXTENSIONS[content_type]}"
    await storage.upload(key, data, content_type)
    old, user.avatar_key = user.avatar_key, key
    await db.commit()
    if old:
        try:
            await storage.delete(old)
        except Exception:
            pass
    FILES_UPLOADED.labels(kind="avatar").inc()
    return user


@router.delete("/users/me/avatar", response_model=UserMe, summary="Удалить аватар")
async def delete_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
                        storage: S3Storage = Depends(get_storage)):
    if user.avatar_key:
        key, user.avatar_key = user.avatar_key, None
        await db.commit()
        try:
            await storage.delete(key)
        except Exception:
            pass
    return user


@router.get("/users/{user_id}/avatar", summary="Аватар пользователя", response_class=Response)
async def get_avatar(user_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db),
                     storage: S3Storage = Depends(get_storage)):
    user = await db.get(User, user_id)
    if user is None or not user.avatar_key:
        raise HTTPException(status_code=404, detail="Avatar not found")
    try:
        data, content_type = await storage.download(user.avatar_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Avatar not found") from None
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


# ---------- 2FA (TOTP) ----------
@router.post("/auth/2fa/enable", summary="Начать подключение 2FA: секрет и QR-код")
async def enable_2fa(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    # Секрет сохраняется сразу, но 2FA включится только после подтверждения кода (/confirm):
    # так пользователь не потеряет доступ, если не успел добавить аккаунт в приложение
    user.totp_secret = pyotp.random_base32()
    await db.commit()
    uri = pyotp.TOTP(user.totp_secret).provisioning_uri(name=user.email or user.username,
                                                         issuer_name=settings.twofa_issuer)
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2)
    return {"secret": user.totp_secret, "otpauth_uri": uri, "qr_svg": qr}


@router.post("/auth/2fa/confirm", response_model=UserMe, summary="Подтвердить 2FA кодом из приложения")
async def confirm_2fa(body: TotpCode, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /auth/2fa/enable first")
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail={"field": "code", "message": "Invalid 2FA code"})
    user.totp_enabled = True
    await db.commit()
    AUTH_EVENTS.labels(event="2fa_enabled").inc()
    return user


@router.post("/auth/2fa/disable", response_model=UserMe, summary="Отключить 2FA (пароль и код)")
async def disable_2fa(body: TotpDisable, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=400, detail={"field": "password", "message": "Wrong password"})
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail={"field": "code", "message": "Invalid 2FA code"})
    user.totp_enabled = False
    user.totp_secret = None
    await db.commit()
    return user
