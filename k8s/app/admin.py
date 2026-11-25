"""Админ-панель (sqladmin): /admin. Вход — пользователь API с ролью admin (пароль проверяется bcrypt)."""
from typing import Any

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from app.auth import verify_password
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models import Dish, Order, OrderItem, OrderStatus, Role, User
from app.redis_client import DISHES_CACHE_KEY, invalidate_cache, redis_client


class AdminAuth(AuthenticationBackend):
    """Вход в /admin — учётная запись пользователя с ролью admin (пароль проверяется bcrypt).
    В сессии (подписанная cookie) хранятся id и token_version: блокировка или разжалование
    пользователя сразу закрывает ему админку."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.username == str(form.get("username", ""))))
            ok = verify_password(str(form.get("password", "")), user.hashed_password if user else None)
            if not ok or not user.is_active or user.role != Role.ADMIN.value:
                return False
            request.session.update({"uid": user.id, "ver": user.token_version})
            return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        uid = request.session.get("uid")
        if not uid:
            return False
        async with AsyncSessionLocal() as db:
            user = await db.get(User, uid)
        return bool(
            user and user.is_active and user.role == Role.ADMIN.value
            and user.token_version == request.session.get("ver")
        )


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


class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.username, User.email, User.role, User.is_active, User.created_at]
    column_searchable_list = [User.username, User.email]
    column_details_exclude_list = [User.hashed_password]
    can_create = False                       # регистрация — через API (хэширование пароля)
    form_columns = [User.role, User.is_active]
    form_choices = {"role": [(r.value, r.value) for r in Role]}

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        model.token_version += 1             # смена роли/блокировка отзывает выданные токены


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
    admin.add_view(UserAdmin)
    return admin
