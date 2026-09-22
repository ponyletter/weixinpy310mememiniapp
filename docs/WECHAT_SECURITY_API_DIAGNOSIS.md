# 微信内容安全接口诊断（2026-09-22）

## 结论

线上 `https://meme.tg-cc755.cn` 仍在运行旧版本：直接请求
`/api/materials/templates` 返回 20 个旧 `tpl_*` 模板，而当前仓库返回 10 个
`open_*` 模板。因此线上图片误报和 `render-meme` 400 不能用当前工作区复现；它们
来自尚未部署的旧代码。

旧代码有两条误报路径：

1. `imgSecCheck` 的任意非零接口错误（鉴权、限频、配额等）都被映射为“内容违规”。
2. `msgSecCheck` 2.0 缺少有效 OpenID 时返回 `40003`。即使随后 1.0 降级检测通过，
   旧代码仍继续根据第一次的 `40003` 返回“内容违规”。

## 官方接口实测

使用仓库当前小程序配置，针对用户提供的参考图片进行脱敏测试：

- `POST /wxa/img_sec_check`：`errcode=0, errmsg=ok`。
- `POST /wxa/media_check_async`（2.0）：请求成功受理并返回 `trace_id`。
- `POST /wxa/msg_sec_check`（2.0）使用数据库旧 OpenID：返回
  `40003 invalid openid`，证明这是调用参数/登录态问题，不是文本违规。

官方文档说明同步图片接口属于 1.0，已在 2021-09-01 停止更新；2.0 图片接口
`mediaCheckAsync` 是异步接口，需要公开可下载的 `media_url`、真实 OpenID，并通过
消息推送接收最终结果。它不能在不改变产品流程的情况下直接替代当前同步上传预检。

## 可重复诊断

从 `backend/` 目录运行：

```bash
python scripts/check_wechat_security_api.py --image /absolute/path/test.png
python scripts/check_wechat_security_api.py --text 测试 --openid REAL_OPENID
python scripts/check_wechat_security_api.py \
  --media-url https://public.example/test.png --openid REAL_OPENID
```

脚本仅输出 `errcode`、`errmsg`、`trace_id`、`result` 和 `detail`，不会打印
Access Token 或 OpenID。

## 部署后验证

1. `GET /health` 应包含 `revision=security-templates-20260922-v2`。
2. `GET /api/materials/templates` 应返回 10 个 `open_*` 模板。
3. 已登录请求 `POST /api/materials/render-meme`，台词为“测试”，应返回 200。
4. 上传参考图到 `POST /api/check/image` 应返回 200。
5. 若微信接口自身故障，服务端日志应记录原始 `errcode`，客户端不应再看到伪造的
   “内容违规”结论。
