"""Экземпляр Celery. Запуск воркера: celery -A app.celery_app worker --loglevel=info"""
from celery import Celery
from celery.signals import setup_logging

from app.config import settings

celery_app = Celery(
    "restaurant",
    broker=settings.celery_broker_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    task_time_limit=60,
    broker_connection_retry_on_startup=True,
    task_default_queue=settings.celery_queue,
    # Воркер берёт из RabbitMQ по одной задаче и подтверждает её после выполнения.
    # Тогда невыполненные задачи остаются в очереди (KEDA видит реальную длину),
    # а при гибели пода задача возвращается в очередь и достаётся другому воркеру.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@setup_logging.connect
def _configure_worker_logging(**kwargs) -> None:
    """Воркер пишет логи тем же JSON-форматом, что и API (Celery не трогает root-логгер)."""
    from app.logging_config import setup_logging as configure

    configure(settings.log_format, settings.log_level)
