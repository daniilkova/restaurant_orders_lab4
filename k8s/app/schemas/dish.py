from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DishBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: float = Field(..., gt=0, le=100000)
    is_available: bool = True
    min_age: int = Field(0, ge=0, le=21, description="Возрастное ограничение: 0 или 18 (алкоголь)")


class DishCreate(DishBase):
    pass


class DishUpdate(DishBase):
    """PUT: полная замена данных блюда."""


class DishOut(DishBase):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    # Адрес фото блюда: файл отдаёт API, бакет S3 наружу не публикуется.
    # Обычное поле (а не computed): ответ из кэша Redis — это уже готовый dict с image_url.
    image_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _image_url_from_key(cls, data):
        if isinstance(data, dict):
            return data
        image_key = getattr(data, "image_key", None)
        return {
            "id": data.id,
            "name": data.name,
            "description": data.description,
            "price": data.price,
            "is_available": data.is_available,
            "min_age": data.min_age or 0,
            "image_url": f"/dishes/{data.id}/image" if image_key else None,
        }

    @field_validator("price", mode="before")
    @classmethod
    def _decimal_to_float(cls, value):
        return float(value) if isinstance(value, Decimal) else value
