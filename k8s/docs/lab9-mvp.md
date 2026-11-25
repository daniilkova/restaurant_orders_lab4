# ЛР9 — завершение MVP

## Доступность (WCAG 2.1 AA)

Аудит — axe-core (те же правила, что в axe DevTools: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`,
`best-practice`) на 10 экранах. До исправлений: `html-has-lang` (пустой `lang`), кнопка Vue DevTools
без доступного имени (`aria-prohibited-attr`) и содержимое вне ориентиров (`region`). После — 0 нарушений.

| Требование | Реализация |
|------------|-----------|
| Skip link | «Перейти к содержимому» → `<main id="main" tabindex="-1">` (`App.vue`) |
| Фокус при переходах | после навигации фокус на `<h1>` новой страницы, заголовок объявляется в `aria-live` |
| Модальные окна | ловушка фокуса, Escape, возврат фокуса (`BaseModal`) |
| Вкладки аккаунта | `tablist/tab/tabpanel`, `aria-selected`, roving `tabindex`, ←/→/Home/End |
| Поля форм | `<label for>`, ошибки через `aria-invalid` + `aria-describedby`, `role="alert"` |
| Уведомления | `role="status"` + `aria-live="polite"`, ошибки — `role="alert"`/`assertive` |
| Мобильное меню | кнопка с `aria-expanded`/`aria-controls`, цели касания ≥ 44 px |
| Анимации | `prefers-reduced-motion` |

## Адаптивность (mobile-first)

Базовые стили — для 375 px, расширение медиазапросами `min-width`: **sm 640**, **md 768**, **lg 1024**.
Сетки — `repeat(auto-fill, minmax(min(100%, 230px), 1fr))`. Проверка Playwright: на 375, 768 и
1280 px `scrollWidth` равен ширине окна на всех экранах (гость и вошедший пользователь).

## Vite proxy и CORS

`VITE_API_BASE_URL=/api`, `server.proxy['/api']` → `http://localhost:8000` с удалением префикса и
`cookiePathRewrite` (refresh-cookie выдаётся с `Path=/auth/refresh`, а браузер видит `/api/auth/refresh`).
Фронтенд и API на одном origin — CORS в разработке не нужен. На бэкенде CORS остаётся строгим:
явный список `CORS_ORIGINS`, `allow_credentials=True`, `max_age=3600`.

## Cloudflare Turnstile

* Фронтенд: `TurnstileWidget.vue` (ключ `VITE_TURNSTILE_SITE_KEY`) на формах входа и регистрации,
  токен — в заголовке `X-Turnstile-Token`, после каждой попытки виджет сбрасывается (токен одноразовый).
* Бэкенд: `app/captcha.py` — `siteverify` с `secret`, `response` и `remoteip`; без
  `TURNSTILE_SECRET_KEY` проверка выключена; при недоступности Cloudflare — отказ (fail-closed).
* Тестовые ключи: site `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`.

## Cloudflare (пример)

Как это работало бы при реальном деплое на домене `app.example.com`:

1. DNS-запись `app.example.com` с включённым проксированием (оранжевое облако): браузер соединяется
   с Cloudflare, Cloudflare — с нашим сервером (ingress-nginx).
2. **SSL/TLS → Full (strict)**: шифрование и браузер → Cloudflare, и Cloudflare → сервер, причём
   сертификат сервера проверяется (Let's Encrypt через cert-manager или Cloudflare Origin CA).
   Режим «Flexible» нельзя: участок до сервера идёт по HTTP, а приложение считает соединение
   защищённым (Secure-cookies, HSTS).
3. **Реальный IP клиента.** За Cloudflare `request.client.host` — адрес узла Cloudflare, поэтому
   rate limit и журнал видели бы «одного» клиента. Реальный адрес — в `CF-Connecting-IP`:
   `CLIENT_IP_HEADER=CF-Connecting-IP`. Доверять заголовку можно, только если на сервер нельзя попасть
   в обход Cloudflare (firewall пропускает лишь диапазоны IP Cloudflare), иначе клиент подставит любой адрес.
4. WAF и rate limiting Cloudflare — первый рубеж, лимиты ingress-nginx и FastAPI — второй.

## Nginx (альтернатива Cloudflare, локально)

`nginx/restaurant.conf` + `nginx/snippets/restaurant-proxy.conf`: статика из `dist/`, SPA-fallback
`try_files $uri $uri/ /index.html`, `/api` → `rewrite ^/api/(.*)$ /$1 break` → FastAPI на 127.0.0.1:8000,
`X-Real-IP`/`X-Forwarded-For` перезаписываются, `limit_req_zone $binary_remote_addr`: `auth_limit` 5r/m
для `/api/auth/`, `api_limit` 100r/m для `/api/`, `proxy_cookie_path`, пример HTTPS с самоподписанным сертификатом.

## Kubernetes

| Файл | Что |
|------|-----|
| `frontend-app/Dockerfile`, `frontend-app/nginx.conf` | multi-stage: `node:22-alpine` → `nginx-unprivileged` (UID 101, порт 8080), CSP, SPA-fallback |
| `k8s/frontend/frontend-deployment.yaml`, `frontend-service.yaml` | 2 реплики, PSS restricted, read-only rootfs |
| `k8s/30-ingress.yaml` | `app.example.com`: `/` → frontend-service, `/api(/\|$)(.*)` → api (`rewrite-target: /$2`), 100 rpm |
| `k8s/31-ingress-auth.yaml` | `/api/auth` — отдельный Ingress с `limit-rpm: 5` (лимиты в Ingress общие на все пути) |
| `k8s/frontend/networkpolicy-frontend.yaml` | к фронтенду — только ingress-nginx |
| `k8s/frontend/canary/` | canary: Deployment `track: canary`, Service, Ingress `canary-weight: 10` + `X-Canary: always` |
| `helm/frontend-chart/` | чарт фронтенда (`_helpers.tpl`: имена, метки, общий podSpec), dependency umbrella-чарта |

```bash
eval $(minikube docker-env)
docker build -t restaurant-frontend:0.9.0 frontend-app/
kubectl apply -f k8s/frontend/ -f k8s/30-ingress.yaml -f k8s/31-ingress-auth.yaml
echo "$(minikube ip) app.example.com" | sudo tee -a /etc/hosts
curl -k https://app.example.com/account            # 200 (SPA-fallback)
for i in $(seq 1 8); do curl -k -s -o /dev/null -w '%{http_code} ' -X POST https://app.example.com/api/auth/token -d 'username=x&password=y'; done
#   401 401 401 401 401 503 503 503  — лимит /api/auth
kubectl logs -n fastapi-app deploy/api | grep '"client"'   # реальный IP клиента (X-Real-IP)

# Helm
helm install frontend helm/frontend-chart -n fastapi-app
helm dependency update helm/fastapi-platform
helm upgrade --install restaurant helm/fastapi-platform -n fastapi-app -f helm/fastapi-platform/values-dev.yaml

# Canary
docker build -t restaurant-frontend:0.9.1 frontend-app/
kubectl apply -f k8s/frontend/canary/
for i in $(seq 1 100); do curl -k -s https://app.example.com/ | grep -o 'index-[A-Za-z0-9_-]*\.js'; done | sort | uniq -c
curl -k -s -H 'X-Canary: always' https://app.example.com/ | grep -o 'index-[^"]*\.js'
kubectl annotate ingress restaurant-frontend-canary -n fastapi-app nginx.ingress.kubernetes.io/canary-weight=50 --overwrite
kubectl annotate ingress restaurant-frontend-canary -n fastapi-app nginx.ingress.kubernetes.io/canary-weight=100 --overwrite
# откат: kubectl delete -f k8s/frontend/canary/   (100% снова на stable)
```
