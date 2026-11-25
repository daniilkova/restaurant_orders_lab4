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
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me-at-least-32-bytes-long")
        self.bcrypt_rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))

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

        # Аутентификация (JWT). SECRET_KEY в Kubernetes приходит из Vault (VaultStaticSecret)
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        self.jwt_issuer = os.getenv("JWT_ISSUER", "restaurant-api")
        # Ограничение попыток входа: N неудачных попыток за окно — по логину и по IP отдельно
        self.login_max_attempts = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
        self.login_window_seconds = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
        # Первый администратор (создаётся при старте, если в БД нет ни одного admin)
        self.bootstrap_admin_username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "")
        self.bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        # Безопасность HTTP
        self.allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
        # CORS: фронтенд Vite (npm run dev) работает на другом origin — http://localhost:5173
        self.cors_origins = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ]
        self.hsts_enabled = os.getenv("HSTS_ENABLED", "false").lower() == "true"
        # /metrics: если задан токен, Prometheus обязан прислать Authorization: Bearer <токен>
        self.metrics_token = os.getenv("METRICS_TOKEN", "")

        # --- ЛР8: сессии в httpOnly cookies ---
        self.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # true за HTTPS
        self.cookie_samesite = os.getenv("COOKIE_SAMESITE", "strict")
        self.cookie_domain = os.getenv("COOKIE_DOMAIN") or None
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        self.twofa_issuer = os.getenv("TWOFA_ISSUER", "Ресторан Пряность")
        self.twofa_temp_token_minutes = int(os.getenv("TWOFA_TEMP_TOKEN_MINUTES", "5"))
        self.username_change_cooldown_days = int(os.getenv("USERNAME_CHANGE_COOLDOWN_DAYS", "182"))
        self.email_token_ttl_hours = int(os.getenv("EMAIL_TOKEN_TTL_HOURS", "24"))
        self.max_avatar_mb = int(os.getenv("MAX_AVATAR_MB", "2"))
        # Почта: без SMTP_HOST письма пишутся в лог и в каталог MAIL_OUTBOX_DIR (разработка)
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", "no-reply@restaurant.local")
        self.mail_outbox_dir = os.getenv("MAIL_OUTBOX_DIR", "")
        self.email_send_sync = os.getenv("EMAIL_SEND_SYNC", "false").lower() == "true"
        # Self.xyz: возрастная верификация
        self.age_verification_on_register = os.getenv("AGE_VERIFICATION_ON_REGISTER", "false").lower() == "true"
        self.self_network = os.getenv("SELF_NETWORK", "testnet")  # testnet + mock-паспорт для учёбы
        self.self_api_base = os.getenv("SELF_API_BASE", "")
        self.self_api_key = os.getenv("SELF_API_KEY", "")
        self.self_age_flow_id = os.getenv("SELF_AGE_FLOW_ID", "")
        self.self_webhook_secret = os.getenv("SELF_WEBHOOK_SECRET", "")
        # Учебная заглушка Self (только для локальной разработки и тестов, в production — false)
        self.age_verification_mock = os.getenv("AGE_VERIFICATION_MOCK", "false").lower() == "true"

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
