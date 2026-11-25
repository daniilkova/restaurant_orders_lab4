from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base


class OrderStatus(str, Enum):
    ACCEPTED = "принят"
    COOKING = "готовится"
    DELIVERING = "доставляется"
    COMPLETED = "завершён"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(
        String(20), default=OrderStatus.ACCEPTED.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    # Владелец заказа (BOLA: клиент видит и меняет только свои заказы)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    items: Mapped[List["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @validates("status")
    def _validate_status(self, key: str, value: str) -> str:
        OrderStatus(value)  # ValueError, если статус не из списка (в том числе при правке в админке)
        return value

    def __str__(self) -> str:
        return f"Заказ #{self.id}"


class OrderItem(Base):
    """Позиция заказа. Название и цена блюда копируются на момент заказа,
    чтобы последующая смена цены в меню не меняла старые заказы."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), index=True)
    dish_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="items")

    def __str__(self) -> str:
        return f"{self.dish_name} x{self.quantity}"
