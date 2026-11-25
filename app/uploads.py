"""Проверка загружаемых файлов: размер и настоящий тип изображения по сигнатуре (magic bytes).

Заголовку Content-Type и расширению имени файла доверять нельзя — их задаёт клиент.
SVG не принимается: это XML, внутри которого может быть <script> (XSS при открытии по прямой ссылке).
"""
from typing import Optional

from fastapi import HTTPException, UploadFile

EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def detect_image_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def read_limited(file: UploadFile, max_mb: int) -> bytes:
    """Читает файл, не больше max_mb мегабайт (иначе 413)."""
    limit = max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File is too large (max {max_mb} MB)")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    return data


def require_image(data: bytes) -> str:
    content_type = detect_image_type(data)
    if content_type is None:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG or WebP images are allowed")
    return content_type
