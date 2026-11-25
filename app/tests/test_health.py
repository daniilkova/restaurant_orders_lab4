from app.routers import health


def test_health_is_always_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_dependencies_ok(client, monkeypatch):
    async def ok():
        return None

    monkeypatch.setitem(health.CHECKS, "database", ok)
    monkeypatch.setitem(health.CHECKS, "redis", ok)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


def test_ready_returns_503_when_redis_down(client, monkeypatch):
    async def ok():
        return None

    async def down():
        raise ConnectionError("redis is down")

    monkeypatch.setitem(health.CHECKS, "database", ok)
    monkeypatch.setitem(health.CHECKS, "redis", down)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not ready",
        "checks": {"database": "ok", "redis": "unavailable"},
    }


def test_ready_times_out_slow_dependency(client, monkeypatch):
    import asyncio

    from app.config import settings

    async def slow():
        await asyncio.sleep(5)

    async def ok():
        return None

    monkeypatch.setattr(settings, "ready_check_timeout", 0.05)
    monkeypatch.setitem(health.CHECKS, "database", slow)
    monkeypatch.setitem(health.CHECKS, "redis", ok)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"


def test_database_url_from_parts(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_HOST", "restaurant-db-rw")
    monkeypatch.setenv("DATABASE_NAME", "restaurant")
    monkeypatch.setenv("DATABASE_USER", "app")
    monkeypatch.setenv("DATABASE_PASSWORD", "p@ss/word")
    url = Settings().database_url
    assert url == "postgresql+asyncpg://app:p%40ss%2Fword@restaurant-db-rw:5432/restaurant"


def test_celery_config_for_keda():
    from app.celery_app import celery_app

    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_default_queue == "celery"
