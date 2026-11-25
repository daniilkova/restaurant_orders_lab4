"""HTTP-защита: заголовки безопасности, проверка Host, CORS, закрытие /metrics."""
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings

# Страницы со своим HTML/JS (Swagger, админка, живая таблица) — им строгий CSP API не подходит
HTML_PREFIXES = ("/docs", "/redoc", "/admin", "/dashboard", "/openapi.json", "/auth/age-mock")
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Вход по cookie: изменяющий запрос из браузера обязан нести этот заголовок. Чужой сайт не может
# добавить его без CORS-preflight, который наш сервер не разрешит, — это защита от CSRF поверх SameSite.
CSRF_HEADER = "x-requested-with"

API_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def setup_security(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        path = request.url.path
        if path == "/metrics" and settings.metrics_token:
            auth = request.headers.get("authorization", "")
            if not secrets.compare_digest(auth.encode(), f"Bearer {settings.metrics_token}".encode()):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        if (
            request.method in UNSAFE_METHODS
            and "access_token" in request.cookies
            and "authorization" not in request.headers
            and request.headers.get(CSRF_HEADER) != "XMLHttpRequest"
        ):
            return JSONResponse({"detail": "CSRF check failed: X-Requested-With header required"}, status_code=403)
        response = await call_next(request)
        for name, value in API_HEADERS.items():
            response.headers.setdefault(name, value)
        if not path.startswith(HTML_PREFIXES):
            # Ответы API — JSON и файлы; запрещаем браузеру исполнять в них что-либо
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if settings.hsts_enabled:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if path.startswith("/auth"):
            response.headers["Cache-Control"] = "no-store"  # токены не должны оседать в кэшах
        return response

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,   # явный список, не "*"
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Registration-Token"],
            expose_headers=["X-Hidden-Age-Restricted"],
            max_age=3600,
        )
    if settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
