#!/usr/bin/env python3
"""独立检查 Cloudflare R2 的 DNS、HTTPS、自定义域名和 S3 读写能力。

公开域名检查不需要密钥：

    python backend/r2_probe.py

完整 S3 写入/读取/删除检查需要先在当前 shell 设置临时环境变量：

    export R2_ACCESS_KEY_ID='...'
    export R2_SECRET_ACCESS_KEY='...'
    python backend/r2_probe.py

脚本只会操作一个随机生成的 r2-healthcheck/ 测试对象，默认测试结束后删除。
不会打印密钥，也不会修改现有业务对象。
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


DEFAULT_ACCOUNT_ID = "2b8b32244fb5f932eeaaa106ac264061"
DEFAULT_BUCKET = "memo"
DEFAULT_S3_ENDPOINT = f"https://{DEFAULT_ACCOUNT_ID}.r2.cloudflarestorage.com"
DEFAULT_PUBLIC_URL = "https://media.tg-cc755.cn"


def log(status: str, message: str) -> None:
    print(f"[{status}] {message}")


def public_object_url(public_url: str, key: str) -> str:
    encoded_key = quote(key.lstrip("/"), safe="/~.-_")
    return f"{public_url.rstrip('/')}/{encoded_key}"


def probe_dns_and_tls(public_url: str, label: str = "公开域名") -> bool:
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.hostname:
        log("FAIL", f"{label}必须是完整 HTTPS URL：{public_url}")
        return False

    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)})
        log("PASS", f"{label} DNS {parsed.hostname} -> {', '.join(addresses)}")
    except OSError as exc:
        log("FAIL", f"{label} DNS 解析失败：{exc}")
        return False

    try:
        request = Request(public_url.rstrip("/") + "/", method="GET", headers={"User-Agent": "r2-probe/1.0"})
        with urlopen(request, timeout=15) as response:
            status = response.status
            response.read(256)
        if status < 500:
            log("PASS", f"{label} HTTPS/TLS 可用，返回 HTTP {status}")
            return True
        log("FAIL", f"{label}返回服务器错误 HTTP {status}")
    except HTTPError as exc:
        if exc.code in (400, 403, 404):
            log("PASS", f"{label} HTTPS/TLS 可用，返回 HTTP {exc.code}（未授权、无对象或未开放目录索引均可能出现）")
            return True
        log("FAIL", f"{label}返回 HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        log("FAIL", f"{label} HTTPS 访问失败：{exc}")
    return False


def fetch_public_object(public_url: str, key: str, expected: bytes) -> bool:
    url = public_object_url(public_url, key)
    try:
        request = Request(url, method="GET", headers={"User-Agent": "r2-probe/1.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read()
            if response.status != 200 or body != expected:
                log("FAIL", f"自定义域名对象内容不匹配：HTTP {response.status}，地址 {url}")
                return False
        log("PASS", f"自定义域名可以读取刚上传的对象：{url}")
        return True
    except HTTPError as exc:
        log("FAIL", f"自定义域名读取对象失败：HTTP {exc.code}，地址 {url}")
    except (URLError, TimeoutError, OSError) as exc:
        log("FAIL", f"自定义域名读取对象失败：{exc}")
    return False


def probe_s3(args: argparse.Namespace) -> bool | None:
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        log("SKIP", "未设置 R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY，跳过 S3 写入测试")
        return None

    try:
        import boto3
    except ImportError:
        log("FAIL", "检测到 R2 密钥但环境没有 boto3，请安装：python -m pip install boto3")
        return False

    client = boto3.client(
        "s3",
        endpoint_url=args.s3_endpoint,
        region_name="auto",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    key = f".r2-healthcheck/{int(time.time())}-{secrets.token_hex(6)}.txt"
    payload = f"r2 probe {time.time_ns()}\n".encode("utf-8")
    uploaded = False
    try:
        client.put_object(
            Bucket=args.bucket,
            Key=key,
            Body=payload,
            ContentType="text/plain; charset=utf-8",
            CacheControl="no-store",
        )
        uploaded = True
        log("PASS", f"S3 API 上传成功：bucket={args.bucket}, key={key}")

        response = client.get_object(Bucket=args.bucket, Key=key)
        body = response["Body"].read()
        if body != payload:
            log("FAIL", "S3 API 读取成功，但对象内容不匹配")
            return False
        log("PASS", "S3 API 读取内容匹配")

        if not args.skip_public_object and not fetch_public_object(args.public_url, key, payload):
            return False
        return True
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        suffix = f"（S3 错误码：{error_code}）" if error_code else ""
        log("FAIL", f"S3 API 测试失败{suffix}：{exc}")
        return False
    finally:
        if uploaded and not args.keep:
            try:
                client.delete_object(Bucket=args.bucket, Key=key)
                log("PASS", "测试对象已删除")
            except Exception as exc:
                log("WARN", f"测试对象删除失败，请手动删除 {key}：{exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cloudflare R2 独立连通性和 S3 读写检查")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--s3-endpoint", default=DEFAULT_S3_ENDPOINT)
    parser.add_argument("--public-url", default=DEFAULT_PUBLIC_URL)
    parser.add_argument("--skip-s3", action="store_true", help="只检查 DNS/HTTPS，不执行 S3 测试")
    parser.add_argument("--skip-public-object", action="store_true", help="S3 上传读取后不再通过自定义域名读取")
    parser.add_argument("--keep", action="store_true", help="保留测试对象（默认自动删除）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log("INFO", f"检查 R2 bucket={args.bucket}")
    public_ok = probe_dns_and_tls(args.public_url, "自定义域名")
    s3_endpoint_url = f"{args.s3_endpoint.rstrip('/')}/{quote(args.bucket, safe='')}"
    s3_network_ok = probe_dns_and_tls(s3_endpoint_url, "S3 API")
    s3_ok = None if args.skip_s3 else probe_s3(args)

    if not public_ok or not s3_network_ok:
        return 1
    if s3_ok is False:
        return 1
    log("PASS", "R2 基础检查完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
