"""Отправка писем. Вызывается из Celery-задачи, чтобы регистрация не ждала SMTP-сервер.

Без SMTP_HOST (разработка) письмо пишется в лог и, если задан MAIL_OUTBOX_DIR, в файл .eml.
"""
import logging
import os
import smtplib
import uuid
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def build_verification_email(to: str, link: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Подтвердите email — ресторан «Пряность»"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(
        "Здравствуйте!\n\nЧтобы активировать аккаунт, перейдите по ссылке (действует "
        f"{settings.email_token_ttl_hours} ч):\n{link}\n\nЕсли вы не регистрировались — просто проигнорируйте письмо.\n"
    )
    return msg


def send_email(msg: EmailMessage) -> None:
    if settings.smtp_host:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("Письмо отправлено", extra={"to": msg["To"], "subject": msg["Subject"]})
        return
    if settings.mail_outbox_dir:
        os.makedirs(settings.mail_outbox_dir, exist_ok=True)
        path = os.path.join(settings.mail_outbox_dir, f"{uuid.uuid4().hex}.eml")
        with open(path, "wb") as f:
            f.write(bytes(msg))
    logger.info("SMTP не настроен, письмо не отправлено (dev): %s", msg.get_content().strip().splitlines()[3],
                extra={"to": msg["To"]})
