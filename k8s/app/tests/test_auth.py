"""Аутентификация, роли и защита от OWASP API Top 10 (с ЛР8: cookies, подтверждение email, 2FA)."""
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pyotp
import pytest

from app.config import settings


def register(anon, username="ivan", password="Pizza2026", email=None, **extra):
    return anon.post("/auth/register", json={
        "username": username, "password": password, "email": email or f"{username}@mail.ru", **extra})


def login(anon, username="ivan", password="Pizza2026"):
    return anon.post("/auth/token", data={"username": username, "password": password})


def verify_from_outbox(anon, outbox, index=-1):
    token = parse_qs(urlparse(outbox[index][1]).query)["token"][0]
    return anon.get("/auth/verify-email", params={"token": token})


def signup(anon, outbox, username="ivan", password="Pizza2026"):
    assert register(anon, username, password).status_code == 201
    assert verify_from_outbox(anon, outbox).status_code == 200


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- регистрация и подтверждение email ----------
def test_register_sends_email_and_login_blocked_until_verified(anon, outbox):
    response = register(anon)
    assert response.status_code == 201
    assert response.json()["requires_age_verification"] is False
    assert outbox[0][0] == "ivan@mail.ru" and "/verify-email?token=" in outbox[0][1]
    assert login(anon).json() == {"detail": "email_not_verified"}
    assert verify_from_outbox(anon, outbox).json()["verified"] is True
    assert login(anon).status_code == 200


def test_verification_link_is_one_time_and_stored_hashed(client, anon, outbox):
    register(anon)
    token = parse_qs(urlparse(outbox[0][1]).query)["token"][0]
    assert anon.get("/auth/verify-email", params={"token": token}).status_code == 200
    assert anon.get("/auth/verify-email", params={"token": token}).status_code == 400

    import asyncio

    from sqlalchemy import select

    from app.models import User

    async def stored():
        async with client.session_maker() as db:
            return await db.scalar(select(User.email_verification_token).where(User.username == "ivan"))

    assert asyncio.run(stored()) is None  # после подтверждения токен удалён


def test_register_role_is_client_mass_assignment_rejected(anon, outbox):
    assert register(anon, role="admin").status_code == 422
    signup(anon, outbox)
    login(anon)
    assert anon.get("/auth/me").json()["role"] == "client"


def test_register_conflict_409_with_field(anon, outbox):
    register(anon)
    dup = register(anon, username="ivan2", email="ivan@mail.ru")
    assert dup.status_code == 409 and dup.json()["detail"]["field"] == "email"


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678", "ivan12345"])
def test_password_policy(anon, password):
    assert register(anon, password=password).status_code == 422


def test_resend_does_not_reveal_registered_emails(anon, outbox):
    a = anon.post("/auth/resend-verification", json={"email": "nobody@mail.ru"})
    register(anon)
    b = anon.post("/auth/resend-verification", json={"email": "ivan@mail.ru"})
    assert a.status_code == b.status_code == 202 and a.json() == b.json()
    assert len(outbox) == 2


# ---------- вход и cookies ----------
def test_login_sets_httponly_cookies(anon, outbox):
    signup(anon, outbox)
    response = login(anon)
    cookies = response.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith("access_token="))
    refresh = next(c for c in cookies if c.startswith("refresh_token="))
    assert "HttpOnly" in access and "SameSite=strict" in access and "Path=/" in access
    assert "HttpOnly" in refresh and "Path=/auth/refresh" in refresh
    assert "refresh_token" not in response.json()
    assert anon.get("/auth/me").status_code == 200  # cookie, без заголовка Authorization


def test_wrong_password_and_unknown_user_same_answer(anon, outbox):
    signup(anon, outbox)
    wrong, unknown = login(anon, password="Wrong12345"), login(anon, username="nobody")
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_login_bruteforce_is_limited(anon, outbox, monkeypatch):
    monkeypatch.setattr(settings, "login_max_attempts", 3)
    signup(anon, outbox)
    for _ in range(3):
        assert login(anon, password="Wrong12345").status_code == 401
    assert login(anon).status_code == 429


def test_logout_clears_cookies_and_me_401(anon, outbox):
    signup(anon, outbox)
    login(anon)
    assert anon.post("/auth/logout").status_code == 204
    assert anon.get("/auth/me").status_code == 401


def test_csrf_header_required_for_cookie_requests(anon, outbox, make_dish):
    from fastapi.testclient import TestClient

    from app.main import app

    signup(anon, outbox)
    login(anon)
    browser_without_header = TestClient(app, cookies=dict(anon.cookies))
    dish = make_dish()
    body = {"items": [{"dish_id": dish["id"], "quantity": 1}]}
    assert browser_without_header.post("/orders/", json=body).status_code == 403
    assert anon.post("/orders/", json=body).status_code == 201


# ---------- токены ----------
def test_refresh_rotation_and_reuse_detection(anon, outbox):
    signup(anon, outbox)
    login(anon)
    first = anon.cookies.get("refresh_token")
    assert anon.post("/auth/refresh", json={"refresh_token": first}).status_code == 204
    second = anon.cookies.get("refresh_token")
    assert second and second != first
    # старый refresh предъявлен повторно — отзывается вся цепочка, включая новый
    assert anon.post("/auth/refresh", json={"refresh_token": first}).status_code == 401
    assert anon.post("/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_token_forgery_rejected(anon, outbox):
    signup(anon, outbox)
    token = login(anon).json()["access_token"]
    payload = jwt.decode(token, options={"verify_signature": False})
    assert anon.get("/auth/me", headers=bearer(jwt.encode({**payload, "role": "admin"}, None, algorithm="none"))).status_code == 401
    payload["exp"] = int(time.time()) - 10
    assert anon.get("/auth/me", headers=bearer(jwt.encode(payload, settings.secret_key, algorithm="HS256"))).status_code == 401


# ---------- 2FA ----------
def enable_2fa(anon):
    secret = anon.post("/auth/2fa/enable").json()["secret"]
    assert anon.post("/auth/2fa/confirm", json={"code": pyotp.TOTP(secret).now()}).json()["totp_enabled"] is True
    return secret


def test_2fa_enable_requires_valid_code(anon, outbox):
    signup(anon, outbox)
    login(anon)
    data = anon.post("/auth/2fa/enable").json()
    assert data["otpauth_uri"].startswith("otpauth://totp/") and data["qr_svg"].startswith("data:image/svg+xml")
    assert anon.post("/auth/2fa/confirm", json={"code": "000000"}).status_code == 400
    assert anon.get("/auth/me").json()["totp_enabled"] is False


def test_login_with_2fa_two_steps(anon, outbox):
    signup(anon, outbox)
    login(anon)
    secret = enable_2fa(anon)
    anon.post("/auth/logout")
    step1 = login(anon)
    assert step1.json()["2fa_required"] is True and "access_token" not in step1.headers.get("set-cookie", "")
    temp = step1.json()["temp_token"]
    assert anon.get("/auth/me", headers=bearer(temp)).status_code == 401  # temp_token — не access
    assert anon.post("/auth/2fa/verify", json={"temp_token": temp, "code": "123456"}).status_code == 401
    ok = anon.post("/auth/2fa/verify", json={"temp_token": temp, "code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200
    assert anon.get("/auth/me").json()["username"] == "ivan"


def test_disable_2fa_needs_password_and_code(anon, outbox):
    signup(anon, outbox)
    login(anon)
    secret = enable_2fa(anon)
    assert anon.post("/auth/2fa/disable", json={"password": "Wrong12345", "code": pyotp.TOTP(secret).now()}).status_code == 400
    assert anon.post("/auth/2fa/disable", json={"password": "Pizza2026", "code": pyotp.TOTP(secret).now()}).status_code == 200


# ---------- пароль и сессии ----------
def test_change_password_revokes_other_sessions(anon, outbox):
    from fastapi.testclient import TestClient

    from app.main import app

    signup(anon, outbox)
    login(anon)
    other = TestClient(app, headers={"X-Requested-With": "XMLHttpRequest"})
    login(other)
    other_refresh = other.cookies.get("refresh_token")
    bad = anon.post("/auth/change-password", json={"current_password": "Wrong1234", "new_password": "Burger2027"})
    assert bad.status_code == 400
    ok = anon.post("/auth/change-password", json={"current_password": "Pizza2026", "new_password": "Burger2027"})
    assert ok.status_code == 204
    assert anon.get("/auth/me").status_code == 200        # текущее устройство осталось в системе
    assert other.get("/auth/me").status_code == 401       # старый access второго устройства недействителен
    assert other.post("/auth/refresh", json={"refresh_token": other_refresh}).status_code == 401
    assert login(anon, password="Burger2027").status_code == 200


def test_sessions_list_and_revoke_current(anon, outbox):
    from fastapi.testclient import TestClient

    from app.main import app

    signup(anon, outbox)
    login(anon)
    phone = TestClient(app, headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": "Phone"})
    login(phone)
    sessions = anon.get("/auth/sessions").json()
    assert len(sessions) == 2 and sessions[0]["current"] is True
    phone_session = next(s for s in sessions if not s["current"])
    assert anon.delete(f"/auth/sessions/{phone_session['id']}").status_code == 204
    assert phone.post("/auth/refresh", json={"refresh_token": phone.cookies.get("refresh_token")}).status_code == 401
    assert anon.delete(f"/auth/sessions/{sessions[0]['id']}").status_code == 204
    assert anon.get("/auth/me").status_code == 401


def test_cannot_revoke_foreign_session(anon, outbox, client):
    signup(anon, outbox)
    login(anon)
    session_id = anon.get("/auth/sessions").json()[0]["id"]
    assert client.delete(f"/auth/sessions/{session_id}").status_code == 404


# ---------- профиль ----------
def test_username_change_cooldown_and_uniqueness(anon, outbox, client):
    signup(anon, outbox)
    login(anon)
    assert anon.patch("/users/me/username", json={"username": "admin"}).status_code == 409
    changed = anon.patch("/users/me/username", json={"username": "ivan_petrov"})
    assert changed.status_code == 200 and changed.json()["next_username_change_at"]
    again = anon.patch("/users/me/username", json={"username": "ivan_2"})
    assert again.status_code == 429 and "next_change_at" in again.json()["detail"]


def test_display_name(anon, outbox):
    signup(anon, outbox)
    login(anon)
    assert anon.patch("/users/me", json={"display_name": "Иван"}).json()["display_name"] == "Иван"


def test_avatar_upload_rejects_svg(anon, outbox, s3_storage):
    signup(anon, outbox)
    login(anon)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert anon.put("/users/me/avatar", files={"file": ("a.svg", svg, "image/svg+xml")}).status_code == 415
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    me = anon.put("/users/me/avatar", files={"file": ("a.png", png, "image/png")}).json()
    assert me["avatar_url"].startswith(f"/users/{me['id']}/avatar")
    image = anon.get(me["avatar_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"


# ---------- роли ----------
def test_roles_client_moderator_admin(client, anon, outbox, make_dish):
    signup(anon, outbox)
    login(anon)
    dish = make_dish()
    assert anon.post("/dishes/", json={"name": "X", "price": 1}).status_code == 403
    users = client.get("/users/").json()
    ivan = next(u for u in users if u["username"] == "ivan")
    assert client.patch(f"/users/{ivan['id']}", json={"role": "moderator"}).status_code == 200
    login(anon)  # смена роли отзывает токены — входим заново
    assert anon.post("/dishes/", json={"name": "Суп дня", "price": 250}).status_code == 201
    assert anon.patch(f"/orders/{dish['id']}/status", json={"status": "готовится"}).status_code in (200, 404)
    assert anon.get("/users/").status_code == 403  # пользователями управляет только admin


def test_admin_cannot_demote_self(client):
    me = client.get("/auth/me").json()
    assert client.patch(f"/users/{me['id']}", json={"role": "client"}).status_code == 400


# ---------- BOLA ----------
def test_bola_user_sees_only_own_orders(client, anon, make_dish, user_headers):
    dish = make_dish()
    ivan, petr = user_headers("ivan"), user_headers("petr")
    order = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 2}]}, headers=petr)
    assert [o["id"] for o in anon.get("/orders/", headers=ivan).json()] == [order["id"]]
    assert anon.get(f"/orders/{order['id']}", headers=petr).status_code == 404
    assert anon.delete(f"/orders/{order['id']}", headers=petr).status_code == 404
    assert len(client.get("/orders/").json()) == 2


def test_user_cannot_change_status(anon, make_dish, user_headers):
    dish = make_dish()
    ivan = user_headers("ivan")
    order = anon.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]}, headers=ivan).json()
    assert anon.patch(f"/orders/{order['id']}/status", json={"status": "завершён"}, headers=ivan).status_code == 403


# ---------- возрастные ограничения ----------
def test_age_restricted_dishes_hidden_on_backend(client, anon, make_dish, user_headers):
    make_dish(name="Пицца")
    wine = make_dish(name="Вино красное", min_age=18)
    menu = anon.get("/dishes/")
    assert [d["name"] for d in menu.json()] == ["Пицца"] and menu.headers["x-hidden-age-restricted"] == "1"
    ivan = user_headers("ivan")
    assert anon.get(f"/dishes/{wine['id']}", headers=ivan).json() == {"detail": "age_verification_required"}
    body = {"items": [{"dish_id": wine["id"], "quantity": 1}]}
    assert anon.post("/orders/", json=body, headers=ivan).status_code == 403  # обход через прямой запрос закрыт
    assert len(client.get("/dishes/").json()) == 2  # персонал видит всё


def test_age_verification_mock_flow(client, anon, outbox, make_dish, monkeypatch):
    monkeypatch.setattr(settings, "age_verification_mock", True)
    wine = make_dish(name="Вино", min_age=18)
    signup(anon, outbox)
    login(anon)
    url = anon.post("/auth/age-session").json()["verificationUrl"]
    page = anon.get(urlparse(url).path + "?" + urlparse(url).query)
    assert page.status_code == 200 and "mock-паспорт" in page.text
    done = anon.get(urlparse(url).path + "?" + urlparse(url).query + "&outcome=success", follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"].endswith("/verify-age?age=success")
    assert anon.get("/auth/me").json()["is_age_verified"] is True
    assert anon.get(f"/dishes/{wine['id']}").status_code == 200


def test_registration_with_required_age_verification(anon, outbox, monkeypatch):
    monkeypatch.setattr(settings, "age_verification_on_register", True)
    monkeypatch.setattr(settings, "age_verification_mock", True)
    result = register(anon).json()
    assert result["requires_age_verification"] is True and outbox == []  # письма нет до верификации
    assert login(anon).json() == {"detail": "age_verification_required"}
    token = result["registration_token"]
    assert anon.post("/auth/complete-registration", json={"registration_token": token}).status_code == 403
    url = anon.post("/auth/age-session", headers={"X-Registration-Token": token}).json()["verificationUrl"]
    done = anon.get(urlparse(url).path + "?" + urlparse(url).query + "&outcome=success", follow_redirects=False)
    assert "registration=true" in done.headers["location"]
    assert anon.post("/auth/complete-registration", json={"registration_token": token}).json()["email_sent"] is True
    assert len(outbox) == 1
    verify_from_outbox(anon, outbox)
    assert login(anon).status_code == 200


def test_verify_age_requires_signed_agent_request(anon, outbox):
    signup(anon, outbox)
    login(anon)
    # без заголовков подписи агента Self SDK отвечает 401
    assert anon.post("/auth/verify-age").status_code == 401


def test_verify_age_with_agent_credentials(anon, outbox, monkeypatch):
    from types import SimpleNamespace

    from app.main import app
    from app.self_verifier import agent_auth

    signup(anon, outbox)
    login(anon)
    app.dependency_overrides[agent_auth] = lambda: SimpleNamespace(agent_id=7, credentials=SimpleNamespace(older_than=16))
    assert anon.post("/auth/verify-age").status_code == 403
    app.dependency_overrides[agent_auth] = lambda: SimpleNamespace(agent_id=7, credentials=SimpleNamespace(older_than=18))
    assert anon.post("/auth/verify-age").json() == {"verified": True, "agent_id": 7}
    app.dependency_overrides.pop(agent_auth)


# ---------- заголовки ----------
def test_security_headers(anon):
    response = anon.get("/dishes/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_metrics_protected_by_token(anon, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "scrape-secret")
    assert anon.get("/metrics").status_code == 401
    assert anon.get("/metrics", headers=bearer("scrape-secret")).status_code == 200
