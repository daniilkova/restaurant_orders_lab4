import httpx
import pytest

from app import captcha
from app.config import settings


@pytest.fixture
def turnstile(monkeypatch):
    """Включаем капчу и подменяем ответ Cloudflare siteverify."""
    monkeypatch.setattr(settings, "turnstile_secret_key", "1x0000000000000000000000000000000AA")
    seen = {}

    def install(success: bool):
        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = request.content.decode()
            return httpx.Response(200, json={"success": success, "error-codes": [] if success else ["invalid-input-response"]})

        transport = httpx.MockTransport(handler)
        original = httpx.AsyncClient

        monkeypatch.setattr(captcha.httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw))

    return install, seen


def body(username="ivan"):
    return {"username": username, "password": "Pizza2026", "email": f"{username}@mail.ru"}


def test_register_without_captcha_token_rejected(anon, turnstile):
    install, _ = turnstile
    install(True)
    response = anon.post("/auth/register", json=body())
    assert response.status_code == 400 and response.json()["detail"] == "captcha_failed"


def test_register_with_valid_captcha(anon, turnstile, outbox):
    install, seen = turnstile
    install(True)
    response = anon.post("/auth/register", json=body(), headers={"X-Turnstile-Token": "XXXX.DUMMY.TOKEN"})
    assert response.status_code == 201
    assert "response=XXXX.DUMMY.TOKEN" in seen["body"] and "remoteip=" in seen["body"]


def test_login_with_failed_captcha(anon, turnstile):
    install, _ = turnstile
    install(False)
    response = anon.post("/auth/token", data={"username": "a", "password": "b"}, headers={"X-Turnstile-Token": "bad"})
    assert response.status_code == 400


def test_real_ip_from_trusted_header(client, monkeypatch):
    from starlette.requests import Request

    scope = {"type": "http", "headers": [(b"cf-connecting-ip", b"203.0.113.7")], "client": ("172.70.1.1", 1234)}
    assert captcha.client_ip(Request(scope)) == "172.70.1.1"  # заголовку без настройки не доверяем
    monkeypatch.setattr(settings, "client_ip_header", "CF-Connecting-IP")
    assert captcha.client_ip(Request(scope)) == "203.0.113.7"
