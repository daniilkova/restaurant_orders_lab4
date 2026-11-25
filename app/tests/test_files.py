import io
import json
import logging

from app.logging_config import JsonFormatter

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def test_upload_and_download_file(client, s3_storage):
    response = client.post(
        "/files/upload", files={"file": ("menu.pdf", b"%PDF-1.4 test", "application/pdf")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["object_name"].startswith("uploads/") and body["object_name"].endswith(".pdf")
    assert body["size"] == len(b"%PDF-1.4 test")

    download = client.get(f"/files/download/{body['object_name']}")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 test"
    assert download.headers["content-type"] == "application/pdf"
    assert "attachment" in download.headers["content-disposition"]


def test_object_name_is_generated_by_server(client, s3_storage):
    response = client.post("/files/upload", files={"file": ("../../etc/passwd", b"x", "text/plain")})
    assert response.status_code == 201
    name = response.json()["object_name"]
    assert ".." not in name and name.startswith("uploads/")


def test_download_rejects_path_traversal_and_missing(client, s3_storage):
    assert client.get("/files/download/uploads/../secret").status_code in (400, 404)
    assert client.get("/files/download/other/file.txt").status_code == 400
    assert client.get("/files/download/uploads/nope.txt").status_code == 404


def test_upload_size_limit(client, s3_storage, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = io.BytesIO(b"0" * (1024 * 1024 + 1))
    response = client.post("/files/upload", files={"file": ("big.bin", big, "application/octet-stream")})
    assert response.status_code == 413


def test_empty_file_rejected(client, s3_storage):
    assert client.post("/files/upload", files={"file": ("e.txt", b"", "text/plain")}).status_code == 400


def test_dish_image_upload_replaces_old_and_is_served(client, s3_storage, make_dish):
    dish = make_dish()
    assert dish["image_url"] is None

    first = client.put(f"/dishes/{dish['id']}/image", files={"file": ("a.png", PNG, "image/png")})
    assert first.status_code == 200, first.text
    assert first.json()["image_url"] == f"/dishes/{dish['id']}/image"
    second = client.put(f"/dishes/{dish['id']}/image", files={"file": ("b.jpg", JPEG, "image/jpeg")})
    assert second.status_code == 200

    keys = [o["Key"] for o in s3_storage.client.list_objects_v2(Bucket="test-bucket")["Contents"]]
    assert len(keys) == 1 and keys[0].endswith(".jpg")  # старое фото удалено

    image = client.get(f"/dishes/{dish['id']}/image")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == JPEG
    # меню (из кэша) тоже знает про фото: кэш сброшен после загрузки
    menu = client.get("/dishes/").json()
    assert menu[0]["image_url"] == f"/dishes/{dish['id']}/image"
    assert "image_key" not in menu[0]


def test_dish_image_type_checked_by_content_not_header(client, s3_storage, make_dish):
    dish = make_dish()
    fake = client.put(f"/dishes/{dish['id']}/image", files={"file": ("x.png", b"not an image", "image/png")})
    assert fake.status_code == 415
    svg = client.put(f"/dishes/{dish['id']}/image", files={"file": ("x.svg", SVG, "image/svg+xml")})
    assert svg.status_code == 415


def test_dish_without_image_404(client, s3_storage, make_dish):
    dish = make_dish()
    assert client.get(f"/dishes/{dish['id']}/image").status_code == 404
    assert client.put("/dishes/999/image", files={"file": ("a.png", PNG, "image/png")}).status_code == 404


def test_metrics_endpoint(client, make_dish):
    dish = make_dish()
    client.post("/orders/", json={"items": [{"dish_id": dish["id"], "quantity": 2}]})
    client.get("/orders/999")
    text = client.get("/metrics").text
    assert 'http_requests_total{handler="/orders/{order_id}",method="GET",status="404"}' in text
    assert "restaurant_orders_created_total" in text
    assert "restaurant_order_total_rub_bucket" in text
    assert 'handler="/metrics"' not in text  # служебные эндпоинты исключены


def test_json_log_format():
    record = logging.makeLogRecord(
        {"name": "app.access", "levelname": "INFO", "msg": "GET %s", "args": ("/orders",), "status": 200}
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "GET /orders"
    assert payload["level"] == "INFO" and payload["status"] == 200 and "ts" in payload
