"""Метрики Prometheus: HTTP-метрики (prometheus-fastapi-instrumentator) + бизнес-метрики ресторана."""
from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

ORDERS_CREATED = Counter("restaurant_orders_created_total", "Создано заказов")
ORDER_TOTAL = Histogram(
    "restaurant_order_total_rub",
    "Сумма заказа, руб.",
    buckets=(250, 500, 1000, 1500, 2000, 3000, 5000, 10000),
)
ORDER_STATUS_CHANGES = Counter(
    "restaurant_order_status_changes_total",
    "Смены статуса заказов через API",
    ["status", "source"],
)
FILES_UPLOADED = Counter("restaurant_files_uploaded_total", "Загружено файлов в S3", ["kind"])


def setup_metrics(app: FastAPI) -> None:
    Instrumentator(
        # Коды ответа не группируем в «5xx»: иначе правило status=~"5.." из алерта ничего не найдёт
        should_group_status_codes=False,
        should_ignore_untemplated=True,          # /orders/123 -> handler="/orders/{order_id}"
        excluded_handlers=["/metrics", "/health", "/ready"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

AUTH_EVENTS = Counter(
    "restaurant_auth_events_total",
    "События аутентификации: login, login_failed, login_blocked, refresh, refresh_reuse, register",
    ["event"],
)
