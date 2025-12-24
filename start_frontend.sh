#!/bin/bash
# ========================================
# 总承包AI智能评测系统 - 前端启动脚本
# ========================================

echo "========================================"
echo "🎨 总承包AI智能评测系统 - 前端服务"
echo "========================================"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📍 项目根目录: $SCRIPT_DIR"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python3"
    exit 1
fi

echo "✅ Python环境检查通过"
echo ""

echo "========================================"
echo "🎯 启动前端服务..."
echo "========================================"
echo "🌐 服务地址: http://localhost:8100"
echo "📄 项目列表: http://localhost:8100/project/frontend_improved.html"
echo "🔍 配置管理: http://localhost:8100/config-manager.html"
echo ""
echo "浏览器将自动打开，如未打开请手动访问上述地址"
echo "按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 启动前端服务
cd frontend
python3 start_frontend.py
