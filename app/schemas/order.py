from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    dish_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, le=100)


class OrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(..., min_length=1, max_length=50)


class OrderUpdate(OrderCreate):
    """PUT: полностью заменяет состав заказа и статус."""
    status: OrderStatus


class OrderStatusUpdate(BaseModel):
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
    items: List[OrderItemOut]

    @computed_field
    @property
    def total(self) -> float:
        return round(sum(item.subtotal for item in self.items), 2)
