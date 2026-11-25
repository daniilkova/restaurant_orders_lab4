"""Демо-данные для фронтенда: администратор, два клиента, меню и заказы.

    alembic upgrade head && python -m scripts.seed_demo
Учётные записи: admin / Admin12345 (администратор), manager / Manager2026 (модератор),
ivan / Pizza2026, maria / Sushi2026 (клиенты).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models import Dish, Order, OrderItem, Role, User

USERS = [
    ("admin", "Admin12345", Role.ADMIN),
    ("manager", "Manager2026", Role.MODERATOR),
    ("ivan", "Pizza2026", Role.CLIENT),
    ("maria", "Sushi2026", Role.CLIENT),
]
DISHES = [
    ("Пицца Маргарита", "Томаты, моцарелла, базилик", "450.00"),
    ("Пицца Пепперони", "Пепперони, моцарелла, томатный соус", "520.00"),
    ("Ролл Филадельфия", "Лосось, сливочный сыр, огурец", "590.00"),
    ("Борщ", "Со сметаной и пампушками", "320.00"),
    ("Цезарь с курицей", "Романо, курица гриль, пармезан, соус цезарь", "410.00"),
    ("Паста Карбонара", "Бекон, яйцо, пармезан", "480.00"),
    ("Морс клюквенный", "0,5 л", "150.00"),
    ("Чизкейк", "Нью-Йорк, с ягодным соусом", "290.00"),
    ("Вино красное, бокал", "Каберне Совиньон, 150 мл (18+)", "390.00", 18),
    ("Пиво крафтовое", "IPA, 0,5 л (18+)", "330.00", 18),
]
ORDERS = [  # (клиент, статус, [(индекс блюда, количество)], минут назад)
    ("ivan", "завершён", [(0, 1), (6, 2)], 180),
    ("ivan", "доставляется", [(2, 2), (7, 1)], 35),
    ("ivan", "принят", [(1, 1), (4, 1), (6, 1)], 3),
    ("maria", "готовится", [(3, 2), (5, 1)], 12),
    ("maria", "принят", [(2, 1)], 1),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(User.id).limit(1)):
            print("Данные уже есть — пропускаю")
            return
        users = {}
        for username, password, role in USERS:
            users[username] = User(username=username, hashed_password=hash_password(password), role=role.value,
                                   email=f"{username}@restaurant-demo.ru", is_email_verified=True)
            db.add(users[username])
        dishes = [Dish(name=n, description=d, price=Decimal(p), min_age=(rest[0] if rest else 0))
                  for n, d, p, *rest in DISHES]
        db.add_all(dishes)
        await db.flush()
        now = datetime.now(timezone.utc)
        for username, status, items, minutes in ORDERS:
            db.add(Order(
                user_id=users[username].id,
                status=status,
                created_at=now - timedelta(minutes=minutes),
                items=[OrderItem(dish_id=dishes[i].id, dish_name=dishes[i].name, quantity=q, price=dishes[i].price)
                       for i, q in items],
            ))
        await db.commit()
    print("Готово: admin / Admin12345, manager / Manager2026, ivan / Pizza2026, maria / Sushi2026")


if __name__ == "__main__":
    asyncio.run(main())
