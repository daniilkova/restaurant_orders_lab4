"""Клиент S3 (SeaweedFS, MinIO, AWS — любой S3-совместимый сервер).

boto3 синхронный, поэтому каждый вызов уводится в пул потоков (run_in_threadpool),
чтобы не блокировать event loop FastAPI.
"""
import logging
from functools import lru_cache
from typing import Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from starlette.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(
        self,
        endpoint: Optional[str],
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        auto_create_bucket: bool = False,
    ) -> None:
        self.bucket = bucket
        self.auto_create_bucket = auto_create_bucket
        self._bucket_checked = False
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            region_name=region,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},  # SeaweedFS/MinIO: http://host:8333/<bucket>/<key>
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=3,
                read_timeout=10,
            ),
        )

    def _ensure_bucket(self) -> None:
        if not self.auto_create_bucket or self._bucket_checked:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            logger.info("Бакет %s не найден, создаём", self.bucket)
            self.client.create_bucket(Bucket=self.bucket)
        self._bucket_checked = True

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def _get(self, key: str) -> Tuple[bytes, str]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NoSuchBucket"}:
                raise FileNotFoundError(key) from exc
            raise
        return response["Body"].read(), response.get("ContentType") or "application/octet-stream"

    def _delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await run_in_threadpool(self._put, key, data, content_type)

    async def download(self, key: str) -> Tuple[bytes, str]:
        return await run_in_threadpool(self._get, key)

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self._delete, key)

    def ping(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


@lru_cache(maxsize=1)
def get_storage() -> S3Storage:
    """Зависимость FastAPI; в тестах подменяется через app.dependency_overrides."""
    return S3Storage(
        endpoint=settings.s3_endpoint,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        auto_create_bucket=settings.s3_auto_create_bucket,
    )
