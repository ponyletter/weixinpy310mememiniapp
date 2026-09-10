"""
微信小程序虚拟支付 2.0 (XPay) 服务端自动化道具上架与发布脚本
通过官方 /xpay/start_upload_goods 和 /xpay/start_publish_goods 接口实现全自动管理
"""
import time
import json
import hmac
import hashlib
import requests
from app.config import settings

def get_access_token() -> str:
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={settings.WX_APPID}&secret={settings.WX_APPSECRET}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"获取 access_token 失败: {data}")
    return token

def calc_pay_sig(uri: str, post_body: str, appkey: str) -> str:
    msg = f"{uri}&{post_body}"
    return hmac.new(appkey.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

def sync_props():
    token = get_access_token()
    appkey = settings.XPAY_APP_KEY_LIVE if settings.XPAY_ENV == 0 else settings.XPAY_APP_KEY
    env = settings.XPAY_ENV

    items = [
        {
            "id": "meme_100",
            "name": "制作尝鲜包1元",
            "price": 100,
            "remark": "尝鲜包20次",
            "item_url": "https://apiwx.tg-cc755.cn/api/assets/goods_icon.png"
        },
        {
            "id": "meme_500",
            "name": "制作超值包5元",
            "price": 500,
            "remark": "超值包120次",
            "item_url": "https://apiwx.tg-cc755.cn/api/assets/goods_icon.png"
        },
        {
            "id": "meme_990",
            "name": "制作尊享包9元9",
            "price": 990,
            "remark": "尊享包300次VIP",
            "item_url": "https://apiwx.tg-cc755.cn/api/assets/goods_icon.png"
        }
    ]

    for item in items:
        print(f"📦 正在上传道具: {item['id']} ({item['name']}, {item['price']}分)...")
        uri = "/xpay/start_upload_goods"
        payload = {"upload_item": [item], "env": env}
        post_body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        pay_sig = calc_pay_sig(uri, post_body, appkey)
        url = f"https://api.weixin.qq.com/xpay/start_upload_goods?access_token={token}&pay_sig={pay_sig}"
        resp = requests.post(url, data=post_body.encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"}, timeout=10)
        print(f"   上传结果: {resp.text}")
        time.sleep(2)

        print(f"🚀 正在发布道具: {item['id']}...")
        uri = "/xpay/start_publish_goods"
        payload = {"publish_item": [{"id": item["id"]}], "env": env}
        post_body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        pay_sig = calc_pay_sig(uri, post_body, appkey)
        url = f"https://api.weixin.qq.com/xpay/start_publish_goods?access_token={token}&pay_sig={pay_sig}"
        resp = requests.post(url, data=post_body.encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"}, timeout=10)
        print(f"   发布结果: {resp.text}")
        time.sleep(2)

    print("🎉 全部道具上传与发布流程完成！")

if __name__ == "__main__":
    sync_props()
