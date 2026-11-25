def order_payload(*pairs):
    return {"items": [{"dish_id": d, "quantity": q} for d, q in pairs]}


def test_create_order_with_several_dishes(client, make_dish, scheduled_tasks):
    pizza = make_dish("Пицца", 450.0)
    soup = make_dish("Борщ", 120.5)
    response = client.post("/orders/", json=order_payload((pizza["id"], 2), (soup["id"], 1)))
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "принят"
    assert data["total"] == 1020.5
    assert {i["dish_name"]: i["quantity"] for i in data["items"]} == {"Пицца": 2, "Борщ": 1}
    assert {i["subtotal"] for i in data["items"]} == {900.0, 120.5}
    # после создания в очередь поставлена фоновая задача
    assert scheduled_tasks == [data["id"]]


def test_order_keeps_price_after_menu_change(client, make_dish):
    dish = make_dish("Пицца", 450.0)
    order = client.post("/orders/", json=order_payload((dish["id"], 1))).json()
    client.put(f"/dishes/{dish['id']}", json={"name": "Пицца", "price": 999.0})
    again = client.get(f"/orders/{order['id']}").json()
    assert again["items"][0]["price"] == 450.0
    assert again["total"] == 450.0


def test_duplicate_dishes_are_merged(client, make_dish):
    dish = make_dish()
    response = client.post("/orders/", json=order_payload((dish["id"], 1), (dish["id"], 2)))
    assert response.status_code == 201
    items = response.json()["items"]
    assert len(items) == 1 and items[0]["quantity"] == 3


def test_create_order_errors(client, make_dish, scheduled_tasks):
    dish = make_dish()
    hidden = make_dish("Снято с меню", 10, is_available=False)
    assert client.post("/orders/", json=order_payload((999, 1))).status_code == 404
    assert client.post("/orders/", json=order_payload((hidden["id"], 1))).status_code == 400
    assert client.post("/orders/", json={"items": []}).status_code == 422
    assert client.post("/orders/", json=order_payload((dish["id"], 0))).status_code == 422
    assert scheduled_tasks == []  # ни один неудачный запрос не создал задачу


def test_get_orders_pagination_and_filter(client, make_dish):
    dish = make_dish()
    for _ in range(3):
        client.post("/orders/", json=order_payload((dish["id"], 1)))
    client.patch("/orders/2/status", json={"status": "готовится"})

    assert len(client.get("/orders/").json()) == 3
    assert len(client.get("/orders/?limit=2").json()) == 2
    assert len(client.get("/orders/?skip=2").json()) == 1
    filtered = client.get("/orders/", params={"status": "готовится"}).json()
    assert [o["id"] for o in filtered] == [2]


def test_get_order_and_not_found(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json=order_payload((dish["id"], 1)))
    assert client.get("/orders/1").status_code == 200
    response = client.get("/orders/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_update_order(client, make_dish):
    pizza = make_dish("Пицца", 450.0)
    soup = make_dish("Борщ", 100.0)
    client.post("/orders/", json=order_payload((pizza["id"], 1)))
    body = {"items": [{"dish_id": soup["id"], "quantity": 3}], "status": "готовится"}
    response = client.put("/orders/1", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "готовится"
    assert [i["dish_name"] for i in data["items"]] == ["Борщ"]
    assert data["total"] == 300.0
    assert client.put("/orders/999", json=body).status_code == 404


def test_change_status(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json=order_payload((dish["id"], 1)))
    for status in ["готовится", "доставляется", "завершён"]:
        response = client.patch("/orders/1/status", json={"status": status})
        assert response.status_code == 200
        assert response.json()["status"] == status
    assert client.patch("/orders/1/status", json={"status": "потерян"}).status_code == 422
    assert client.patch("/orders/999/status", json={"status": "готовится"}).status_code == 404


def test_delete_order(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json=order_payload((dish["id"], 1)))
    assert client.delete("/orders/1").status_code == 204
    assert client.get("/orders/1").status_code == 404
    assert client.delete("/orders/1").status_code == 404


def test_rate_limit_on_order_creation(client, make_dish):
    dish = make_dish()
    payload = order_payload((dish["id"], 1))
    for _ in range(20):
        assert client.post("/orders/", json=payload).status_code == 201

    response = client.post("/orders/", json=payload)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    # другие эндпоинты этим лимитом не затронуты
    assert client.get("/orders/").status_code == 200
    assert client.get("/dishes/").status_code == 200


def test_rate_limit_skipped_when_redis_is_down(client, make_dish, broken_redis):
    dish = make_dish()
    for _ in range(25):
        assert client.post("/orders/", json=order_payload((dish["id"], 1))).status_code == 201
