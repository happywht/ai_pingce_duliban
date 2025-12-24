#!/bin/bash
# ========================================
# 总承包AI智能评测系统 - 统一服务启动脚本
# ========================================

echo "========================================"
echo "🚀 总承包AI智能评测系统 - 统一服务"
echo "========================================"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python3"
    exit 1
fi

echo "📍 项目根目录: $SCRIPT_DIR"
echo ""

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "✅ 检测到虚拟环境，正在激活..."
    source .venv/bin/activate
else
    echo "⚠️  未检测到虚拟环境，使用系统Python"
fi

# 检查.env配置文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未找到.env配置文件"
    echo ""
    echo "请先创建配置文件："
    echo "  cp .env.sqlserver.example .env"
    echo "  然后编辑.env配置数据库连接信息"
    exit 1
fi

echo "✅ 配置文件检查通过"
echo ""

# 检查依赖
echo "🔍 检查Python依赖..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  依赖未安装，正在安装..."
    pip install -r backend/requirements.txt
fi

echo ""
echo "========================================"
echo "🎯 启动统一服务 (前端 + 后端API)..."
echo "========================================"
echo "🌐 服务地址: http://localhost:5000"
echo "📄 前端页面: http://localhost:5000/project/frontend_improved.html"
echo "📊 API接口: http://localhost:5000/api/projects"
echo "🔍 配置管理: http://localhost:5000/config-manager.html"
echo ""
echo "按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 启动后端服务
cd backend
python3 app.py
