# 域名与 DNS 解析配置规范

本文档为表情包小程序后端服务与资源加速提供二级域名命名建议、DNS 解析配置及微信服务器合法域名配置参考。

---

## 一、推荐二级域名前缀方案

基于你的主域名 `tg-cc755.cn`，推荐以下前缀方案：

| 方案 | 完整二级域名 | 用途定位 | 推荐度 |
| :--- | :--- | :--- | :--- |
| **方案 A（首选直观）** | **`meme.tg-cc755.cn`** | 统一承载小程序 API 接口与管理后台 | ⭐⭐⭐⭐⭐ (最推荐) |
| **方案 B（API专线）** | **`api-meme.tg-cc755.cn`** | 纯后端 API 接口，若后续图片走单独 CDN | ⭐⭐⭐⭐ |
| **方案 C（拼音特色）** | **`doutu.tg-cc755.cn`** | 斗图专有二级域，辨识度高 | ⭐⭐⭐⭐ |
| **方案 D（动静态分离）** | **`meme.tg-cc755.cn`** (API) + **`img-meme.tg-cc755.cn`** (表情包静态资源加速) | 高并发、大流量多表情包分发 | ⭐⭐⭐⭐⭐ |

---

## 二、DNS 解析添加指南（提前配置）

登录你的域名 DNS 解析后台（如腾讯云 DNSPod、阿里云云解析或 Cloudflare），添加以下 A 记录：

```text
主机记录 (RR) : meme
记录类型       : A
线路类型       : 默认
记录值         : 81.69.190.161  (你的国内云服务器公网 IP)
TTL            : 600 (或默认)
```

若采用动静态分离，可额外添加：
```text
主机记录 (RR) : img-meme
记录类型       : A / CNAME (指向服务器 IP 或 CDN 加速域名)
```

---

## 三、服务器 Nginx 反向代理配置参考

在服务器配置 Nginx 并申请 Let's Encrypt / 腾讯云免费 SSL 证书（HTTPS 是微信小程序必须要求）：

```nginx
server {
    listen 80;
    server_name meme.tg-cc755.cn;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name meme.tg-cc755.cn;

    ssl_certificate /etc/letsencrypt/live/meme.tg-cc755.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/meme.tg-cc755.cn/privkey.pem;

    # 后端 Python API 服务反代（例如监听在 8290 端口）
    location /api/ {
        proxy_pass http://127.0.0.1:8290/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # 表情包静态资源直接由 Nginx 高速提供，避免占用 Python 进程
    location /static/memes/ {
        alias /root/02project/weixinpy310mememiniapp/data/memes/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

---

## 四、微信小程序后台“服务器域名”配置

在微信公众平台【开发管理】➔【开发设置】➔【服务器域名】中需配置：
- **`request` 合法域名**：`https://meme.tg-cc755.cn`
- **`downloadFile` 合法域名**：`https://meme.tg-cc755.cn`（用于用户在小程序内保存表情包到手机相册）
- **`uploadFile` 合法域名**：`https://meme.tg-cc755.cn`（若支持用户上传表情或留言截图）
