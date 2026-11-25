"""Заказы: CRUD + смена статуса. POST /orders ограничен 20 запросами в минуту с одного IP.

Права (защита от BOLA — OWASP API1): клиент видит и меняет только свои заказы, причём менять
состав и удалять можно лишь заказ в статусе «принят». Чужой заказ для клиента не существует (404):
ответ не подтверждает, что заказ с таким ID есть. Администратор видит все заказы и меняет статусы.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app import tasks
from app.auth import get_current_user, is_staff, require_staff
from app.config import settings
from app.database import get_db
from app.metrics import ORDER_STATUS_CHANGES, ORDER_TOTAL, ORDERS_CREATED
from app.models import Dish, Order, OrderItem, OrderStatus, User
from app.redis_client import rate_limit
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


async def fetch_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    """Заказ вместе с позициями — одним дополнительным запросом (selectin), без N+1."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_order_or_404(db: AsyncSession, order_id: int, user: Optional[User] = None) -> Order:
    order = await fetch_order(db, order_id)
    if order is None or (user is not None and not can_access(user, order)):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def is_admin(user: User) -> bool:
    """Персонал (модератор или администратор) видит все заказы и меняет статусы."""
    return is_staff(user)


def can_access(user: User, order: Order) -> bool:
    return is_admin(user) or order.user_id == user.id


def ensure_editable(user: User, order: Order) -> None:
    if not is_admin(user) and order.status != OrderStatus.ACCEPTED.value:
        raise HTTPException(status_code=409, detail="Order is already being prepared and cannot be changed")


async def build_items(db: AsyncSession, items_in, user: Optional[User] = None) -> List[OrderItem]:
    """Собрать позиции заказа: одним запросом загружаем все блюда, цену копируем из меню."""
    quantities: Dict[int, int] = {}
    for item in items_in:  # одинаковые блюда объединяем
        quantities[item.dish_id] = quantities.get(item.dish_id, 0) + item.quantity

    result = await db.execute(select(Dish).where(Dish.id.in_(list(quantities))))
    dishes = {dish.id: dish for dish in result.scalars()}

    items: List[OrderItem] = []
    for dish_id, quantity in quantities.items():
        dish = dishes.get(dish_id)
        if dish is None:
            raise HTTPException(status_code=404, detail=f"Dish {dish_id} not found")
        if not dish.is_available:
            raise HTTPException(status_code=400, detail=f"Dish {dish_id} is not available")
        if (dish.min_age or 0) > 0 and user is not None and not (user.is_age_verified or is_staff(user)):
            raise HTTPException(status_code=403, detail="age_verification_required")
        items.append(
            OrderItem(dish_id=dish.id, dish_name=dish.name, quantity=quantity, price=dish.price)
        )
    return items


@router.get("/", response_model=List[OrderOut], summary="Список заказов")
async def get_orders(
    status: Optional[OrderStatus] = Query(None, description="Фильтр по статусу"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Order).options(selectinload(Order.items)).order_by(Order.id)
    if not is_admin(user):
        query = query.where(Order.user_id == user.id)
    if status is not None:
        query = query.where(Order.status == status.value)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderOut, summary="Заказ по ID")
async def get_order(
    order_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_order_or_404(db, order_id, user)


@router.post(
    "/",
    response_model=OrderOut,
    status_code=201,
    summary="Создать заказ (лимит 20/мин с одного IP)",
    dependencies=[Depends(rate_limit(settings.orders_rate_limit, settings.orders_rate_window))],
)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = await build_items(db, payload.items, user)
    order = Order(status=OrderStatus.ACCEPTED.value, items=items, user_id=user.id)
    db.add(order)
    await db.commit()  # задачу ставим только после commit, иначе воркер может не найти заказ

    # apply_async — синхронный вызов (сеть), поэтому уводим его из event loop в поток
    await run_in_threadpool(tasks.schedule_order_progress, order.id)
    ORDERS_CREATED.inc()
    ORDER_TOTAL.observe(float(sum(i.price * i.quantity for i in items)))
    return await fetch_order(db, order.id)


@router.put("/{order_id}", response_model=OrderOut, summary="Полностью обновить заказ")
async def update_order(
    payload: OrderUpdate,
    order_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await get_order_or_404(db, order_id, user)
    ensure_editable(user, order)
    if not is_admin(user) and payload.status != OrderStatus.ACCEPTED:
        raise HTTPException(status_code=403, detail="Only staff can change order status")
    order.items = await build_items(db, payload.items, user)
    order.status = payload.status.value
    await db.commit()
    return await fetch_order(db, order_id)


@router.patch(
    "/{order_id}/status",
    response_model=OrderOut,
    summary="Изменить статус заказа (персонал)",
    dependencies=[Depends(require_staff)],
)
async def change_status(
    body: OrderStatusUpdate,
    order_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    order = await get_order_or_404(db, order_id)
    order.status = body.status.value
    await db.commit()
    ORDER_STATUS_CHANGES.labels(status=body.status.value, source="api").inc()
    return await fetch_order(db, order_id)


@router.delete("/{order_id}", status_code=204, summary="Удалить (отменить) заказ")
async def delete_order(
    order_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await get_order_or_404(db, order_id, user)
    ensure_editable(user, order)
    await db.delete(order)
    await db.commit()
    return Response(status_code=204)
