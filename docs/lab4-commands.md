# ЛР4 — команды для демонстрации и скриншотов

## SeaweedFS
```bash
helm repo add seaweedfs-operator https://seaweedfs.github.io/seaweedfs-operator/
helm install seaweedfs-operator seaweedfs-operator/seaweedfs-operator -n seaweedfs-system --create-namespace
kubectl apply -f k8s/seaweedfs/
kubectl get pods -n fastapi-app | grep seaweedfs          # СКРИНШОТ: master, volume, filer Running
kubectl get svc -n fastapi-app | grep 8333                # S3-шлюз на 8333
kubectl get bucket,s3identity,s3credentials -n fastapi-app
kubectl rollout restart deploy/api -n fastapi-app         # подхватить s3-config и s3-credentials
```

## Проверка S3 через API
```bash
kubectl port-forward -n fastapi-app svc/api 8000:80
curl -F "file=@menu.pdf" http://localhost:8000/files/upload
curl -OJ http://localhost:8000/files/download/uploads/<object_name>
curl -X PUT -F "file=@pizza.jpg" http://localhost:8000/dishes/1/image
curl -o - http://localhost:8000/dishes/1/image | file -          # JPEG image data
```

## Prometheus + Grafana
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts && helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/prometheus-values.yaml
kubectl apply -f monitoring/servicemonitors.yaml -f monitoring/alerts.yaml -f monitoring/grafana-dashboards-configmap.yaml
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
#   http://localhost:9090/targets -> fastapi-monitor, flower-monitor, rabbitmq-monitor UP   (СКРИНШОТ)
#   http://localhost:9090/alerts  -> группы restaurant-api, restaurant-celery               (СКРИНШОТ)
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80   # admin / admin
#   Dashboards -> Restaurant -> «Ресторан — FastAPI» и «Ресторан — Celery и RabbitMQ»       (СКРИНШОТЫ)
```
Нагрузка для графиков: `for i in $(seq 1 300); do curl -s localhost:8000/dishes/ >/dev/null; curl -s localhost:8000/orders/999 >/dev/null; done`

## Loki + Alloy
```bash
helm install loki grafana/loki -n monitoring -f monitoring/loki-values.yaml
helm install alloy grafana/alloy -n monitoring -f monitoring/alloy-values.yaml
kubectl get pods -n monitoring | grep -E "loki|alloy"     # alloy — по поду на узел (DaemonSet)
```
Grafana → Explore → Loki (СКРИНШОТЫ):
```
{namespace="fastapi-app", app="api"} | json | status >= 400
{namespace="fastapi-app", level="ERROR"}
{namespace="fastapi-app", app="celery-worker"} |= "доставляется"
sum by (status) (count_over_time({namespace="fastapi-app", app="api"} | json | __error__="" [5m]))
```

## Алерты
```bash
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager 9093:9093
kubectl scale deploy/celery-worker -n fastapi-app --replicas=0   # через 5 мин NoCeleryWorkers -> Firing
```

## Весь стек через Helm
```bash
helm upgrade --install restaurant helm/fastapi-platform -n fastapi-app -f helm/fastapi-platform/values-dev.yaml
```

## Локально (docker compose)
`docker compose up --build` → API :8000, SeaweedFS S3 :8333, Prometheus :9090, Grafana :3000 (admin/admin).
