from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Numeric, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dish(Base):
    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Ключ объекта с фото блюда в S3 (SeaweedFS), например dishes/3/9f1c....jpg
    image_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __str__(self) -> str:
        return self.name
