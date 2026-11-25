"""Фоновые задачи Celery: имитация приготовления и доставки заказа.

Цепочка: принят --(COOKING_DELAY)--> доставляется --(DELIVERY_DELAY)--> завершён.
Воркер синхронный, поэтому использует обычную (не async) сессию SQLAlchemy.
"""
import logging
import time
from functools import lru_cache
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models import Order, OrderStatus

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


def apply_status_change(session: Session, order_id: int, new_status: str) -> bool:
    """Сменить статус заказа. False — если заказ удалён или уже завершён (менять нечего)."""
    order = session.get(Order, order_id)
    if order is None:
        logger.info("Заказ %s не найден (удалён?), задача пропущена", order_id)
        return False
    if order.status == OrderStatus.COMPLETED.value:
        logger.info("Заказ %s уже завершён, задача пропущена", order_id)
        return False
    order.status = new_status
    session.commit()
    logger.info("Заказ %s -> %s", order_id, new_status)
    return True


@celery_app.task(
    bind=True,
    name="orders.advance_status",
    max_retries=3,
    default_retry_delay=5,
)
def advance_order_status(
    self,
    order_id: int,
    new_status: str,
    next_status: Optional[str] = None,
    next_delay: int = 0,
) -> dict:
    """Меняет статус и (если указано) планирует следующий шаг через next_delay секунд."""
    try:
        with get_session_factory()() as session:
            changed = apply_status_change(session, order_id, new_status)
    except SQLAlchemyError as exc:  # временные проблемы с БД — повторяем
        logger.warning("Ошибка БД в задаче, повтор (%s)", exc)
        raise self.retry(exc=exc)

    if changed and next_status:
        advance_order_status.apply_async(args=[order_id, next_status], countdown=next_delay)
    return {"order_id": order_id, "status": new_status, "changed": changed}


def schedule_order_progress(order_id: int) -> Optional[str]:
    """Поставить в очередь цепочку статусов. Вызывать ПОСЛЕ commit() заказа.

    Если брокер недоступен, заказ всё равно создан — просто логируем ошибку.
    """
    try:
        result = advance_order_status.apply_async(
            args=[
                order_id,
                OrderStatus.DELIVERING.value,
                OrderStatus.COMPLETED.value,
                settings.delivery_delay_seconds,
            ],
            countdown=settings.cooking_delay_seconds,
        )
        return result.id
    except Exception:
        logger.exception("Не удалось поставить задачу для заказа %s в очередь", order_id)
        return None


@celery_app.task(name="kitchen.prepare_report")
def prepare_kitchen_report(order_id: int, seconds: float = 2.0) -> dict:
    """«Тяжёлая» задача для проверки автомасштабирования: имитирует формирование
    отчёта кухни (чек, накладная) и занимает воркер на seconds секунд."""
    time.sleep(seconds)
    logger.info("Отчёт кухни по заказу %s готов", order_id)
    return {"order_id": order_id, "seconds": seconds}


@celery_app.task(
    name="accounts.send_verification_email",
    autoretry_for=(OSError,),       # SMTP недоступен — повтор с паузой
    retry_backoff=True,
    max_retries=5,
)
def send_verification_email(email: str, link: str) -> None:
    from app.mailer import build_verification_email, send_email

    send_email(build_verification_email(email, link))


def queue_verification_email(email: str, link: str) -> None:
    """Поставить письмо в очередь; если брокер недоступен — отправить сразу (регистрация не должна падать)."""
    if settings.email_send_sync:  # локальная разработка без воркера
        send_verification_email.run(email, link)
        return
    try:
        send_verification_email.delay(email, link)
    except Exception:
        logger.warning("Брокер недоступен, письмо отправляется синхронно", exc_info=True)
        send_verification_email.run(email, link)
