"""Тестовое окружение: SQLite-файл во временной папке, поддельный Redis, замоканный Celery.

Для тестов не нужны ни Docker, ни Redis, ни PostgreSQL.
"""
import asyncio
from typing import List

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import tasks
from app.database import Base, get_db
from app.main import app
from app.redis_client import get_redis
from app.s3_client import S3Storage, get_storage


class FakeRedis:
    """Минимальная in-memory замена Redis (TTL только записывается, не истекает)."""

    def __init__(self) -> None:
        self.store = {}
        self.ttls = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if self.store.pop(key, None) is not None:
                deleted += 1
            self.ttls.pop(key, None)
        return deleted

    async def incr(self, key):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = value
        return value

    async def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    async def ttl(self, key):
        return self.ttls.get(key, -1)


class BrokenRedis:
    """Redis, который «упал»: любая команда бросает ConnectionError."""

    def __getattr__(self, name):
        async def fail(*args, **kwargs):
            raise RedisConnectionError("redis is down")

        return fail


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def scheduled_tasks(monkeypatch) -> List[int]:
    """Вместо Celery запоминаем ID заказов, для которых поставили бы задачу."""
    scheduled: List[int] = []
    monkeypatch.setattr(
        tasks, "schedule_order_progress", lambda order_id: scheduled.append(order_id)
    )
    return scheduled


@pytest.fixture
def client(tmp_path, fake_redis, scheduled_tasks):
    db_file = (tmp_path / "test.db").as_posix()
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", poolclass=NullPool)

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    yield TestClient(app)
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


@pytest.fixture
def broken_redis(client):
    """Подменяет Redis на «упавший» (используйте вместе с client)."""
    app.dependency_overrides[get_redis] = lambda: BrokenRedis()


@pytest.fixture
def make_dish(client):
    def _make(name="Пицца Маргарита", price=450.0, **extra):
        response = client.post("/dishes/", json={"name": name, "price": price, **extra})
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def s3_storage(client):
    """S3 в памяти (moto): реальные вызовы boto3, но без сервера SeaweedFS."""
    from moto import mock_aws

    with mock_aws():
        storage = S3Storage(None, "test-bucket", "us-east-1", "test", "test")
        storage.client.create_bucket(Bucket="test-bucket")
        app.dependency_overrides[get_storage] = lambda: storage
        yield storage
