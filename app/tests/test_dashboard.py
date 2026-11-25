from app.config import settings

AUTH = (settings.admin_username, settings.admin_password)


def create_order(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]})


def test_dashboard_requires_auth(client):
    assert client.get("/dashboard/api/orders").status_code == 401
    assert client.get("/dashboard/api/orders", auth=("admin", "wrong")).status_code == 401
    assert client.get("/dashboard/").status_code == 401


def test_dashboard_page(client):
    response = client.get("/dashboard/", auth=AUTH)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_shows_active_orders_and_switches_status(client, make_dish):
    create_order(client, make_dish)
    create_order(client, make_dish)

    response = client.patch(
        "/dashboard/api/orders/1/status", json={"status": "завершён"}, auth=AUTH
    )
    assert response.status_code == 200

    active = client.get("/dashboard/api/orders", auth=AUTH).json()
    assert [o["id"] for o in active] == [2]  # завершённый заказ ушёл из списка
