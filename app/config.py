"""Настройки приложения из переменных окружения (значения по умолчанию подходят для локального запуска)."""
import os
from urllib.parse import quote_plus


class Settings:
    def __init__(self) -> None:
        self.database_url = self._build_database_url()
        self.sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        self.celery_broker_url = os.getenv(
            "CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"
        )

        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "admin")
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

        # Таймаут проверок зависимостей в /ready (секунды)
        self.ready_check_timeout = float(os.getenv("READY_CHECK_TIMEOUT", "2"))
        # Celery: очередь, по длине которой KEDA масштабирует воркеров
        self.celery_queue = os.getenv("CELERY_QUEUE", "celery")

        # S3 (SeaweedFS): фото блюд и прочие файлы
        self.s3_endpoint = os.getenv("S3_ENDPOINT", "http://localhost:8333")
        self.s3_bucket = os.getenv("S3_BUCKET", "fastapi-files")
        self.s3_region = os.getenv("S3_REGION", "us-east-1")
        self.s3_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.s3_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        # Создавать бакет при первом обращении (docker compose); в Kubernetes бакет создаёт CRD Bucket
        self.s3_auto_create_bucket = os.getenv("S3_AUTO_CREATE_BUCKET", "false").lower() == "true"
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
        self.max_image_mb = int(os.getenv("MAX_IMAGE_MB", "5"))

        # Логи: json (для Loki) или text (удобнее читать локально)
        self.log_format = os.getenv("LOG_FORMAT", "json")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Кэш меню (GET /dishes) — 1 минута
        self.dishes_cache_ttl = int(os.getenv("DISHES_CACHE_TTL", "60"))
        # Rate limit на создание заказа — 20 в минуту с одного IP
        self.orders_rate_limit = int(os.getenv("ORDERS_RATE_LIMIT", "20"))
        self.orders_rate_window = int(os.getenv("ORDERS_RATE_WINDOW", "60"))
        # Имитация готовки и доставки (секунды)
        self.cooking_delay_seconds = int(os.getenv("COOKING_DELAY_SECONDS", "30"))
        self.delivery_delay_seconds = int(os.getenv("DELIVERY_DELAY_SECONDS", "30"))

    @staticmethod
    def _build_database_url() -> str:
        """DATABASE_URL целиком или (в Kubernetes) из частей: хост и имя БД из ConfigMap, логин и пароль из Secret."""
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        host = os.getenv("DATABASE_HOST")
        if not host:
            return "sqlite+aiosqlite:///./app.db"
        user = quote_plus(os.getenv("DATABASE_USER", "postgres"))
        password = quote_plus(os.getenv("DATABASE_PASSWORD", ""))
        port = os.getenv("DATABASE_PORT", "5432")
        name = os.getenv("DATABASE_NAME", "restaurant")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для Celery-воркера (он не использует asyncio)."""
        return self.database_url.replace("+aiosqlite", "").replace("+asyncpg", "")


settings = Settings()
