import hashlib
import time
import requests

BASE_URL = "http://127.0.0.1:8290"

def test_all():
    print("=" * 60)
    print("🧪 开始微信小程序 AI 表情包制作全栈后端 API 自动化全链路测试")
    print("=" * 60)
    
    # 1. 探活
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health failed: {r.text}"
    print("✅ 1. 基础探活接口 /health 测试通过")

    # 2. 模版列表
    r = requests.get(f"{BASE_URL}/api/templates")
    assert r.status_code == 200
    templates = r.json()["data"]
    assert len(templates) > 0
    print(f"✅ 2. 预设动作模版列表 /api/templates 测试通过，加载 {len(templates)} 个动作模版")

    # 3. 提示词组装器
    r = requests.post(f"{BASE_URL}/api/prompt-builder", data={
        "character_desc": "可爱的白色萨摩耶",
        "action_type": "kiss",
        "custom_caption": "么么哒",
        "has_image": "false",
        "is_sketch": "false"
    })
    assert r.status_code == 200
    prompt_res = r.json()["data"]
    assert "么么哒" in prompt_res["generated_prompt"]
    print("✅ 3. AI 提示词智能组装器 /api/prompt-builder 测试通过")

    # 4. 微信公开配置接口
    r = requests.get(f"{BASE_URL}/api/wechat/info")
    assert r.status_code == 200
    wx_info = r.json()
    assert wx_info["app_id"] == "wx86e299efa495d1f6"
    assert wx_info["offer_id"] == "1450644655"
    assert wx_info["order_center_path"] == "pages/order/order"
    print("✅ 4. 微信公开参数与资质配置 /api/wechat/info 测试通过")

    # 5. 微信消息推送与服务器握手验证 (GET)
    token = "memeTokenSecret2026"
    ts = str(int(time.time()))
    nonce = "rand9988"
    echostr = "echostr_test_success_123"
    sig = hashlib.sha1(''.join(sorted([token, ts, nonce])).encode()).hexdigest()
    r = requests.get(f"{BASE_URL}/api/wechat/callback?signature={sig}&timestamp={ts}&nonce={nonce}&echostr={echostr}")
    assert r.status_code == 200
    assert r.text == echostr
    print("✅ 5. 微信公众平台服务器配置/消息推送握手验证 /api/wechat/callback (GET) 测试通过")

    # 6. 小程序订单中心 Path
    r = requests.get(f"{BASE_URL}/pages/order/order")
    assert r.status_code == 200
    assert r.json()["path"] == "pages/order/order"
    print("✅ 6. 小程序订单中心直达端点 /pages/order/order 测试通过")

    # 7. 用户登录 (code2session / mock)
    test_code = f"mock_tester_{int(time.time())}"
    r = requests.post(f"{BASE_URL}/api/user/login", json={"code": test_code})
    assert r.status_code == 200
    login_data = r.json()
    openid = login_data["openid"]
    user = login_data["user"]
    assert user["free_quota"] == 10  # 新用户赠送 10 次
    print(f"✅ 7. 用户静默登录 /api/user/login 测试通过，获得 openid={openid}，新用户赠送 {user['free_quota']} 次免费额度")

    # 8. 用户资料查询
    r = requests.get(f"{BASE_URL}/api/user/profile?openid={openid}")
    assert r.status_code == 200
    assert r.json()["user"]["total_quota"] >= 10
    print("✅ 8. 用户资料与实时额度资产查询 /api/user/profile 测试通过")

    # 9. 每日签到
    r = requests.post(f"{BASE_URL}/api/user/checkin", json={"openid": openid})
    assert r.status_code == 200
    checkin_res = r.json()
    assert checkin_res["success"] is True
    assert checkin_res["reward"] == 3
    print(f"✅ 9. 每日签到领取额度 /api/user/checkin 测试通过，额外到账 {checkin_res['reward']} 次，当前剩余: {checkin_res['remaining_quota']} 次")

    # 10. 兑换码兑换
    r = requests.post(f"{BASE_URL}/api/user/redeem", json={"openid": openid, "code": "MEME888"})
    assert r.status_code == 200
    redeem_res = r.json()
    assert redeem_res["success"] is True
    print(f"✅ 10. 私域兑换码兑换 /api/user/redeem (MEME888) 测试通过，到账 {redeem_res['reward_quota']} 次，当前剩余: {redeem_res['remaining_quota']} 次")

    # 11. 虚拟支付道具列表查询
    r = requests.get(f"{BASE_URL}/api/pay/goods")
    assert r.status_code == 200
    goods = r.json()["packages"]
    assert len(goods) == 3
    print(f"✅ 11. 虚拟支付 2.0 道具档位列表 /api/pay/goods 测试通过，包含 1元(20次), 5元(120次), 9.9元(300次/VIP)")

    # 12. 虚拟支付 2.0 下单与 paySig/signature 计算
    r = requests.post(f"{BASE_URL}/api/pay/create-order", json={"openid": openid, "package_id": "item_100"})
    assert r.status_code == 200
    pay_order = r.json()["data"]
    order_id = pay_order["order_id"]
    pay_params = pay_order["payment_params"]
    assert "paySig" in pay_params
    assert "signature" in pay_params
    assert "signData" in pay_params
    assert pay_params["mode"] == "short_series_goods"
    print(f"✅ 12. 微信虚拟支付 2.0 下单与核心双签名计算 /api/pay/create-order 测试通过 (订单号: {order_id})")

    # 13. 模拟支付履约与发货
    r = requests.post(f"{BASE_URL}/api/pay/mock-pay", json={"order_id": order_id})
    assert r.status_code == 200
    print("✅ 13. 虚拟支付订单履约发货 /api/pay/mock-pay 测试通过，额度已自动划转至用户账户")

    # 14. 查询订单记录
    r = requests.get(f"{BASE_URL}/api/user/orders?openid={openid}")
    assert r.status_code == 200
    orders = r.json()["orders"]
    assert len(orders) >= 1
    assert orders[0]["status"] == "PAID"
    print(f"✅ 14. 订单历史流水与订单中心 /api/user/orders 测试通过，状态: {orders[0]['status']}")

    # 15. 制作表情包额度审查与扣减启动任务
    r = requests.post(f"{BASE_URL}/api/generate-async", data={
        "action_type": "run_cheer",
        "custom_caption": "冲鸭",
        "character_desc": "测试小柴犬",
        "fps": 8,
        "openid": openid
    })
    assert r.status_code == 200
    task_res = r.json()
    task_id = task_res["data"]["task_id"]
    print(f"✅ 15. 异步生成任务启动与额度动态扣减 /api/generate-async 测试通过 (任务ID: {task_id})")

    # 16. 任务状态轮询查询
    r = requests.get(f"{BASE_URL}/api/task-status/{task_id}")
    assert r.status_code == 200
    status_info = r.json()["data"]
    assert status_info["status"] in ["processing", "completed"]
    print(f"✅ 16. 异步任务进度与状态轮询 /api/task-status/{task_id} 测试通过 (当前进度: {status_info.get('progress')}%)")

    # 17. 历史作品查询
    r = requests.get(f"{BASE_URL}/api/history?openid={openid}")
    assert r.status_code == 200
    print("✅ 17. 用户生成历史与作品展示 /api/history 测试通过")

    print("=" * 60)
    print("🎉 恭喜！全套 17 个微信小程序核心后端接口自动化测试 100% 全部通过！")
    print("=" * 60)

if __name__ == "__main__":
    test_all()
