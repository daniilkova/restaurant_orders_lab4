"""Админ-панель (sqladmin): /admin. Вход по логину и паролю из ADMIN_USERNAME / ADMIN_PASSWORD."""
from typing import Any

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.config import settings
from app.database import engine
from app.models import Dish, Order, OrderItem, OrderStatus
from app.redis_client import DISHES_CACHE_KEY, invalidate_cache, redis_client


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        if (
            form.get("username") == settings.admin_username
            and form.get("password") == settings.admin_password
        ):
            request.session.update({"token": "staff"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("token") == "staff"


class DishAdmin(ModelView, model=Dish):
    name = "Блюдо"
    name_plural = "Блюда"
    icon = "fa-solid fa-utensils"
    column_list = [Dish.id, Dish.name, Dish.price, Dish.is_available]
    column_searchable_list = [Dish.name]
    column_sortable_list = [Dish.id, Dish.name, Dish.price]
    form_columns = [Dish.name, Dish.description, Dish.price, Dish.is_available]

    # Правки меню в админке тоже должны сбрасывать кэш GET /dishes
    async def after_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        await invalidate_cache(redis_client, DISHES_CACHE_KEY)

    async def after_model_delete(self, model: Any, request: Request) -> None:
        await invalidate_cache(redis_client, DISHES_CACHE_KEY)


class OrderAdmin(ModelView, model=Order):
    name = "Заказ"
    name_plural = "Заказы"
    icon = "fa-solid fa-receipt"
    column_list = [Order.id, Order.status, Order.created_at]
    column_sortable_list = [Order.id, Order.status, Order.created_at]
    column_default_sort = [(Order.id, True)]
    can_create = False
    form_columns = [Order.status]  # в админке вручную меняется только статус
    form_choices = {"status": [(s.value, s.value) for s in OrderStatus]}


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "Позиция заказа"
    name_plural = "Позиции заказов"
    icon = "fa-solid fa-list"
    column_list = [
        OrderItem.id,
        OrderItem.order_id,
        OrderItem.dish_name,
        OrderItem.quantity,
        OrderItem.price,
    ]
    can_create = False
    can_edit = False


def setup_admin(app: FastAPI) -> Admin:
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminAuth(secret_key=settings.secret_key),
        title="Ресторан — админка",
    )
    admin.add_view(DishAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    return admin
