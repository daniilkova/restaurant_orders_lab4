import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.admin import setup_admin
from app.bootstrap import bootstrap
from app.config import settings
from app.database import engine
from app.logging_config import setup_logging
from app.metrics import setup_metrics
from app.redis_client import redis_client
from app.routers import account, age, auth, dashboard, dishes, files, health, orders, users
from app.security import setup_security

setup_logging(settings.log_format, settings.log_level)
access_logger = logging.getLogger("app.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: схема БД создаётся миграциями Alembic (alembic upgrade head)
    app.state.redis = redis_client
    await bootstrap()
    yield
    # Shutdown: закрываем соединения
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title="Restaurant Orders API",
    description="Ресторан и заказы (вариант 9): FastAPI + PostgreSQL + Redis + RabbitMQ/Celery + S3",
    version="8.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Одна JSON-строка на запрос: по ним в Loki считаются ошибки и медленные запросы."""
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if request.url.path not in ("/health", "/ready", "/metrics"):
            access_logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "client": request.client.host if request.client else None,
                },
            )


setup_metrics(app)
setup_security(app)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(age.router)
app.include_router(account.router)
app.include_router(users.router)
app.include_router(dishes.router)
app.include_router(orders.router)
app.include_router(files.router)
app.include_router(dashboard.router)
setup_admin(app)


@app.get("/", tags=["root"])
async def root():
    return {
        "docs": "/docs",
        "admin": "/admin",
        "live_orders": "/dashboard/",
        "health": "/health",
        "ready": "/ready",
        "metrics": "/metrics",
    }
