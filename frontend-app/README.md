# Фронтенд «Ресторан «Пряность»» (Vue 3 + Vite)

SPA для API заказов: вход по JWT, список заказов из БД (клиент видит свои, персонал — все).

## Запуск

1. Бэкенд (из корня репозитория):
   ```bash
   pip install -r requirements.txt
   alembic upgrade head
   python -m scripts.seed_demo        # admin / Admin12345, ivan / Pizza2026, maria / Sushi2026
   uvicorn app.main:app --reload      # http://localhost:8000
   ```
   Без Redis и RabbitMQ API тоже работает (кэш и лимиты отключаются). Чтобы создание заказа не ждало
   брокер, задайте `CELERY_BROKER_URL=memory://`. CORS разрешает `http://localhost:5173`
   (переменная `CORS_ORIGINS`, список через запятую).
2. Фронтенд:
   ```bash
   cd frontend-app
   cp .env.example .env.local         # VITE_API_BASE_URL=http://localhost:8000
   npm install
   npm run dev                        # http://localhost:5173
   ```

| Переменная | Где | Назначение |
|------------|-----|-----------|
| `VITE_API_BASE_URL` | `frontend-app/.env.local` | адрес FastAPI (по умолчанию `http://localhost:8000`) |
| `CORS_ORIGINS` | окружение бэкенда | разрешённые origin'ы фронтенда |

## Команды

| Команда | Что делает |
|---------|-----------|
| `npm run dev` | dev-сервер Vite |
| `npm run test:unit` | тесты Vitest |
| `npm run lint` | oxlint + ESLint |
| `npm run build` | production-сборка в `dist/` |

## Структура (ЛР6)

```
src/
├── api/        client.js (Axios + интерсепторы JWT и 401) · orders.js · errors.js
├── stores/     auth.js (Pinia: token, user, isAuthenticated, isAdmin, login, logout, fetchMe)
├── router/     index.js (/, /login, 404; beforeEach guard; safeRedirect)
├── views/      HomeView (список заказов) · LoginView · NotFoundView
├── utils/      format.js (деньги, даты, статусы)
└── App.vue     шапка и навигация по isAuthenticated
```

## Сквозной сценарий ЛР6 (скриншоты в `docs/screenshots/lab6/`)

| Шаг | Результат |
|-----|-----------|
| Открыть `/` без входа | редирект на `/login?redirect=/` |
| Неверный пароль | «Неверный логин или пароль», пароль очищен |
| Вход `ivan` | список «Мои заказы» из БД (3 заказа) |
| Изменить статус через API (Swagger) и нажать «Обновить» | новый статус на экране |
| «Выйти» | токен удалён, экран входа |
| Вход `admin` | «Все заказы» (5), метка «персонал» |
| `/no-such-page` | страница 404 |
| Бэкенд остановлен | «Сервер недоступен…» и «Повторить» |
