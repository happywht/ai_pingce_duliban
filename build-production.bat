@echo off
chcp 65001 >nul
REM ========================================
REM 生产环境部署包打包脚本 (Windows)
REM ========================================

setlocal enabledelayedexpansion

echo ========================================
echo 📦 总承包AI智能评测系统 - 生产部署打包
echo ========================================

set PROJECT_DIR=%cd%
set BUILD_DIR=%PROJECT_DIR%\build
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set mytime=%%a%%b)
set PACKAGE_NAME=ai-review-system-%mydate%-%mytime%
set PACKAGE_DIR=%BUILD_DIR%\%PACKAGE_NAME%

echo 📍 项目目录: %PROJECT_DIR%
echo 📦 构建目录: %PACKAGE_DIR%
echo.

REM 清理旧构建
if exist "%BUILD_DIR%" (
    echo 🧹 清理旧构建...
    rmdir /s /q "%BUILD_DIR%"
)

REM 创建构建目录
echo 🔨 创建构建目录...
mkdir "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%\backend"
mkdir "%PACKAGE_DIR%\backend\static"
mkdir "%PACKAGE_DIR%\backend\static\project"
mkdir "%PACKAGE_DIR%\logs"

echo.
echo ========================================
echo 📋 开始复制核心文件...
echo ========================================

REM 复制后端核心文件
echo 📁 复制后端核心文件...
copy /y "backend\backend_service1126.py" "%PACKAGE_DIR%\backend\" >nul
copy /y "backend\app.py" "%PACKAGE_DIR%\backend\" >nul
copy /y "backend\config.py" "%PACKAGE_DIR%\backend\" >nul
copy /y "backend\advanced_document_parser.py" "%PACKAGE_DIR%\backend\" >nul
copy /y "backend\requirements.txt" "%PACKAGE_DIR%\backend\" >nul
echo   ✅ 后端Python文件 ^(5个^)

REM 复制前端静态文件
echo 📁 复制前端静态文件...
copy /y "backend\static\config.js" "%PACKAGE_DIR%\backend\static\" >nul
copy /y "backend\static\config-manager.html" "%PACKAGE_DIR%\backend\static\" >nul
copy /y "backend\static\project\*.html" "%PACKAGE_DIR%\backend\static\project\" >nul
echo   ✅ 前端文件 ^(5个^)

REM 复制启动脚本
echo 📁 复制启动脚本...
copy /y "start_backend.sh" "%PACKAGE_DIR%\start.sh" >nul
copy /y "start_backend.bat" "%PACKAGE_DIR%\start.bat" >nul
echo   ✅ 启动脚本 ^(2个^)

REM 复制配置文件
echo 📁 复制配置模板...
copy /y ".env.sqlserver.example" "%PACKAGE_DIR%\.env.example" >nul
echo   ✅ 配置模板

echo.
echo ========================================
echo 📦 开始打包...
echo ========================================

cd "%BUILD_DIR%"

REM 创建zip包
echo 📦 创建zip压缩包...
powershell -command "Compress-Archive -Path '%PACKAGE_NAME%' -DestinationPath '%PACKAGE_NAME%.zip' -Force"

REM 计算文件大小
for %%F in ("%PACKAGE_NAME%.zip") do set SIZE=%%~zF
set /a SIZE_MB=%SIZE% / 1048576

echo.
echo ========================================
echo ✅ 打包完成！
echo ========================================
echo.
echo 📦 部署包信息:
echo   目录: %PACKAGE_DIR%
echo   Zip: %PACKAGE_NAME%.zip
echo.
echo 📋 文件清单:
echo   后端核心: 5个Python文件
echo   前端文件: 5个HTML/JS文件
echo   配置文件: 1个
echo   启动脚本: 2个
echo.
echo 🚀 部署方法:
echo   1. 解压: 右键 - 解压到 %PACKAGE_NAME%
echo   2. 配置: 复制 .env.example 为 .env 并编辑
echo   3. 启动: 双击 start.bat
echo.
echo 📍 部署包位置:
echo   %BUILD_DIR%\%PACKAGE_NAME%.zip
echo.

pause
