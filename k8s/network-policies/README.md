# Network Policies (ЛР5)

Модель «запрещено всё, что не разрешено»: `00-default-deny.yaml` закрывает входящий и исходящий
трафик всех подов namespace, остальные файлы открывают только нужные соединения.

> NetworkPolicy применяет сетевой плагин. Стандартный CNI Minikube политики **не выполняет** —
> кластер нужно запускать с Calico: `minikube start --cni=calico`.

| Под | Входящий | Исходящий |
|-----|----------|-----------|
| api | ingress-nginx, Prometheus → 8000 | PostgreSQL 5432, Redis 6379, RabbitMQ 5672, SeaweedFS S3 8333 |
| celery-worker | — | PostgreSQL 5432, RabbitMQ 5672 |
| flower | Prometheus → 5555 | RabbitMQ 5672 |
| db-migrate | — | PostgreSQL 5432 |
| postgres / cnpg | api, worker, migrate → 5432; реплики между собой; оператор; метрики 9187 | реплики, MinIO 9000 (бэкапы), Kubernetes API |
| redis | api → 6379 | — |
| rabbitmq | api, worker, flower → 5672; KEDA; Prometheus → 15692 | — |
| seaweedfs | api → 8333; компоненты между собой; оператор | компоненты между собой |
| все поды | — | CoreDNS 53/UDP+TCP |

Проверка:
```bash
kubectl apply -f k8s/network-policies/
kubectl exec -n fastapi-app deploy/api -- python -c "import socket; socket.create_connection(('redis', 6379), 3); print('redis OK')"
kubectl exec -n fastapi-app deploy/celery-worker -- python -c "import socket; socket.create_connection(('redis', 6379), 3)"   # timeout: воркеру Redis не нужен
kubectl exec -n fastapi-app deploy/api -- python -c "import urllib.request; urllib.request.urlopen('https://example.com', timeout=3)"  # timeout: выход в интернет закрыт
```
