"""Заказы: CRUD + смена статуса. POST /orders ограничен 20 запросами в минуту с одного IP."""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app import tasks
from app.config import settings
from app.database import get_db
from app.metrics import ORDER_STATUS_CHANGES, ORDER_TOTAL, ORDERS_CREATED
from app.models import Dish, Order, OrderItem, OrderStatus
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


async def get_order_or_404(db: AsyncSession, order_id: int) -> Order:
    order = await fetch_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def build_items(db: AsyncSession, items_in) -> List[OrderItem]:
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
):
    query = select(Order).options(selectinload(Order.items)).order_by(Order.id)
    if status is not None:
        query = query.where(Order.status == status.value)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderOut, summary="Заказ по ID")
async def get_order(order_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    return await get_order_or_404(db, order_id)


@router.post(
    "/",
    response_model=OrderOut,
    status_code=201,
    summary="Создать заказ (лимит 20/мин с одного IP)",
    dependencies=[Depends(rate_limit(settings.orders_rate_limit, settings.orders_rate_window))],
)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    items = await build_items(db, payload.items)
    order = Order(status=OrderStatus.ACCEPTED.value, items=items)
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
):
    order = await get_order_or_404(db, order_id)
    order.items = await build_items(db, payload.items)
    order.status = payload.status.value
    await db.commit()
    return await fetch_order(db, order_id)


@router.patch("/{order_id}/status", response_model=OrderOut, summary="Изменить статус заказа")
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


@router.delete("/{order_id}", status_code=204, summary="Удалить заказ")
async def delete_order(order_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    order = await get_order_or_404(db, order_id)
    await db.delete(order)
    await db.commit()
    return Response(status_code=204)
