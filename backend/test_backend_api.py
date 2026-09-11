import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import init_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret-with-at-least-thirty-two-characters")
    monkeypatch.setattr(settings, "ENABLE_MOCK_PAYMENT", False)
    monkeypatch.setattr(settings, "XPAY_ENV", 1)
    monkeypatch.setattr(settings, "XPAY_OFFER_ID", "test-offer")
    monkeypatch.setattr(settings, "XPAY_APP_KEY_SANDBOX", "test-payment-app-key")
    monkeypatch.setattr(settings, "XPAY_CALLBACK_TOKEN", "test-callback-token")
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "OUTPUT_DIR", tmp_path / "outputs")
    settings.UPLOAD_DIR.mkdir(parents=True)
    settings.OUTPUT_DIR.mkdir(parents=True)
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, name: str = "alice") -> tuple[str, dict[str, str]]:
    response = client.post("/api/user/login", json={"code": f"mock_{name}"})
    assert response.status_code == 200
    data = response.json()
    assert "session_key" not in data["user"]
    return data["user"]["openid"], {"Authorization": f"Bearer {data['access_token']}"}


def png_bytes(color: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, "PNG")
    return buffer.getvalue()


def test_authentication_and_user_isolation(client: TestClient):
    alice, alice_headers = login(client, "alice")
    bob, _ = login(client, "bob")
    assert client.get(f"/api/user/profile?openid={alice}").status_code == 401
    assert client.get(f"/api/user/profile?openid={alice}", headers=alice_headers).status_code == 200
    assert client.get(f"/api/user/profile?openid={bob}", headers=alice_headers).status_code == 403
    forged = {"Authorization": alice_headers["Authorization"] + "tampered"}
    assert client.get(f"/api/user/profile?openid={alice}", headers=forged).status_code == 401


def test_collection_ownership(client: TestClient):
    alice, alice_headers = login(client, "alice")
    _, bob_headers = login(client, "bob")
    response = client.post("/api/collection/create", json={"openid": alice, "title": "private"}, headers=alice_headers)
    collection_id = response.json()["data"]["collection_id"]
    denied = client.post(
        "/api/collection/add-item",
        json={"collection_id": collection_id, "gif_url": "/outputs/test.gif"},
        headers=bob_headers,
    )
    assert denied.status_code == 403


def test_mock_payment_and_callback_are_closed_by_default(client: TestClient):
    _, headers = login(client)
    assert client.post("/api/pay/mock-pay", json={"order_id": "unknown"}, headers=headers).status_code == 404
    assert client.post("/api/pay/notify", json={"outTradeNo": "unknown"}).status_code == 401


def test_payment_callback_validates_business_fields(client: TestClient):
    _, headers = login(client)
    created = client.post(
        "/api/pay/create-order",
        json={"openid": "user_mock_alice", "package_id": "meme_100"},
        headers=headers,
    )
    assert created.status_code == 200
    order_id = created.json()["data"]["order_id"]
    callback_headers = {"X-XPay-Callback-Token": "test-callback-token"}

    rejected = client.post(
        "/api/pay/notify",
        json={"outTradeNo": order_id, "productId": "meme_100", "goodsPrice": 1, "offerId": "test-offer"},
        headers=callback_headers,
    )
    assert rejected.status_code == 400

    accepted = client.post(
        "/api/pay/notify",
        json={"outTradeNo": order_id, "productId": "meme_100", "goodsPrice": 100, "offerId": "test-offer"},
        headers=callback_headers,
    )
    assert accepted.status_code == 200


def test_path_traversal_is_rejected(client: TestClient):
    _, headers = login(client)
    response = client.post(
        "/api/convert/edit-caption",
        data={"gif_url": "/outputs/../../app/config.py", "caption": "test"},
        headers=headers,
    )
    assert response.status_code == 400


def test_staged_multi_image_composition(client: TestClient):
    _, headers = login(client)
    upload_ids = []
    for color in ("red", "blue"):
        response = client.post(
            "/api/convert/images-to-gif/frame",
            files={"file": (f"{color}.png", png_bytes(color), "image/png")},
            headers=headers,
        )
        assert response.status_code == 200
        upload_ids.append(response.json()["upload_id"])
    response = client.post(
        "/api/convert/images-to-gif/compose",
        json={"upload_ids": upload_ids, "fps": 4, "caption": "测试"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
