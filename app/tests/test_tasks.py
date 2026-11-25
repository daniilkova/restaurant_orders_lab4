from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import tasks
from app.config import settings
from app.database import Base
from app.models import Order


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'sync.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def make_order(factory, status="принят") -> int:
    with factory() as session:
        order = Order(status=status)
        session.add(order)
        session.commit()
        return order.id


def get_status(factory, order_id) -> str:
    with factory() as session:
        return session.get(Order, order_id).status


def test_apply_status_change(session_factory):
    order_id = make_order(session_factory)
    with session_factory() as session:
        assert tasks.apply_status_change(session, order_id, "доставляется") is True
    assert get_status(session_factory, order_id) == "доставляется"


def test_apply_status_change_missing_order(session_factory):
    with session_factory() as session:
        assert tasks.apply_status_change(session, 999, "доставляется") is False


def test_completed_order_is_not_touched(session_factory):
    order_id = make_order(session_factory, status="завершён")
    with session_factory() as session:
        assert tasks.apply_status_change(session, order_id, "доставляется") is False
    assert get_status(session_factory, order_id) == "завершён"


def test_task_changes_status_and_schedules_next_step(session_factory, monkeypatch):
    monkeypatch.setattr(tasks, "get_session_factory", lambda: session_factory)
    calls = []

    def fake_apply_async(args=None, kwargs=None, countdown=None, **options):
        calls.append({"args": args, "countdown": countdown})

    monkeypatch.setattr(tasks.advance_order_status, "apply_async", fake_apply_async)

    order_id = make_order(session_factory)
    result = tasks.advance_order_status.run(order_id, "доставляется", "завершён", 7)

    assert result["changed"] is True
    assert get_status(session_factory, order_id) == "доставляется"
    assert calls == [{"args": [order_id, "завершён"], "countdown": 7}]


def test_task_does_not_schedule_next_step_for_missing_order(session_factory, monkeypatch):
    monkeypatch.setattr(tasks, "get_session_factory", lambda: session_factory)
    calls = []
    monkeypatch.setattr(
        tasks.advance_order_status, "apply_async", lambda **kw: calls.append(kw)
    )
    result = tasks.advance_order_status.run(999, "доставляется", "завершён", 7)
    assert result["changed"] is False
    assert calls == []


def test_schedule_order_progress_enqueues_task(monkeypatch):
    calls = []

    def fake_apply_async(args=None, kwargs=None, countdown=None, **options):
        calls.append({"args": args, "countdown": countdown})
        return SimpleNamespace(id="task-1")

    monkeypatch.setattr(tasks.advance_order_status, "apply_async", fake_apply_async)

    assert tasks.schedule_order_progress(5) == "task-1"
    assert calls[0]["args"] == [5, "доставляется", "завершён", settings.delivery_delay_seconds]
    assert calls[0]["countdown"] == settings.cooking_delay_seconds


def test_schedule_order_progress_survives_broker_failure(monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("broker is down")

    monkeypatch.setattr(tasks.advance_order_status, "apply_async", broken)
    assert tasks.schedule_order_progress(5) is None


def test_kitchen_report_task_runs_without_broker():
    from app.tasks import prepare_kitchen_report

    # .run() выполняет тело задачи синхронно, без брокера
    assert prepare_kitchen_report.run(7, 0) == {"order_id": 7, "seconds": 0}
