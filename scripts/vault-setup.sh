#!/usr/bin/env bash
# Настройка Vault для «Ресторан и заказы»: kv-секреты, вход из Kubernetes, динамические пароли БД.
# Запуск: bash scripts/vault-setup.sh   (нужны kubectl и openssl; Vault установлен в namespace vault)
set -euo pipefail

VAULT="kubectl exec -i -n vault vault-0 -- env VAULT_TOKEN=root vault"
DB_HOST="${DB_HOST:-postgres.fastapi-app.svc.cluster.local}"   # для CloudNativePG: restaurant-db-rw.fastapi-app.svc.cluster.local
DB_OWNER="${DB_OWNER:-restaurant}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:-restaurant-pass}"

echo "== Vault Secrets Operator"
helm repo add hashicorp https://helm.releases.hashicorp.com >/dev/null 2>&1 || true
helm upgrade --install vault-secrets-operator hashicorp/vault-secrets-operator \
  -n vault-secrets-operator-system --create-namespace --wait

echo "== Вход из Kubernetes (auth/kubernetes)"
$VAULT auth enable kubernetes 2>/dev/null || true
$VAULT write auth/kubernetes/config kubernetes_host="https://kubernetes.default.svc:443"

echo "== Политика: только чтение секретов приложения и выдача динамических учётных данных БД"
$VAULT policy write fastapi-policy - <<'HCL'
path "secret/data/fastapi/*" {
  capabilities = ["read"]
}
path "database/creds/restaurant-app" {
  capabilities = ["read"]
}
HCL
$VAULT write auth/kubernetes/role/fastapi-role \
  bound_service_account_names=fastapi-sa \
  bound_service_account_namespaces=fastapi-app \
  audience=vault \
  policies=fastapi-policy \
  ttl=1h

echo "== Статические секреты (kv-v2 secret/fastapi/config)"
$VAULT secrets enable -path=secret kv-v2 2>/dev/null || true
RABBIT_PASSWORD="$(openssl rand -hex 16)"
$VAULT kv put secret/fastapi/config \
  SECRET_KEY="$(openssl rand -hex 32)" \
  DATABASE_USER="$DB_OWNER" \
  DATABASE_PASSWORD="$DB_OWNER_PASSWORD" \
  RABBITMQ_USER=restaurant \
  RABBITMQ_PASSWORD="$RABBIT_PASSWORD" \
  CELERY_BROKER_URL="amqp://restaurant:${RABBIT_PASSWORD}@rabbitmq:5672//" \
  ADMIN_USERNAME=staff \
  ADMIN_PASSWORD="$(openssl rand -base64 18)" \
  BOOTSTRAP_ADMIN_USERNAME=admin \
  BOOTSTRAP_ADMIN_PASSWORD="$(openssl rand -base64 18)" \
  METRICS_TOKEN="$(openssl rand -hex 24)"

echo "== Динамические учётные данные PostgreSQL (database secrets engine)"
$VAULT secrets enable database 2>/dev/null || true
$VAULT write database/config/restaurant \
  plugin_name=postgresql-database-plugin \
  allowed_roles=restaurant-app \
  connection_url="postgresql://{{username}}:{{password}}@${DB_HOST}:5432/restaurant?sslmode=disable" \
  username="$DB_OWNER" password="$DB_OWNER_PASSWORD"
# Временный пользователь входит в роль-владельца таблиц и наследует её права на данные
$VAULT write database/roles/restaurant-app \
  db_name=restaurant \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' IN ROLE ${DB_OWNER};" \
  revocation_statements="REASSIGN OWNED BY \"{{name}}\" TO ${DB_OWNER}; DROP OWNED BY \"{{name}}\"; DROP ROLE IF EXISTS \"{{name}}\";" \
  default_ttl=1h max_ttl=24h

echo "== Ресурсы VSO в namespace fastapi-app"
kubectl delete secret app-secret -n fastapi-app --ignore-not-found   # дальше Secret ведёт VSO
kubectl apply -f k8s/vault/
kubectl get vaultstaticsecret,vaultdynamicsecret -n fastapi-app
echo "Готово. Пароль bootstrap-администратора:"
$VAULT kv get -field=BOOTSTRAP_ADMIN_PASSWORD secret/fastapi/config
