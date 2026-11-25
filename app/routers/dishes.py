"""Меню. GET /dishes кэшируется в Redis на 1 минуту, при изменении меню кэш сбрасывается."""
import logging
import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Path, Response, UploadFile
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.metrics import FILES_UPLOADED
from app.models import Dish, OrderItem
from app.redis_client import DISHES_CACHE_KEY, get_cached, get_redis, invalidate_cache
from app.s3_client import S3Storage, get_storage
from app.schemas.dish import DishCreate, DishOut, DishUpdate
from app.uploads import EXTENSIONS, read_limited, require_image

router = APIRouter(prefix="/dishes", tags=["dishes"])
logger = logging.getLogger(__name__)


async def get_dish_or_404(db: AsyncSession, dish_id: int) -> Dish:
    dish = await db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return dish


@router.get("/", response_model=List[DishOut], summary="Меню (кэш 1 минута)")
async def list_dishes(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    async def fetch_from_db():
        result = await db.execute(select(Dish).order_by(Dish.id))
        return [DishOut.model_validate(d).model_dump(mode="json") for d in result.scalars()]

    return await get_cached(redis, DISHES_CACHE_KEY, fetch_from_db, ttl=settings.dishes_cache_ttl)


@router.get("/{dish_id}", response_model=DishOut, summary="Блюдо по ID")
async def get_dish(dish_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    return await get_dish_or_404(db, dish_id)


@router.post("/", response_model=DishOut, status_code=201, summary="Добавить блюдо")
async def create_dish(
    payload: DishCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    dish = Dish(
        name=payload.name,
        description=payload.description,
        price=Decimal(str(payload.price)),
        is_available=payload.is_available,
    )
    db.add(dish)
    await db.commit()
    await invalidate_cache(redis, DISHES_CACHE_KEY)
    return dish


@router.put("/{dish_id}", response_model=DishOut, summary="Обновить блюдо (в т.ч. цену)")
async def update_dish(
    payload: DishUpdate,
    dish_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    dish = await get_dish_or_404(db, dish_id)
    dish.name = payload.name
    dish.description = payload.description
    dish.price = Decimal(str(payload.price))
    dish.is_available = payload.is_available
    await db.commit()
    await invalidate_cache(redis, DISHES_CACHE_KEY)
    return dish


@router.delete("/{dish_id}", status_code=204, summary="Удалить блюдо")
async def delete_dish(
    dish_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    dish = await get_dish_or_404(db, dish_id)
    used = await db.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.dish_id == dish_id)
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail="Dish is used in orders; set is_available=false instead of deleting",
        )
    await db.delete(dish)
    await db.commit()
    await invalidate_cache(redis, DISHES_CACHE_KEY)
    return Response(status_code=204)


@router.put("/{dish_id}/image", response_model=DishOut, summary="Загрузить фото блюда (JPEG/PNG/WebP)")
async def upload_dish_image(
    dish_id: int = Path(..., gt=0),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: S3Storage = Depends(get_storage),
):
    dish = await get_dish_or_404(db, dish_id)
    data = await read_limited(file, settings.max_image_mb)
    content_type = require_image(data)  # тип по сигнатуре файла, а не по заголовку клиента
    key = f"dishes/{dish_id}/{uuid.uuid4().hex}{EXTENSIONS[content_type]}"
    await storage.upload(key, data, content_type)
    old_key, dish.image_key = dish.image_key, key
    await db.commit()
    if old_key:
        try:
            await storage.delete(old_key)
        except Exception:  # старое фото не критично: заказ меню уже обновлён
            logger.warning("Не удалось удалить старое фото %s", old_key, exc_info=True)
    FILES_UPLOADED.labels(kind="dish_image").inc()
    await invalidate_cache(redis, DISHES_CACHE_KEY)
    return dish


@router.get("/{dish_id}/image", summary="Фото блюда", response_class=Response)
async def get_dish_image(
    dish_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    storage: S3Storage = Depends(get_storage),
):
    dish = await get_dish_or_404(db, dish_id)
    if not dish.image_key:
        raise HTTPException(status_code=404, detail="Dish has no image")
    try:
        data, content_type = await storage.download(dish.image_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found in storage") from None
    return Response(
        content=data,
        media_type=content_type,
        # ключ меняется при каждой загрузке, поэтому фото можно кэшировать надолго
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
