@echo off
chcp 65001 >nul
REM ========================================
REM 总承包AI智能评测系统 - 前端启动脚本
REM ========================================

echo ========================================
echo 🎨 总承包AI智能评测系统 - 前端服务
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

echo ✅ Python环境检查通过
echo.

echo ========================================
echo 🎯 启动前端服务...
echo ========================================
echo 🌐 服务地址: http://localhost:8100
echo 📄 项目列表: http://localhost:8100/project/frontend_improved.html
echo 🔍 配置管理: http://localhost:8100/config-manager.html
echo.
echo 浏览器将自动打开，如未打开请手动访问上述地址
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

REM 启动前端服务
cd frontend
python start_frontend.py
