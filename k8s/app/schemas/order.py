from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dish_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, le=100)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[OrderItemCreate] = Field(..., min_length=1, max_length=50)


class OrderUpdate(OrderCreate):
    """PUT: полностью заменяет состав заказа и статус."""
    status: OrderStatus


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dish_id: int
    dish_name: str
    quantity: int
    price: float

    @field_validator("price", mode="before")
    @classmethod
    def _decimal_to_float(cls, value):
        return float(value) if isinstance(value, Decimal) else value

    @computed_field
    @property
    def subtotal(self) -> float:
        return round(self.price * self.quantity, 2)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    created_at: datetime
    user_id: Optional[int] = None

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        # SQLite возвращает время без часового пояса; без «+00:00» браузер принял бы его за местное
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    items: List[OrderItemOut]

    @computed_field
    @property
    def total(self) -> float:
        return round(sum(item.subtotal for item in self.items), 2)
