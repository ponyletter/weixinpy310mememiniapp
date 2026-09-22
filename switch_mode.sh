#!/usr/bin/env bash
# ==============================================================================
# 微信小程序运行模式极速切换脚本（审核模式 vs 全量 AI 模式）
# 无需重启后端服务进程，修改 SQLite 配置即时生效！
#
# 使用方法:
#   ./switch_mode.sh on       # 开启审核模式 (本地纯 PIL 图片处理，0% 深度合成，合规秒级过审)
#   ./switch_mode.sh off      # 开启全量 AI 模式 (调用 CPA / GPU 扩散大模型出图)
#   ./switch_mode.sh status   # 查看当前运行模式与流水线状态
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="/root/miniconda3/envs/weixinpy310mememiniapp/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
  PYTHON_EXEC="$(which python3)"
fi

$PYTHON_EXEC "$PROJECT_ROOT/backend/toggle_audit.py" "$@"
