from app.redis_client import DISHES_CACHE_KEY


def test_create_dish(client):
    response = client.post(
        "/dishes/", json={"name": "Борщ", "price": 120.5, "description": "Со сметаной"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Борщ"
    assert data["price"] == 120.5
    assert data["is_available"] is True


def test_create_dish_validation(client):
    assert client.post("/dishes/", json={"name": "X", "price": 0}).status_code == 422
    assert client.post("/dishes/", json={"name": "", "price": 10}).status_code == 422
    assert client.post("/dishes/", json={"price": 10}).status_code == 422


def test_list_dishes_empty(client):
    assert client.get("/dishes/").json() == []


def test_list_dishes_returns_created(client, make_dish, fake_redis):
    make_dish("Борщ", 120.5)
    make_dish("Пицца", 450)
    response = client.get("/dishes/")
    assert response.status_code == 200
    assert [d["name"] for d in response.json()] == ["Борщ", "Пицца"]


def test_menu_is_cached_with_ttl(client, make_dish, fake_redis):
    make_dish()
    client.get("/dishes/")
    assert DISHES_CACHE_KEY in fake_redis.store
    assert fake_redis.ttls[DISHES_CACHE_KEY] == 60


def test_menu_is_served_from_cache(client, make_dish, fake_redis):
    make_dish()
    client.get("/dishes/")
    # подменяем значение в кэше: если ответ взят из кэша, мы увидим подмену
    import json

    fake_redis.store[DISHES_CACHE_KEY] = json.dumps(
        [{"id": 99, "name": "Из кэша", "description": None, "price": 1.0, "is_available": True}]
    )
    data = client.get("/dishes/").json()
    assert [d["name"] for d in data] == ["Из кэша"]


def test_cache_invalidated_on_create_update_delete(client, make_dish, fake_redis):
    dish = make_dish()
    client.get("/dishes/")
    assert DISHES_CACHE_KEY in fake_redis.store

    make_dish("Суп", 100)
    assert DISHES_CACHE_KEY not in fake_redis.store  # POST сбросил кэш

    client.get("/dishes/")
    client.put(f"/dishes/{dish['id']}", json={"name": "Пицца 2", "price": 500})
    assert DISHES_CACHE_KEY not in fake_redis.store  # PUT сбросил кэш

    names = [d["name"] for d in client.get("/dishes/").json()]
    assert "Пицца 2" in names

    client.delete(f"/dishes/{dish['id']}")
    assert DISHES_CACHE_KEY not in fake_redis.store  # DELETE сбросил кэш


def test_menu_works_when_redis_is_down(client, make_dish, broken_redis):
    # make_dish использует тот же (уже сломанный) Redis: запись всё равно проходит
    make_dish()
    response = client.get("/dishes/")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_update_delete_dish(client, make_dish):
    dish = make_dish()
    assert client.get(f"/dishes/{dish['id']}").json()["name"] == "Пицца Маргарита"

    response = client.put(f"/dishes/{dish['id']}", json={"name": "Пицца", "price": 500})
    assert response.status_code == 200
    assert response.json()["price"] == 500

    assert client.delete(f"/dishes/{dish['id']}").status_code == 204
    assert client.get(f"/dishes/{dish['id']}").status_code == 404


def test_dish_not_found(client):
    assert client.get("/dishes/999").status_code == 404
    assert client.put("/dishes/999", json={"name": "X", "price": 1}).status_code == 404
    assert client.delete("/dishes/999").status_code == 404


def test_cannot_delete_dish_used_in_orders(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 1}]})
    response = client.delete(f"/dishes/{dish['id']}")
    assert response.status_code == 409
