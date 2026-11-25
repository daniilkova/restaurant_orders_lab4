"""Аутентификация, роли и защита от OWASP API Top 10."""
import time

import jwt
import pytest

from app.config import settings


def register(anon, username="ivan", password="Pizza2026", **extra):
    return anon.post("/auth/register", json={"username": username, "password": password, **extra})


def login(anon, username="ivan", password="Pizza2026"):
    return anon.post("/auth/token", data={"username": username, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- регистрация и вход ----------
def test_register_login_me(anon):
    assert register(anon).status_code == 201
    tokens = login(anon).json()
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] == settings.access_token_expire_minutes * 60
    me = anon.get("/auth/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "ivan" and me.json()["role"] == "user"
    assert "hashed_password" not in me.json()


def test_register_cannot_set_role_mass_assignment(anon):
    response = register(anon, role="admin")
    assert response.status_code == 422  # лишнее поле role отклоняется, а не игнорируется


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678", "ivan12345"])
def test_password_policy(anon, password):
    assert register(anon, password=password).status_code == 422


def test_duplicate_username_409(anon):
    register(anon)
    assert register(anon).status_code == 409


def test_wrong_password_and_unknown_user_same_answer(anon):
    register(anon)
    wrong = login(anon, password="Wrong12345")
    unknown = login(anon, username="nobody")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_bruteforce_is_limited(anon, monkeypatch):
    monkeypatch.setattr(settings, "login_max_attempts", 3)
    register(anon)
    for _ in range(3):
        assert login(anon, password="Wrong12345").status_code == 401
    blocked = login(anon)  # даже верный пароль: лимит исчерпан
    assert blocked.status_code == 429 and "retry-after" in blocked.headers


# ---------- токены ----------
def test_protected_endpoint_requires_token(anon):
    assert anon.get("/orders/").status_code == 401
    assert anon.get("/orders/", headers=bearer("garbage")).status_code == 401


def test_refresh_token_not_accepted_as_access(anon):
    register(anon)
    tokens = login(anon).json()
    assert anon.get("/auth/me", headers=bearer(tokens["refresh_token"])).status_code == 401


def test_token_with_alg_none_rejected(anon):
    register(anon)
    payload = jwt.decode(login(anon).json()["access_token"], options={"verify_signature": False})
    forged = jwt.encode({**payload, "role": "admin"}, key=None, algorithm="none")
    assert anon.get("/auth/me", headers=bearer(forged)).status_code == 401


def test_expired_token_rejected(anon):
    register(anon)
    payload = jwt.decode(login(anon).json()["access_token"], options={"verify_signature": False})
    payload["exp"] = int(time.time()) - 10
    expired = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    assert anon.get("/auth/me", headers=bearer(expired)).status_code == 401


def test_refresh_rotation_and_reuse_detection(anon):
    register(anon)
    first = login(anon).json()
    second = anon.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    second = second.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Старый refresh предъявлен повторно — кража: отзывается вся цепочка, включая новый токен
    reuse = anon.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    assert anon.post("/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh(anon):
    register(anon)
    tokens = login(anon).json()
    assert anon.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 204
    assert anon.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


# ---------- роли ----------
def test_user_cannot_modify_menu(client, anon, make_dish):
    dish = make_dish()
    register(anon)
    headers = bearer(login(anon).json()["access_token"])
    assert anon.post("/dishes/", json={"name": "X", "price": 1}, headers=headers).status_code == 403
    assert anon.delete(f"/dishes/{dish['id']}", headers=headers).status_code == 403
    assert anon.get("/dishes/").status_code == 200  # меню публичное


def test_users_admin_only_and_role_change_revokes_tokens(client, anon):
    register(anon)
    user_token = login(anon).json()["access_token"]
    assert anon.get("/users/", headers=bearer(user_token)).status_code == 403

    users = client.get("/users/").json()
    ivan = next(u for u in users if u["username"] == "ivan")
    assert client.patch(f"/users/{ivan['id']}", json={"is_active": False}).status_code == 200
    # access-токен ещё не истёк, но пользователь заблокирован — доступ закрыт сразу
    assert anon.get("/auth/me", headers=bearer(user_token)).status_code == 401
    assert login(anon).status_code == 401


def test_admin_cannot_demote_self(client):
    me = client.get("/auth/me").json()
    assert client.patch(f"/users/{me['id']}", json={"role": "user"}).status_code == 400


def test_mass_assignment_on_user_update(client):
    me = client.get("/auth/me").json()
    assert client.patch(f"/users/{me['id']}", json={"hashed_password": "x"}).status_code == 422


# ---------- BOLA ----------
def test_bola_user_sees_only_own_orders(client, anon, make_dish, user_headers):
    dish = make_dish()
    ivan, petr = user_headers("ivan"), user_headers("petr")
    order = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 2}]}, headers=petr)

    assert [o["id"] for o in anon.get("/orders/", headers=ivan).json()] == [order["id"]]
    assert anon.get(f"/orders/{order['id']}", headers=petr).status_code == 404  # чужой = не существует
    assert anon.delete(f"/orders/{order['id']}", headers=petr).status_code == 404
    assert len(client.get("/orders/").json()) == 2  # администратор видит все


def test_user_cannot_change_status(anon, make_dish, user_headers):
    dish = make_dish()
    ivan = user_headers("ivan")
    order = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    assert anon.patch(f"/orders/{order['id']}/status", json={"status": "завершён"}, headers=ivan).status_code == 403
    body = {"items": [{"dish_id": dish["id"], "quantity": 3}], "status": "завершён"}
    assert anon.put(f"/orders/{order['id']}", json=body, headers=ivan).status_code == 403


def test_user_can_cancel_only_accepted_order(client, anon, make_dish, user_headers):
    dish = make_dish()
    ivan = user_headers("ivan")
    first = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    second = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    client.patch(f"/orders/{second['id']}/status", json={"status": "готовится"})
    assert anon.delete(f"/orders/{first['id']}", headers=ivan).status_code == 204
    assert anon.delete(f"/orders/{second['id']}", headers=ivan).status_code == 409


# ---------- заголовки и служебные эндпоинты ----------
def test_security_headers(anon):
    response = anon.get("/dishes/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert anon.post("/auth/token", data={"username": "a", "password": "b"}).headers["cache-control"] == "no-store"


def test_metrics_protected_by_token(anon, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    assert anon.get("/metrics").status_code == 401
    assert anon.get("/metrics", headers=bearer("scrape-secret")).status_code == 200


def test_bootstrap_admin_created_once(client):
    import asyncio

    from app.bootstrap import ensure_admin

    # В тестовой БД уже есть admin — второй не создаётся
    assert asyncio.run(ensure_admin("boss", "Boss12345", client.session_maker)) is False
