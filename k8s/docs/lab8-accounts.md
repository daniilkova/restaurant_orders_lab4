# ЛР8 — аккаунты пользователей и RBAC

## Роли

| Роль | Кто | Права |
|------|-----|-------|
| `client` | клиент (по умолчанию при регистрации) | меню, свои заказы, свой профиль |
| `moderator` | менеджер ресторана | + создание/изменение/удаление блюд и фото, все заказы, смена статусов |
| `admin` | администратор | + управление пользователями и ролями (`/users`) |

На фронтенде кнопки изменения меню скрыты для `client`, но проверка — на бэкенде:
`require_staff` / `require_admin`; прямой `POST /dishes/` с сессией клиента возвращает 403.

## Вход и сессии

* `POST /auth/token` — пароль; если включена 2FA, ответ `{"2fa_required": true, "temp_token": ...}`
  (JWT на 5 минут, годится только для `/auth/2fa/verify`), иначе — cookies.
* Cookies: `access_token` (httpOnly, SameSite=Strict, Path=/, 15 мин) и `refresh_token`
  (httpOnly, SameSite=Strict, **Path=/auth/refresh**, 7 дней). `Secure` включается `COOKIE_SECURE=true` за HTTPS.
* `POST /auth/refresh` — ротация: старый refresh отзывается, повторное предъявление отзывает всю цепочку.
* CSRF: кроме SameSite, изменяющие запросы с cookie обязаны нести `X-Requested-With: XMLHttpRequest`
  (чужой сайт не добавит его без CORS-preflight).
* `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `POST /auth/sessions/revoke-others`.
* `POST /auth/change-password` — нужен текущий пароль; все остальные сессии отзываются.

## 2FA (TOTP, RFC 6238)
`POST /auth/2fa/enable` → секрет + `otpauth://` + QR (SVG) → `POST /auth/2fa/confirm {code}` включает 2FA →
`POST /auth/2fa/disable {password, code}`. Неудачные коды ограничены так же, как пароли (5 за 5 минут).

## Профиль
`PATCH /users/me` (отображаемое имя), `PATCH /users/me/username` (раз в 182 дня, уникальность → 409),
`PUT /users/me/avatar` (JPEG/PNG/WebP по сигнатуре, до 2 МБ, SVG отклоняется), `GET /users/{id}/avatar`.

## Подтверждение email
При регистрации генерируется токен (32 байта), в БД — только его SHA-256 и срок (24 ч). Письмо
отправляет Celery-задача `accounts.send_verification_email` (SMTP; без `SMTP_HOST` — лог и `MAIL_OUTBOX_DIR`).
`GET /auth/verify-email?token=` — одноразово. Вход до подтверждения → 403 `email_not_verified`.

## Возрастная верификация (Self.xyz)
* Блюда с `min_age=18` (вино, пиво) не отдаются в `GET /dishes/` без верификации (заголовок
  `X-Hidden-Age-Restricted` — сколько скрыто); `GET /dishes/{id}` и заказ такого блюда → 403.
* `POST /auth/age-session` → `verificationUrl` (hosted-сессия Self по `SELF_API_BASE`/`SELF_API_KEY`;
  для локальной разработки — учебная заглушка при `AGE_VERIFICATION_MOCK=true`).
* `POST /auth/verify-age` — запрос, подписанный агентом Self; проверяет `selfxyz-agent-sdk`
  (`AgentAuth`, верификатор: `network("testnet")`, `require_age(18)`, `require_self_provider()`,
  `sybil_limit(1)`), возраст — `agent.credentials.older_than`.
* `POST /auth/self-webhook` — результат hosted-сессии (подпись HMAC `SELF_WEBHOOK_SECRET`).
* `AGE_VERIFICATION_ON_REGISTER=true`: регистрация возвращает `requires_age_verification: true` и
  `registration_token`; письмо уходит только после верификации (`POST /auth/complete-registration`),
  вход до этого → 403 `age_verification_required`.

## Какие данные мы храним

| Поле | Зачем | Срок хранения |
|------|-------|---------------|
| `username` | вход и отображение | пока существует аккаунт |
| `email` | подтверждение и восстановление доступа | пока существует аккаунт |
| `hashed_password` | проверка пароля (bcrypt, 12 раундов; сам пароль не хранится) | пока существует аккаунт |
| `role`, `is_active` | права доступа и блокировка | пока существует аккаунт |
| `token_version` | мгновенный отзыв выданных токенов | пока существует аккаунт |
| `totp_secret`, `totp_enabled` | проверка кодов 2FA | до отключения 2FA |
| `display_name`, `avatar_key` | профиль (по желанию пользователя) | до удаления пользователем |
| `username_changed_at` | кулдаун смены логина | пока существует аккаунт |
| `is_email_verified`, `email_verification_token` (SHA-256), `email_verification_expires_at` | подтверждение email | токен — до подтверждения или 24 ч |
| `is_age_verified`, `age_verified_at` | доступ к позициям 18+; **дата рождения и данные документа не хранятся** | пока существует аккаунт |
| `refresh_tokens`: `jti`, `family_id`, `user_agent`, `ip`, даты | список сессий, отзыв, обнаружение кражи | до истечения (7 дней), затем можно удалять |
| заказы: состав, цены, статус, `user_id` | выполнение заказа, история клиента | по требованиям учёта |
