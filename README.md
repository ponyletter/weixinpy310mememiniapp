# weixinpy310mememiniapp

微信表情包 / 斗图小程序全栈项目（Python 后端 + 微信小程序前端）。

![小程序头像与品牌视觉](assets/app_avatar.jpg)

---

## 目录索引

- [一、小程序基础资料与备案规范](docs/MINIAPP_REGISTRATION_GUIDE.md)
  - 名称推荐方案（如：**元气斗图盒**、**萌梗表情社**、**趣图喵喵包**）
  - 简介文案与类目选择（个人 vs 企业主体）
  - 头像设计与 ICP 备案前置操作
- [二、二级域名规划与 DNS 解析](docs/DOMAIN_DNS_CONFIG.md)
  - 推荐二级域名（如：`meme.tg-cc755.cn`）
  - DNS A 记录配置与国内云服务器关联
  - Nginx 反向代理与微信服务器合法域名配置
- [三、开发前置参数与虚拟支付配置清单](docs/PRE_CONFIG_CHECKLIST.md)
  - AppID / AppSecret / MCHID
  - 虚拟支付 OfferID、现网 AppKey 配置
  - 道具批量配置规范与避坑说明（金额单位：分）
- [四、16帧网格切割与去白底核心算法及流程详解](docs/ALGORITHM_AND_PIPELINE.md)
  - ChatGPT Images 2.5 16格连续动作与原生跳动字幕
  - 多尺度主间隙投影探测算法（解决行错位与字幕断裂）
  - 内容紧致包络裁剪（解决留白过大，填充率 96.5%）
  - 固定色差泛洪去底算法（FloodFill Fixed Range 保护镂空字与浅色笔画）
- [五、环境配置模版](.env.example)
  - 环境变量配置示例

---

## 快速开始

### 1. 激活 Conda 环境
```bash
conda activate weixinpy310mememiniapp
```

### 2. 启动本地/服务端 H5 测试服务
```bash
cd backend
python run.py
# 访问 http://localhost:8290 或公网 IP:8290 测试 GIF 切割与去底预览
```

---

## 仓库结构

```text
weixinpy310mememiniapp/
├── assets/
│   └── app_avatar.jpg                # 预生成的高清品牌/小程序头像
├── backend/
│   ├── app/
│   │   ├── api/                      # FastAPI 路由 (表情包切图、转 GIF 接口)
│   │   ├── core/                     # 核心算法引擎 (sprite_processor, prompt_templates)
│   │   └── main.py
│   ├── static/                       # H5 交互测试控制台 (实时 GIF 播放器、16帧检查器)
│   └── run.py
├── docs/
│   ├── ALGORITHM_AND_PIPELINE.md     # 核心算法剖析与避坑复盘实录
│   ├── MINIAPP_REGISTRATION_GUIDE.md # 命名、简介、备案与类目指导
│   ├── DOMAIN_DNS_CONFIG.md          # 域名规划与 DNS 解析
│   └── PRE_CONFIG_CHECKLIST.md       # 参数凭据与虚拟支付检查清单
├── templates/                        # 模板文件 (如虚拟支付道具 Excel 导入模板)
├── .env.example                      # 环境变量模板
└── README.md                         # 项目说明
```

