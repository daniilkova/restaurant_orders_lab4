# Ресторан и заказы — FastAPI-платформа в Kubernetes (вариант 9)

API службы доставки еды: меню (`/dishes`), заказы (`/orders`) со статусами
«принят → готовится → доставляется → завершён», фоновая смена статусов в Celery,
кэш меню и rate limit в Redis, админ-панель и «живая» таблица заказов.

| ЛР | Что добавлено | Документация |
|----|---------------|--------------|
| 1–2 | REST API, PostgreSQL/SQLite, Redis, Celery, админка | [docs/lab2.md](docs/lab2.md) |
| 3 | Kubernetes, Helm, KEDA, CloudNativePG, Argo CD, Image Updater | этот файл, [docs/lab3-commands.md](docs/lab3-commands.md) |
| 4 | SeaweedFS (S3), Prometheus, Grafana, Loki, Alloy, алерты | раздел «ЛР4», [docs/lab4-commands.md](docs/lab4-commands.md) |
| 5 | JWT, роли, OWASP API Top 10, PSS, Network Policies, Vault, Kyverno, Falco, Trivy, cert-manager | раздел «ЛР5», [docs/lab5-commands.md](docs/lab5-commands.md) |
| 6 | Фронтенд Vue 3: вход, список заказов, маршрутизация, CORS | [frontend-app/README.md](frontend-app/README.md) |
| 7 | UI-компоненты, composables, CRUD меню, фото блюд, уведомления | [frontend-app/README.md](frontend-app/README.md#лр7-компонентная-архитектура-и-crud-меню) |
| 8 | Регистрация с подтверждением email, 2FA, httpOnly cookies, роли client/moderator/admin, профиль, возраст 18+ (Self.xyz) | [docs/lab8-accounts.md](docs/lab8-accounts.md) |

## Архитектура (ЛР3)

```
                 Ingress (restaurant.local)
                          │
                    Service api:80
                          │
          ┌──── Deployment api (2 пода, /health, /ready) ────┐
          │               │                │                 │
   PostgreSQL        Redis (кэш,      RabbitMQ (брокер)   Job db-migrate
   StatefulSet /     rate limit)      StatefulSet + PVC   (alembic upgrade)
   CloudNativePG     Deployment              │
   Cluster (3)                               ▼
                               Deployment celery-worker ◄── KEDA ScaledObject
                               (1…N подов)                  (длина очереди celery)
```

## Структура репозитория

```
app/                     код FastAPI (routers/health.py — пробы /health и /ready)
scripts/enqueue_load.py  нагрузка на очередь для проверки KEDA
docker/                  Dockerfile.api, Dockerfile.worker (multi-stage, non-root UID 10001)
docker-compose.yml       PostgreSQL + Redis + RabbitMQ + migrate + api + worker + flower
k8s/                     «чистые» манифесты (kubectl apply -f k8s/)
  keda/                  TriggerAuthentication + ScaledObject
  cnpg/                  кластер CloudNativePG, резервные копии в S3 (MinIO)
helm/fastapi-platform/   umbrella-чарт; подчарты api, worker, redis, rabbitmq в charts/
argocd/                  Application, Application с Image Updater, ApplicationSet
environments/            значения для окружений dev / staging / prod (ApplicationSet)
.github/workflows/ci.yml тесты, ruff, helm lint, kubeconform, сборка образов по тегу
```

## Быстрый старт

### Docker Compose (контрольная точка)
```bash
docker compose up --build
# Swagger: http://localhost:8000/docs   RabbitMQ: http://localhost:15672 (restaurant/restaurant)
# Flower:  http://localhost:5555 (admin/secret)
```
Миграции выполняет отдельный сервис `migrate`; `api` и `worker` стартуют после его успешного завершения.

### Kubernetes (Minikube)
```bash
minikube start --cpus=4 --memory=8g && minikube addons enable ingress
eval $(minikube docker-env)
docker build -f docker/Dockerfile.api -t restaurant-api:0.3.0 .
docker build -f docker/Dockerfile.worker -t restaurant-worker:0.3.0 .
kubectl apply -f k8s/
kubectl get pods -n fastapi-app
kubectl port-forward -n fastapi-app svc/api 8000:80
```

### Helm (весь стек одной командой)
```bash
helm install restaurant helm/fastapi-platform -n fastapi-app --create-namespace \
  -f helm/fastapi-platform/values-dev.yaml
```
Основные параметры `values.yaml`:

| Параметр | По умолчанию | Назначение |
|----------|--------------|------------|
| `database.mode` | `statefulset` | `statefulset` — свой PostgreSQL, `cnpg` — кластер CloudNativePG |
| `api.replicaCount` | 2 | реплики API |
| `api.image.repository` / `tag` | `restaurant-api` / `0.3.0` | образ API (и Job миграций) |
| `worker.autoscaled` | false | не рендерить `replicas` воркера (им управляет KEDA) |
| `keda.enabled` | false | ScaledObject + TriggerAuthentication |
| `keda.messagesPerWorker` | 10 | сообщений в очереди на один воркер |
| `ingress.enabled` / `host` | false / `restaurant.local` | Ingress |
| `secrets.existingSecret` | "" | взять секреты из готового Secret (Vault, ЛР5) |

Подробные команды для каждого пункта чек-листа — в [docs/lab3-commands.md](docs/lab3-commands.md).

## Пробы

| Компонент | liveness | readiness |
|-----------|----------|-----------|
| api | `GET /health` — процесс жив, зависимости не проверяются | `GET /ready` — `SELECT 1` в БД и `PING` в Redis с таймаутом 2 с, иначе 503 |
| celery-worker | `celery inspect ping -d celery@$HOSTNAME` (ответ именно этого воркера через RabbitMQ) | — (воркер не принимает трафик из Service) |
| postgres | `pg_isready` | `pg_isready` |
| rabbitmq | `rabbitmq-diagnostics ping` | `rabbitmq-diagnostics check_port_connectivity` |
| redis | TCP 6379 | `redis-cli ping` |

У API есть `startupProbe`: пока приложение стартует (до 60 с), liveness не выполняется.

## Автомасштабирование (KEDA)

Воркер берёт из RabbitMQ по одной задаче (`worker_prefetch_multiplier=1`) и подтверждает её после
выполнения (`task_acks_late=True`). Поэтому необработанные задачи лежат в очереди `celery`, и KEDA
видит реальную нагрузку. Правило: 1 воркер на 10 сообщений, от 1 до 10 подов (prod — до 20).

```bash
kubectl exec -n fastapi-app deploy/api -- python -m scripts.enqueue_load 200 --seconds 3
kubectl get deploy celery-worker -n fastapi-app -w
```

## CloudNativePG

`k8s/cnpg/01-cluster.yaml` — 3 экземпляра PostgreSQL 16 (primary + 2 реплики), резервные копии
и архив WAL в S3-бакет `cnpg-backups` (MinIO), ежедневная копия `ScheduledBackup`. Приложение
подключается к сервису `restaurant-db-rw`, который после failover указывает на новый primary.
В Helm включается `database.mode: cnpg`.

## GitOps

* `argocd/application.yaml` — чарт из `main` + `values-dev.yaml`, `automated: {prune, selfHeal}`.
* Sync waves: `-1` ConfigMap/Secret → `0` PostgreSQL, Redis, RabbitMQ → `1` Job миграций (Sync hook)
  → `2` API и воркеры → `3` KEDA, Ingress, резервное копирование.
* `argocd/application-prod-image-updater.yaml` — Image Updater: semver `~0.3` (только патчи),
  git write-back в `helm/fastapi-platform/values-prod.yaml`.
* `argocd/applicationset.yaml` — Git Directory Generator по `environments/*` и RollingSync
  dev → staging → prod.

## Тесты и проверки

```bash
pip install -r requirements-dev.txt
pytest -q            # 86 тестов (S3 — через moto), без Docker/Redis/PostgreSQL
ruff check app scripts
helm lint helm/fastapi-platform
```
В CI (`.github/workflows/ci.yml`) манифесты `k8s/`, `argocd/` и отрендеренный чарт для всех трёх
окружений проверяются kubeconform в строгом режиме, включая схемы CRD (KEDA, CloudNativePG, Argo CD).

## ЛР5: безопасность и защита данных

### Модель угроз (кратко)

| Угроза | Мера |
|--------|------|
| API1 BOLA — чужие заказы по ID | клиент видит/меняет только свои заказы; чужой заказ → 404 (не подтверждаем существование) |
| API2 Broken Authentication | bcrypt (12 раундов), политика паролей, 5 неудачных входов за 5 мин по логину **и** по IP → 429, одинаковый ответ для «нет логина» и «неверный пароль», refresh с ротацией и reuse detection |
| API3 Mass Assignment | все входные схемы `extra="forbid"`: `{"role": "admin"}` при регистрации → 422 |
| API4 Неограниченное потребление | пагинация ≤ 100, лимиты загрузки 5/10 МБ, rate limit заказов и входа |
| API5 Function Level Authorization | `require_admin` на изменении меню, статусов, пользователей, загрузке файлов |
| API8 Security Misconfiguration | заголовки безопасности, CSP для JSON-ответов, `Cache-Control: no-store` на `/auth`, `/metrics` по токену |
| Компрометация пода | PSS restricted, read-only rootfs, drop ALL, non-root, default-deny NetworkPolicy |
| Утечка секретов | Vault + VSO, динамические пароли БД с TTL 1 ч, токен SA не монтируется |
| Опасные манифесты | Kyverno (privileged, root, latest, hostPath — Enforce; ресурсы и ro-rootfs — Audit) |
| Атака в рантайме | Falco: оболочка, сетевые утилиты, запись в /code, чтение /proc/*/environ |
| Уязвимые зависимости, supply chain | Trivy в CI (образы, IaC, секреты), actions закреплены по SHA, Dependabot |
| Перехват трафика | TLS через cert-manager (локальный CA, в production — Let's Encrypt), редирект на HTTPS |

### Аутентификация

| Метод | Путь | Доступ |
|-------|------|--------|
| POST | `/auth/register` | все; создаёт пользователя с ролью `user` |
| POST | `/auth/token` | все; form-urlencoded (OAuth2 password flow) → access (15 мин) + refresh (7 дней) |
| POST | `/auth/refresh` | по refresh-токену; старый токен отзывается, повторное предъявление отзывает всю цепочку |
| POST | `/auth/logout` | отзыв refresh-токена |
| GET | `/auth/me` | авторизованный |
| GET/PATCH | `/users/`, `/users/{id}` | admin: роль и блокировка (старые токены пользователя сразу недействительны) |

Права: меню и фото — публичные, изменение меню — admin; заказы — авторизованные (клиент — свои);
смена статуса — admin. Первый администратор создаётся при старте из `BOOTSTRAP_ADMIN_USERNAME/PASSWORD`
(или `python -m scripts.create_admin`). Вход в `/admin` (sqladmin) — пользователи с ролью admin.

### Kubernetes

* `k8s/00-namespace.yaml` — PSS `restricted` (enforce/audit/warn); все поды: `runAsNonRoot`,
  `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, `drop: [ALL]`,
  `readOnlyRootFilesystem: true` (кроме RabbitMQ) + `emptyDir` для `/tmp`.
* `k8s/05-serviceaccounts.yaml` — `fastapi-sa`, `celery-sa`, `infra-sa`, без автомонтирования токена.
* `k8s/network-policies/` — 14 политик (таблица в `k8s/network-policies/README.md`).
* `k8s/vault/` + `scripts/vault-setup.sh` — VaultStaticSecret (`app-secret`) и VaultDynamicSecret
  (`app-db-credentials`, пользователь PostgreSQL с TTL 1 ч).
* `security/kyverno/`, `security/falco/`, `security/cert-manager/`, `argocd/security-apps.yaml`.
* `scripts/validate_manifests.py --pss` — проверка всех подов на соответствие PSS restricted (в CI).

## ЛР4: наблюдаемость и S3-хранилище

### S3 (SeaweedFS)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/files/upload` | загрузить файл (до 10 МБ); ключ `uploads/<uuid>.<ext>` генерирует сервер |
| GET | `/files/download/{object_name}` | скачать (`Content-Disposition: attachment`, `nosniff`) |
| PUT | `/dishes/{id}/image` | фото блюда: только JPEG/PNG/WebP по сигнатуре файла, до 5 МБ; старое фото удаляется |
| GET | `/dishes/{id}/image` | фото блюда (`Cache-Control: max-age=86400`) |

В ответах меню появилось поле `image_url` (ключ S3 наружу не отдаётся). Миграция
`0002_dish_image` добавляет колонку `dishes.image_key`. Клиент — `app/s3_client.py` (boto3,
path-style адресация, вызовы в пуле потоков). В Kubernetes: `k8s/seaweedfs/` — кластер `Seaweed`,
учётка `S3Identity` + `S3Credentials` (Secret `s3-credentials`), бакет `Bucket fastapi-files`
с квотой 5 ГиБ и `reclaimPolicy: Retain`.

### Метрики

* HTTP: `http_requests_total{handler,method,status}`, `http_request_duration_seconds_bucket` —
  prometheus-fastapi-instrumentator, коды ответа **не** группируются (`status="503"`, а не `5xx`).
* Бизнес: `restaurant_orders_created_total`, `restaurant_order_total_rub` (гистограмма суммы
  заказа), `restaurant_order_status_changes_total{status,source}`, `restaurant_files_uploaded_total{kind}`.
* Celery — метрики Flower (`flower_worker_online`, `flower_events_total`, `flower_task_runtime_seconds`).
* Очередь — плагин `rabbitmq_prometheus`, `/metrics/detailed?family=queue_coarse_metrics`
  → `rabbitmq_detailed_queue_messages_ready{queue="celery"}`.

ServiceMonitor'ы: `monitoring/servicemonitors.yaml`; алерты: `monitoring/alerts.yaml`
(HighErrorRate, HighLatency, ApiDown, CeleryQueueBacklog, NoCeleryWorkers, OrdersStuckAccepted);
дашборды: `monitoring/grafana-dashboards/*.json` (ConfigMap для sidecar Grafana —
`monitoring/grafana-dashboards-configmap.yaml`).

### Логи

API и воркер пишут JSON-строки (`app/logging_config.py`): `ts`, `level`, `logger`, `message` и
поля запроса (`method`, `path`, `status`, `duration_ms`). Alloy (DaemonSet) собирает логи всех подов
и добавляет метки `namespace`, `pod`, `container`, `app`, а для `fastapi-app` — `level`.

### Helm

`monitoring.enabled` — ServiceMonitor'ы, PrometheusRule и ConfigMap с дашбордами;
`seaweedfs.enabled` — кластер SeaweedFS, учётка и бакет. В `values-dev.yaml` и `values-prod.yaml`
оба включены, весь стек приложения ставится одной командой `helm upgrade --install`.
Сами kube-prometheus-stack, Loki и Alloy — отдельные релизы в namespace `monitoring`
(общая инфраструктура кластера, у них свой жизненный цикл).

### Ответы на вопросы ЛР4

**1. SeaweedFS и MinIO.** Оба дают S3 API. SeaweedFS — Apache 2.0, хранит мелкие файлы в больших
томах (O(1) доступ к файлу, мало метаданных), имеет Filer с POSIX/FUSE/WebDAV, оператор с CRD для
бакетов и учёток. MinIO (AGPL) в 2025 году урезал community-версию: убрал из открытой сборки
административную веб-консоль и перестал публиковать готовые сборки, развивая коммерческий продукт.
Это риск vendor lock-in, поэтому команды уходят к полностью открытым альтернативам.

**2. ServiceMonitor.** CRD Prometheus Operator: селектор Service по меткам + порт и путь метрик.
Оператор превращает ServiceMonitor'ы в `scrape_configs`, а Prometheus через Kubernetes API следит за
Endpoints этих сервисов и опрашивает каждый под (цель становится UP после успешного scrape).

**3. Почему Loki не индексирует текст.** Индексируются только метки потока (namespace, app, level),
сами строки сжимаются чанками в объектное хранилище. Индекс в сотни раз меньше, запись дешевле,
хранение — в S3. Поиск по тексту — перебор чанков выбранных потоков (`|=`, `| json`), что приемлемо при
узком отборе по меткам.

**4. Как Alloy собирает логи.** Alloy — DaemonSet: `discovery.kubernetes` находит поды,
`discovery.relabel` превращает их метаданные в метки, `loki.source.kubernetes` читает логи
контейнеров через Kubernetes API, `loki.process` разбирает JSON и выделяет `level`, `loki.write`
отправляет в Loki.

**5. Три столпа наблюдаемости.** Метрики — числа во времени (RPS, P95, длина очереди);
логи — события с контекстом (`POST /orders 429`, трассировка исключения); трейсы — путь одного запроса
через сервисы (API → PostgreSQL → RabbitMQ → воркер) со временем каждого шага (OpenTelemetry + Tempo).

**6. Алерт на 5xx.** `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05`
с `for: 5m`. `sum` обязателен: без него деление идёт по каждой серии отдельно. Коды нельзя
группировать в `5xx`, иначе регулярное выражение ничего не найдёт.

**7. Отказоустойчивость SeaweedFS.** Репликация томов (`defaultReplication`, например `001` —
копия на другом сервере той же стойки, `010` — в другой стойке), несколько Master в кворуме Raft,
несколько Filer с общим хранилищем метаданных, Erasure Coding для «холодных» томов. В учебном
Minikube одна нода, поэтому `000`.

## Ответы на вопросы ЛР3

**1. Deployment и StatefulSet.** Deployment управляет взаимозаменяемыми подами со случайными
именами и общим (или никаким) хранилищем — подходит для API и воркеров. StatefulSet даёт подам
стабильные имена (`postgres-0`), порядок запуска и собственный PVC на каждый под из
`volumeClaimTemplates`, который переживает пересоздание пода. Поэтому PostgreSQL и RabbitMQ —
StatefulSet, а API и воркеры — Deployment.

**2. PVC для PostgreSQL, но не для Redis.** В PostgreSQL лежат заказы — их потеря недопустима.
Redis в проекте хранит только кэш меню (восстановится из БД за один запрос) и счётчики rate limit
(сбросятся через минуту), поэтому персистентность ему не нужна, а `--save ""` ещё и экономит диск.

**3. Падение liveness и readiness.** Если падает liveness, kubelet перезапускает контейнер
(рестарт пода). Если падает readiness, под остаётся работать, но удаляется из endpoints Service и
не получает трафик, пока проба снова не станет успешной. Поэтому зависимости (БД, Redis) проверяет
только `/ready`: недоступная БД не должна вызывать перезапуск всех подов API.

**4. `serviceName` в StatefulSet.** Это имя headless-сервиса, который создаёт DNS-записи для
каждого пода: `postgres-0.postgres-headless.fastapi-app.svc.cluster.local`. Так реплики и клиенты
обращаются к конкретному экземпляру, а не к случайному.

**5. Как Secret попадает в под.** Через переменные окружения (`envFrom.secretRef`,
`secretKeyRef`) или как файлы в смонтированном томе. Ограничения: значения лишь закодированы в
base64, по умолчанию хранятся в etcd без шифрования, читаются любым, у кого есть право `get secrets`
в namespace, переменные окружения не обновляются без рестарта пода, размер — до 1 МиБ.

**6. Отдельная liveness-проба воркера.** У воркера нет HTTP-сервера, а «процесс жив» не значит
«воркер работает»: он может потерять соединение с брокером или зависнуть. `celery inspect ping`
проходит через RabbitMQ и требует ответа именно от этого воркера, то есть проверяет путь
«брокер → воркер».

**7. Зачем Helm.** Один набор шаблонов вместо копий YAML для каждого окружения, параметры в
`values.yaml`, установка всего стека одной командой, версии релизов с `helm rollback`, зависимости
(umbrella-чарт), хуки (миграции), `helm lint`.

**8. Как KEDA передаёт метрику.** Оператор KEDA по `pollingInterval` опрашивает RabbitMQ (AMQP или
HTTP API) с учётными данными из TriggerAuthentication и создаёт HPA `keda-hpa-<имя>`. Метрика
отдаётся через KEDA metrics-apiserver по API `external.metrics.k8s.io`; HPA считает
`желаемые реплики = длина очереди / value`. Переход 0 ↔ 1 KEDA выполняет сам.

**9. `minReplicaCount: 0`.** При пустой очереди KEDA через `cooldownPeriod` уменьшит воркеры до
нуля (экономия ресурсов). Первая задача после простоя будет ждать, пока KEDA заметит сообщение и
под стартует (десятки секунд). Для смены статусов заказов это допустимо, для срочных задач — нет.

**10. Масштабирование Celery через HPA.** Стандартный HPA — по CPU/памяти, но для воркеров это
плохая метрика: длинная очередь может стоять при низком CPU. Правильно масштабировать по внешней
метрике — длине очереди (KEDA RabbitMQ scaler или prometheus-adapter с метрикой из rabbitmq-exporter).

### Контрольные вопросы для защиты

1. **Почему PostgreSQL — StatefulSet / Cluster.** Нужны стабильная идентичность и свой том. В
   production выбран CloudNativePG: оператор управляет репликацией, failover и резервными копиями.
2. **Новый образ в Git.** Image Updater (или CI) меняет тег в `values-*.yaml` → Argo CD видит
   расхождение → применяет новый Deployment → RollingUpdate (`maxUnavailable: 0`, `maxSurge: 1`):
   новый под стартует, проходит readiness, только потом гасится старый.
3. **TriggerAuthentication.** Пароль RabbitMQ нужен самому оператору KEDA, а не приложению.
   TriggerAuthentication ссылается на Secret, чтобы не писать пароль в ScaledObject и
   переиспользовать учётные данные в нескольких ScaledObject.
4. **Дрейф в Argo CD.** Argo CD регулярно (по умолчанию раз в 3 минуты и по webhook) рендерит
   чарт из Git и сравнивает с живыми объектами. При `selfHeal: true` ручные изменения откатываются
   к состоянию из Git.
5. **Secret не секретный.** Только base64, etcd без шифрования, широкий доступ через RBAC.
   Исправляется шифрованием etcd (EncryptionConfiguration), строгим RBAC и внешними хранилищами:
   Vault + Vault Secrets Operator, Sealed Secrets, External Secrets (ЛР5).
6. **Sync waves** задают порядок применения ресурсов: Argo CD применяет волну и ждёт, пока
   ресурсы станут Healthy, прежде чем перейти к следующей (секреты → БД → миграции → API → KEDA).
