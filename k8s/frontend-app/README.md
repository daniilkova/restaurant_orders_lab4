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

## ЛР7: компонентная архитектура и CRUD меню

Главный экран — меню ресторана (сетка карточек блюд). Персонал (роль admin) создаёт, редактирует и
удаляет блюда и загружает их фото (S3, ЛР4); клиент видит меню и свои заказы (`/orders`).

```
src/
├── components/ui/   BaseButton · BaseInput · BaseModal · BaseCard · ToastNotification · ToastContainer
├── components/      DishCard (карточка-ссылка <li>) · DishForm (одна форма для создания и правки)
├── composables/     useResource (CRUD + isLoading/error/notFound) · useForm (валидация, 422)
│                    useToast (глобальные уведомления) · useDebouncedRef (поиск)
├── api/             dishes.js (toDishPayload, загрузка фото) · errors.js (+ разбор 422 Pydantic v2)
├── views/           HomeView (меню) · DishDetailView · DishCreateView · DishEditView · OrdersView
└── test-utils.js    монтирование экрана с роутером и Pinia
```

| Компонент / composable | Зачем |
|------------------------|-------|
| `BaseButton` | варианты primary/secondary/danger/ghost, размеры, `loading` (спиннер, `aria-busy`), атрибуты на `<button>` |
| `BaseInput` | `defineModel` (+ `.number`), подпись через `for`, ошибка с `aria-invalid` и `aria-describedby`, `textarea` |
| `BaseModal` | `Teleport` в `body`, Escape и клик по фону, ловушка и возврат фокуса, `persistent` во время запроса |
| `BaseCard` | карточка с тегом `as` (`li` внутри `ul`), режим `interactive` |
| `useResource` | один раз описанные загрузка, ошибки, 404, защита от гонки запросов, оптимистичное удаление |
| `useForm` | копия начальных значений, валидация (в том числе при вводе), раскладка 422 по полям |
| `useToast` | общий для приложения список уведомлений (не больше 5, ошибки держатся дольше) |

Маршруты: `/dishes/create` (раньше `/dishes/:id`), `/dishes/:id(\d+)`, `/dishes/:id(\d+)/edit`,
все с `requiresAuth`; создание и правка — ещё и `requiresAdmin`. Права проверяет бэкенд (403),
интерфейс лишь не показывает недоступные кнопки.

Тесты: `npm run test:unit` — 79 тестов в 11 файлах. Скриншоты сквозного CRUD-сценария —
`docs/screenshots/lab7/`.

## ЛР8: аккаунты и RBAC

Токены — только в httpOnly cookies (`withCredentials: true`), `localStorage` для них не используется.
Клиент сам продлевает сессию: на 401 вызывает `/auth/refresh` (один запрос на все параллельные) и
повторяет исходный запрос.

| Экран | Что делает |
|-------|-----------|
| `/` гостю — `LandingView` | кнопки «Войти» и «Зарегистрироваться» |
| `RegisterView` | валидация, 409 под полем (логин/email заняты), экран «Проверьте почту» |
| `LoginView` | пароль → (если 2FA) второй шаг с кодом; подсказки «email не подтверждён» |
| `VerifyEmailView` | подтверждение по ссылке, счётчик ожидания, обратный отсчёт до входа, повторная отправка |
| `VerifyAgeView` | старт верификации Self, обработка `?age=success|failure` и `registration=true` |
| `AccountView` | шапка (аватар, имя), вкладки «Профиль», «Настройки», «Безопасность» |
| «Безопасность» | карточки: 2FA (QR), смена пароля, активные сессии, возрастная верификация |

В шапке — аватар и имя со ссылкой на `/account`. Кнопки изменения меню видны модератору и
администратору (`auth.isStaff`). Тесты: 101 (Vitest). Скриншоты — `docs/screenshots/lab8/`.
