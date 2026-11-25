# ЛР5 — команды для демонстрации и скриншотов

> Network Policies работают только с CNI, который их поддерживает: `minikube start --cni=calico --cpus=4 --memory=8g`

## 1. JWT и роли (локально или через port-forward)
```bash
# регистрация клиента (роль задаёт сервер; поле role -> 422)
curl -s -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"ivan","password":"Pizza2026"}'
# вход: OAuth2 password flow (form-urlencoded)
curl -s -X POST localhost:8000/auth/token -d 'username=ivan&password=Pizza2026'
TOKEN=...; curl -s localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/dishes/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"X","price":1}'          # 403 — клиент не меняет меню
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/orders/1 -H "Authorization: Bearer $TOKEN"   # 404 — чужой заказ (BOLA)
```

## 2. Pod Security Standards и securityContext
```bash
kubectl apply -f k8s/00-namespace.yaml -f k8s/05-serviceaccounts.yaml
kubectl get ns fastapi-app --show-labels                              # СКРИНШОТ: pod-security.kubernetes.io/enforce=restricted
kubectl run root-test -n fastapi-app --image=nginx:1.27               # отказ: violates PodSecurity "restricted:latest"
kubectl exec -n fastapi-app deploy/api -- id                          # uid=10001 gid=10001
kubectl exec -n fastapi-app deploy/api -- touch /code/x               # Read-only file system
```

## 3. Network Policies
```bash
kubectl apply -f k8s/network-policies/
kubectl get networkpolicy -n fastapi-app                              # СКРИНШОТ: 14 политик
kubectl exec -n fastapi-app deploy/celery-worker -- python -c "import socket; socket.create_connection(('redis',6379),3)"  # timeout
```

## 4. Vault + VSO
```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace -f security/vault-values.yaml
bash scripts/vault-setup.sh
kubectl get vaultstaticsecret,vaultdynamicsecret -n fastapi-app       # СКРИНШОТ
kubectl get secret app-db-credentials -n fastapi-app -o jsonpath='{.data.DATABASE_USER}' | base64 -d   # v-kubernet-restaura-...
kubectl exec -n vault vault-0 -- env VAULT_TOKEN=root vault list sys/leases/lookup/database/creds/restaurant-app
```

## 5. Kyverno
```bash
helm repo add kyverno https://kyverno.github.io/kyverno/ && helm install kyverno kyverno/kyverno -n kyverno --create-namespace
kubectl apply -f security/kyverno/policies.yaml
kubectl apply -f security/kyverno/test-privileged-pod.yaml            # СКРИНШОТ: denied by disallow-privileged-containers
kubectl get clusterpolicy                                             # READY=True
kubectl get policyreport -n fastapi-app                               # аудит require-ro-rootfs (rabbitmq)
```

## 6. Falco
```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco -n falco --create-namespace -f security/falco/falco-values.yaml
kubectl exec -n fastapi-app deploy/api -- sh -c 'id'                  # срабатывает «Shell in restaurant container»
kubectl logs -n falco -l app.kubernetes.io/name=falco --tail=20 | grep restaurant
# Grafana -> Explore -> Loki:  {namespace="falco"} |= "restaurant"     (СКРИНШОТ)
```

## 7. cert-manager и TLS
```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true
kubectl apply -f security/cert-manager/cluster-issuers.yaml
kubectl apply -f k8s/30-ingress.yaml
kubectl get certificate -n fastapi-app                                # restaurant-tls READY=True
curl -k -I https://restaurant.local/health                            # HTTP/2 200
curl -I http://restaurant.local/health                                # 308 -> https
```

## 8. Trivy (CI и локально)
```bash
trivy image --severity CRITICAL,HIGH --ignore-unfixed restaurant-api:0.5.0
trivy config k8s/ && trivy fs --scanners secret .
```
