"""Создать администратора вручную: python -m scripts.create_admin <логин>  (пароль спросит)."""
import asyncio
import getpass
import sys

from app.bootstrap import ensure_admin


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else input("Логин: ")
    password = getpass.getpass("Пароль: ")
    created = asyncio.run(ensure_admin(username, password))
    print("Администратор создан" if created else "Администратор уже существует — ничего не изменено")


if __name__ == "__main__":
    main()
