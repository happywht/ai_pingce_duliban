@echo off
chcp 65001 >nul
REM ========================================
REM 总承包AI智能评测系统 - 统一服务启动脚本
REM ========================================

echo ========================================
echo 🚀 总承包AI智能评测系统 - 统一服务
echo ========================================

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo 📍 项目根目录: %SCRIPT_DIR%
echo.

REM 检查Python环境
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo ✅ 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
) else (
    echo ⚠️  未检测到虚拟环境，使用系统Python
)

REM 检查.env配置文件
if not exist ".env" (
    echo ❌ 错误: 未找到.env配置文件
    echo.
    echo 请先创建配置文件：
    echo   copy .env.sqlserver.example .env
    echo   然后编辑.env配置数据库连接信息
    pause
    exit /b 1
)

echo ✅ 配置文件检查通过
echo.

REM 检查依赖
echo 🔍 检查Python依赖...
python -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  依赖未安装，正在安装...
    pip install -r backend\requirements.txt
)

echo.
echo ========================================
echo 🎯 启动统一服务 (前端 + 后端API)...
echo ========================================
echo 🌐 服务地址: http://localhost:5000
echo 📄 前端页面: http://localhost:5000/project/frontend_improved.html
echo 📊 API接口: http://localhost:5000/api/projects
echo 🔍 配置管理: http://localhost:5000/config-manager.html
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

REM 启动后端服务
cd backend
python app.py
pause
