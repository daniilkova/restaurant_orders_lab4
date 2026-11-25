"""Файлы в S3 (SeaweedFS): загрузка и скачивание.

Ключ объекта генерирует сервер (uploads/<uuid><расширение>): имя от клиента не используется
как путь, поэтому подменить чужой объект или выйти за префикс через «../» нельзя.
"""
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.auth import get_current_user, require_staff
from app.config import settings
from app.metrics import FILES_UPLOADED
from app.s3_client import S3Storage, get_storage
from app.uploads import read_limited

router = APIRouter(prefix="/files", tags=["files"])

SAFE_EXT = re.compile(r"^\.[a-z0-9]{1,8}$")
OBJECT_NAME = re.compile(r"^(uploads|dishes)/[A-Za-z0-9._/-]+$")


def make_object_name(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if not SAFE_EXT.match(ext):
        ext = ""
    return f"uploads/{uuid.uuid4().hex}{ext}"


@router.post(
    "/upload", status_code=201, summary="Загрузить файл в S3 (персонал)", dependencies=[Depends(require_staff)]
)
async def upload(file: UploadFile = File(...), storage: S3Storage = Depends(get_storage)):
    data = await read_limited(file, settings.max_upload_mb)
    object_name = make_object_name(file.filename)
    content_type = file.content_type or "application/octet-stream"
    await storage.upload(object_name, data, content_type)
    FILES_UPLOADED.labels(kind="file").inc()
    return {"object_name": object_name, "size": len(data), "content_type": content_type}


@router.get(
    "/download/{object_name:path}",
    summary="Скачать файл из S3",
    dependencies=[Depends(get_current_user)],
)
async def download(object_name: str, storage: S3Storage = Depends(get_storage)):
    if ".." in object_name or not OBJECT_NAME.match(object_name):
        raise HTTPException(status_code=400, detail="Invalid object name")
    try:
        data, content_type = await storage.download(object_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    filename = object_name.rsplit("/", 1)[-1]
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
