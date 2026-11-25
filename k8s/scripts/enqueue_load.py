"""Нагрузка на очередь RabbitMQ для проверки KEDA.

Ставит N задач «отчёт кухни» в очередь celery. Запуск внутри кластера:
    kubectl exec -n fastapi-app deploy/api -- python -m scripts.enqueue_load 200 --seconds 3
и наблюдение:
    kubectl get deploy celery-worker -n fastapi-app -w
"""
import argparse

from app.tasks import prepare_kitchen_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Поставить N задач в очередь Celery")
    parser.add_argument("count", type=int, nargs="?", default=100)
    parser.add_argument("--seconds", type=float, default=2.0, help="длительность одной задачи")
    args = parser.parse_args()
    for i in range(1, args.count + 1):
        prepare_kitchen_report.delay(i, args.seconds)
    print(f"В очередь поставлено задач: {args.count}")


if __name__ == "__main__":
    main()
