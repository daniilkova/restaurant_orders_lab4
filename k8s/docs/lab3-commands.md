# ЛР3 — команды для демонстрации и скриншотов

Все команды выполняются из корня репозитория. Для Windows используйте PowerShell или Git Bash.

## 1. Minikube и образы
```bash
minikube start --cpus=4 --memory=8g
minikube addons enable ingress
minikube addons enable metrics-server
eval $(minikube docker-env)          # PowerShell: & minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -f docker/Dockerfile.api    -t restaurant-api:0.3.0 .
docker build -f docker/Dockerfile.worker -t restaurant-worker:0.3.0 .
```

## 2. Чистые манифесты
```bash
kubectl apply -f k8s/
kubectl get pods -n fastapi-app -w                       # СКРИНШОТ: все поды Running, db-migrate Completed
kubectl port-forward -n fastapi-app svc/api 8000:80      # http://localhost:8000/docs  (СКРИНШОТ Swagger)
kubectl logs -n fastapi-app deploy/celery-worker -f      # СКРИНШОТ: «Заказ 1 -> доставляется»
```

## 3. Отказоустойчивость
```bash
kubectl delete pod -n fastapi-app -l app=api --wait=false && kubectl get pods -n fastapi-app -l app=api -w
kubectl delete pod -n fastapi-app postgres-0 && kubectl get pods -n fastapi-app -w
curl http://localhost:8000/orders/1                      # данные на месте (PVC)
kubectl get endpoints api -n fastapi-app                 # во время рестарта БД поды API выпадают из endpoints (/ready = 503)
```

## 4. Helm
```bash
kubectl delete namespace fastapi-app                     # убрать «ручную» установку
helm lint helm/fastapi-platform
helm install restaurant helm/fastapi-platform -n fastapi-app --create-namespace -f helm/fastapi-platform/values-dev.yaml
helm list -n fastapi-app                                 # СКРИНШОТ
helm upgrade restaurant helm/fastapi-platform -n fastapi-app -f helm/fastapi-platform/values-dev.yaml --set api.replicaCount=2
helm history restaurant -n fastapi-app && helm rollback restaurant 1 -n fastapi-app
```

## 5. KEDA
```bash
helm repo add kedacore https://kedacore.github.io/charts && helm repo update
helm install keda kedacore/keda -n keda --create-namespace
helm upgrade restaurant helm/fastapi-platform -n fastapi-app -f helm/fastapi-platform/values-dev.yaml \
  --set keda.enabled=true --set worker.autoscaled=true
kubectl get scaledobject,hpa -n fastapi-app
kubectl exec -n fastapi-app deploy/api -- python -m scripts.enqueue_load 200 --seconds 3
kubectl get deploy celery-worker -n fastapi-app -w        # СКРИНШОТ: 1 -> 10 реплик, затем обратно
```

## 6. CloudNativePG
```bash
kubectl apply --server-side -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.25/releases/cnpg-1.25.1.yaml
kubectl apply -f k8s/cnpg/00-minio-backup-store.yaml -f k8s/cnpg/01-cluster.yaml
kubectl get cluster -n fastapi-app -w                    # «Cluster in healthy state», 3/3
kubectl apply -f k8s/cnpg/04-app-config-cnpg.yaml && kubectl rollout restart deploy -n fastapi-app
# Failover: удаляем текущий primary
kubectl get pods -n fastapi-app -l cnpg.io/cluster=restaurant-db -L role
kubectl delete pod -n fastapi-app <primary-pod>
kubectl get pods -n fastapi-app -l cnpg.io/cluster=restaurant-db -L role -w   # СКРИНШОТ: новый primary
kubectl apply -f k8s/cnpg/02-scheduled-backup.yaml -f k8s/cnpg/03-backup-now.yaml
kubectl get backups -n fastapi-app                       # СКРИНШОТ: phase completed
```

## 7. Argo CD и Image Updater
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
kubectl port-forward svc/argocd-server -n argocd 8080:443   # https://localhost:8080, admin / пароль выше
kubectl apply -f argocd/application.yaml                     # СКРИНШОТ: Synced + Healthy
# GitOps: меняем values-dev.yaml (api.replicaCount: 2), git push -> через ~3 мин 2 пода API
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/stable/manifests/install.yaml
kubectl apply -f argocd/application-prod-image-updater.yaml
kubectl apply -f argocd/applicationset.yaml                  # restaurant-dev / -staging / -prod
git tag v0.3.1 && git push --tags                            # CI собирает образы, Image Updater коммитит тег
```
