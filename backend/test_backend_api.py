import io
import json
import hashlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import init_db
from app.main import app
from app.payment import calc_pay_event_sig


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
    monkeypatch.setattr(settings, "WX_MSG_TOKEN", "test-message-token")
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


def test_collection_list_and_detail_counts_match(client: TestClient):
    alice, headers = login(client, "collection_counts")
    created = client.post(
        "/api/collection/create",
        json={"openid": alice, "title": "count-check"},
        headers=headers,
    )
    assert created.status_code == 200
    collection_id = created.json()["data"]["collection_id"]

    for index in range(4):
        added = client.post(
            "/api/collection/add-item",
            json={"collection_id": collection_id, "gif_url": f"/outputs/{index}.gif", "title": str(index)},
            headers=headers,
        )
        assert added.status_code == 200

    listing = client.get(f"/api/collection/my?openid={alice}", headers=headers)
    assert listing.status_code == 200
    summary = next(item for item in listing.json()["data"] if item["collection_id"] == collection_id)
    assert summary["item_count"] == 4
    assert len(summary["preview_items"]) == 4
    assert listing.headers["cache-control"].startswith("no-store")

    detail = client.get(f"/api/collection/detail?collection_id={collection_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["item_count"] == 4
    assert len(body["items"]) == 4
    assert detail.headers["cache-control"].startswith("no-store")


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

    def callback(price):
        payload = json.dumps({
            "OpenId": "user_mock_alice",
            "OutTradeNo": order_id,
            "GoodsInfo": {
                "ProductId": "meme_100",
                "Quantity": 1,
                "OrigPrice": price,
                "ActualPrice": str(price),
                "Attach": json.dumps({"openid": "user_mock_alice", "pkg_id": "meme_100"}, separators=(",", ":")),
                "OrderSource": 10,
            },
            "PayInfo": {"TransactionId": "tx_test_001"},
        }, separators=(",", ":"))
        event = "xpay_goods_deliver_notify"
        return {
            "eventType": "TRANSACTION.SUCCESS",
            "event": event,
            "payload": payload,
            "payEventSig": calc_pay_event_sig(event, payload, "test-payment-app-key"),
            "transactionId": "tx_test_001",
            "outTradeNo": order_id,
        }

    rejected = client.post(
        "/api/pay/notify",
        json=callback(1),
        headers=callback_headers,
    )
    assert rejected.status_code == 400

    accepted = client.post(
        "/api/pay/notify",
        json=callback(100),
        headers=callback_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["returnCode"] == "0"

    status = client.get(f"/api/pay/order-status?order_id={order_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["paid"] is True

    orders = client.get("/api/user/orders?openid=user_mock_alice", headers=headers)
    assert orders.status_code == 200
    assert orders.json()["orders"][0]["timezone"] == "Asia/Shanghai"


def test_wechat_message_push_handshake_and_delivery(client: TestClient):
    _, headers = login(client, "message_push")
    created = client.post(
        "/api/pay/create-order",
        json={"openid": "user_mock_message_push", "package_id": "meme_100"},
        headers=headers,
    )
    assert created.status_code == 200
    order_id = created.json()["data"]["order_id"]

    token, timestamp, nonce = "test-message-token", "1780000000", "nonce"
    signature = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode("utf-8")).hexdigest()
    verify = client.get(
        "/api/wechat/msg_push",
        params={"signature": signature, "timestamp": timestamp, "nonce": nonce, "echostr": "challenge"},
    )
    assert verify.status_code == 200
    assert verify.text == "challenge"

    body = {
        "ToUserName": "gh_test",
        "FromUserName": "user_mock_message_push",
        "CreateTime": 1780000000,
        "MsgType": "event",
        "Event": "xpay_goods_deliver_notify",
        "OpenId": "user_mock_message_push",
        "OutTradeNo": order_id,
        "Env": 1,
        "WeChatPayInfo": {"TransactionId": "wx_tx_test"},
        "GoodsInfo": {
            "ProductId": "meme_100",
            "Quantity": 1,
            "OrigPrice": 100,
            "ActualPrice": 100,
            "Attach": json.dumps({"openid": "user_mock_message_push"}, separators=(",", ":")),
        },
    }
    delivered = client.post(
        "/api/wechat/msg_push",
        params={"signature": signature, "timestamp": timestamp, "nonce": nonce},
        json=body,
    )
    assert delivered.status_code == 200
    assert delivered.json() == {"ErrCode": 0, "ErrMsg": "success"}

    status = client.get(f"/api/pay/order-status?order_id={order_id}", headers=headers)
    assert status.json()["paid"] is True


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


def test_dynamic_frames_and_target_size_slicing():
    from PIL import Image, ImageDraw
    from app.core.sprite_processor import SpriteProcessor

    # Create a 400x400 test image with 4 distinct colored quadrants
    test_img = Image.new("RGB", (400, 400), (255, 255, 255))
    draw = ImageDraw.Draw(test_img)
    draw.rectangle([20, 20, 180, 180], fill=(255, 0, 0))
    draw.rectangle([220, 20, 380, 180], fill=(0, 255, 0))
    draw.rectangle([20, 220, 180, 380], fill=(0, 0, 255))
    draw.rectangle([220, 220, 380, 380], fill=(255, 255, 0))

    # Test 4 frames (2x2) with target_size_px = 320
    frames_4 = SpriteProcessor.slice_grid(test_img, rows=2, cols=2, target_size_px=320)
    assert len(frames_4) == 4
    for f in frames_4:
        assert f.size == (320, 320)

    # Test 2 frames (1x2) with target_size_px = 480
    frames_2 = SpriteProcessor.slice_grid(test_img, rows=1, cols=2, target_size_px=480)
    assert len(frames_2) == 2
    for f in frames_2:
        assert f.size == (480, 480)


def test_prompt_builder_frame_count():
    from app.core.prompt_templates import build_meme_prompt

    prompt_2 = build_meme_prompt("kiss", caption="爱你", frame_count=2)
    assert "2 张小图片" in prompt_2
    assert "1行×2列" in prompt_2

    prompt_4 = build_meme_prompt("battle_chibi", caption="出击", frame_count=4)
    assert "4 张小图片" in prompt_4
    assert "4 帧" in prompt_4

    prompt_16 = build_meme_prompt("kiss", caption="么么哒", frame_count=16)
    assert "16 张小图片" in prompt_16
    assert "4行×4列" in prompt_16


def test_meme_rename_and_estimate_endpoints(client: TestClient):
    openid, headers = login(client, "rename_test")

    # 1. Test estimate endpoint
    est_resp = client.get("/api/meme/estimate")
    assert est_resp.status_code == 200
    est_data = est_resp.json()["data"]
    assert "estimated_seconds" in est_data
    assert 15.0 <= est_data["estimated_seconds"] <= 90.0

    # 2. Insert a task into database to test rename
    from app.database import get_db
    with get_db() as conn:
        conn.execute(
            "INSERT INTO meme_tasks (task_id, openid, preset_key, text_bottom, status, progress, duration_seconds) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("task_rename_123", openid, "kiss", "原标题", "completed", 100, 28.5)
        )
        conn.commit()

    # Rename the task
    ren_resp = client.post(
        "/api/meme/rename",
        json={"task_id": "task_rename_123", "title": "自定义新备注", "openid": openid},
        headers=headers
    )
    assert ren_resp.status_code == 200
    assert ren_resp.json()["success"] is True

    # Check history returns custom title and CST formatted time
    hist_resp = client.get(f"/api/meme/history?openid={openid}", headers=headers)
    assert hist_resp.status_code == 200
    items = hist_resp.json()["data"]
    assert len(items) >= 1
    item = next(it for it in items if it["task_id"] == "task_rename_123")
    assert item["display_title"] == "自定义新备注"
    assert item["created_at"] is not None


def test_collection_move_rename_reorder_endpoints(client: TestClient):
    openid, headers = login(client, "col_actions")

    # Create collection 1
    c1 = client.post(
        "/api/collection/create",
        json={"openid": openid, "title": "合集A", "description": "测试合集A"},
        headers=headers
    ).json()["data"]
    col_id_1 = c1["collection_id"]

    # Create collection 2
    c2 = client.post(
        "/api/collection/create",
        json={"openid": openid, "title": "合集B", "description": "测试合集B"},
        headers=headers
    ).json()["data"]
    col_id_2 = c2["collection_id"]

    # Add 2 items to collection 1
    item1 = client.post(
        "/api/collection/add-item",
        json={"collection_id": col_id_1, "gif_url": "/samples/sample_run.png", "title": "表情1"},
        headers=headers
    ).json()["data"]
    # Test duplicate insertion returns 409
    dup_res = client.post(
        "/api/collection/add-item",
        json={"collection_id": col_id_1, "gif_url": "/samples/sample_run.png", "title": "重复表情"},
        headers=headers
    )
    assert dup_res.status_code == 409

    item2 = client.post(
        "/api/collection/add-item",
        json={"collection_id": col_id_1, "gif_url": "/samples/sample_walk.png", "title": "表情2"},
        headers=headers
    ).json()["data"]

    # 1. Test rename item
    ren_res = client.post(
        "/api/collection/item/rename",
        json={"item_id": item1["id"], "title": "改名表情1", "openid": openid},
        headers=headers
    )
    assert ren_res.status_code == 200

    # 2. Test reorder items in collection 1
    reorder_res = client.post(
        "/api/collection/item/reorder",
        json={"collection_id": col_id_1, "item_ids": [item2["id"], item1["id"]], "openid": openid},
        headers=headers
    )
    assert reorder_res.status_code == 200

    # 3. Test move item1 to collection 2
    move_res = client.post(
        "/api/collection/item/move",
        json={"item_id": item1["id"], "target_collection_id": col_id_2, "openid": openid},
        headers=headers
    )
    assert move_res.status_code == 200

    # Verify detail of collection 2 contains item1
    detail2 = client.get(f"/api/collection/detail?collection_id={col_id_2}").json()["data"]
    assert any(it["id"] == item1["id"] for it in detail2["items"])


def test_convert_toolkit_endpoints(client: TestClient):
    _, headers = login(client, "convert_toolkit")

    # 1. Test stitch-images (vertical and subtitle)
    stitch_res = client.post(
        "/api/convert/stitch-images",
        files=[
            ("files", ("img1.png", png_bytes("red"), "image/png")),
            ("files", ("img2.png", png_bytes("blue"), "image/png"))
        ],
        data={"mode": "vertical", "spacing": 2},
        headers=headers
    )
    assert stitch_res.status_code == 200
    assert stitch_res.json()["success"] is True
    assert "image_url" in stitch_res.json()

    sub_res = client.post(
        "/api/convert/stitch-images",
        files=[
            ("files", ("img1.png", png_bytes("red"), "image/png")),
            ("files", ("img2.png", png_bytes("blue"), "image/png"))
        ],
        data={"mode": "subtitle", "subtitle_ratio": 0.3},
        headers=headers
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["success"] is True

    # 2. Test compress-image
    comp_res = client.post(
        "/api/convert/compress-image",
        files={"file": ("orig.png", png_bytes("green"), "image/png")},
        data={"target_kb": 200, "quality": 75},
        headers=headers
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["success"] is True

    # 3. Test text-to-image
    card_res = client.post(
        "/api/convert/text-to-image",
        data={"text": "生活很苦，但有你很甜", "theme": "cute", "title": "今日语录", "author": "表情工坊"},
        headers=headers
    )
    assert card_res.status_code == 200
    assert card_res.json()["success"] is True
    assert "image_url" in card_res.json()
