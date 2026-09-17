#!/usr/bin/env python3
"""
微信小程序审核模式 / 全量 AI 模式动态切换脚本
无需重启后端 uvicorn 进程，修改 SQLite 中的 app_settings 即时生效。

用法:
    python toggle_audit.py on       # 开启审核模式（降级为本地纯 PIL 图片动效处理，秒级出图，0% 深度合成）
    python toggle_audit.py off      # 关闭审核模式（恢复全量 16 帧 GPU 扩散大模型动图生成）
    python toggle_audit.py status   # 查看当前运行模式
"""

import sys
from pathlib import Path

# 将 backend 加入 sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import is_audit_mode_active, set_app_setting, get_app_setting
from app.core.prompt_templates import get_active_templates


def print_status():
    active = is_audit_mode_active()
    db_val = get_app_setting("audit_mode", "<未单独设置>")
    templates = get_active_templates()
    print("=" * 60)
    print(f"当前小程序运行模式: {'【 审核模式 (AUDIT MODE) 】' if active else '【 全量 AI 模式 (FULL AI MODE) 】'}")
    print(f"数据库 app_settings.audit_mode: {db_val}")
    print(f"出图流水线: {'本地 PIL 纯图像处理 (秒级出图，0% 深度合成)' if active else 'GPU 扩散大模型 (16帧完整动图生成)'}")
    print(f"当前模板示例 (第1个): {templates[0]['title']}")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print_status()
        print("\n使用提示:")
        print("  python toggle_audit.py on     -> 切换为审核模式")
        print("  python toggle_audit.py off    -> 切换为全量 AI 模式")
        print("  python toggle_audit.py status -> 查看当前状态")
        return

    arg = sys.argv[1].strip().lower()
    if arg in ("on", "1", "true", "enable", "audit"):
        set_app_setting("audit_mode", "true")
        print("\n>>> 已切换为：【 审核模式 (AUDIT MODE) 】<<<")
        print_status()
    elif arg in ("off", "0", "false", "disable", "ai", "full"):
        set_app_setting("audit_mode", "false")
        print("\n>>> 已切换为：【 全量 AI 模式 (FULL AI MODE) 】<<<")
        print_status()
    elif arg in ("status", "info", "check"):
        print_status()
    else:
        print(f"未知参数: {sys.argv[1]}")
        print("有效参数为: on / off / status")
        sys.exit(1)


if __name__ == "__main__":
    main()
