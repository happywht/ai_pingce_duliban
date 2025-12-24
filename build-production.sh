#!/bin/bash
# ========================================
# 生产环境部署包打包脚本
# ========================================

set -e  # 遇到错误立即退出

echo "========================================"
echo "📦 总承包AI智能评测系统 - 生产部署打包"
echo "========================================"

# 获取当前目录
PROJECT_DIR="$(pwd)"
BUILD_DIR="${PROJECT_DIR}/build"
PACKAGE_NAME="ai-review-system-$(date +%Y%m%d-%H%M%S)"
PACKAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}"

echo "📍 项目目录: ${PROJECT_DIR}"
echo "📦 构建目录: ${PACKAGE_DIR}"
echo ""

# 清理旧构建
if [ -d "${BUILD_DIR}" ]; then
    echo "🧹 清理旧构建..."
    rm -rf "${BUILD_DIR}"
fi

# 创建构建目录
echo "🔨 创建构建目录..."
mkdir -p "${PACKAGE_DIR}"

echo ""
echo "========================================"
echo "📋 开始复制核心文件..."
echo "========================================"

# 1. 复制后端核心目录
echo "📁 复制后端核心文件..."
mkdir -p "${PACKAGE_DIR}/backend"

cp backend/backend_service1126.py "${PACKAGE_DIR}/backend/"
cp backend/app.py "${PACKAGE_DIR}/backend/"
cp backend/config.py "${PACKAGE_DIR}/backend/"
cp backend/advanced_document_parser.py "${PACKAGE_DIR}/backend/"
cp backend/requirements.txt "${PACKAGE_DIR}/backend/"
echo "  ✅ 后端Python文件 (5个)"

# 2. 复制前端静态文件
echo "📁 复制前端静态文件..."
mkdir -p "${PACKAGE_DIR}/backend/static"
mkdir -p "${PACKAGE_DIR}/backend/static/project"

cp backend/static/config.js "${PACKAGE_DIR}/backend/static/"
cp backend/static/config-manager.html "${PACKAGE_DIR}/backend/static/"
cp backend/static/project/*.html "${PACKAGE_DIR}/backend/static/project/"
echo "  ✅ 前端文件 (5个)"

# 3. 复制启动脚本
echo "📁 复制启动脚本..."
cp start_backend.sh "${PACKAGE_DIR}/start.sh"
cp start_backend.bat "${PACKAGE_DIR}/start.bat"
chmod +x "${PACKAGE_DIR}/start.sh"
echo "  ✅ 启动脚本 (2个)"

# 4. 复制配置文件
echo "📁 复制配置模板..."
cp .env.sqlserver.example "${PACKAGE_DIR}/.env.example"
echo "  ✅ 配置模板"

# 5. 创建生产环境README
echo "📁 创建部署说明..."
cat > "${PACKAGE_DIR}/README.md" << 'EOF'
# 总承包AI智能评测系统 - 生产环境部署包

## 📋 部署包说明

本部署包包含系统运行所需的所有核心文件。

**部署日期**: 生成时自动填充
**版本信息**: v1.0 (统一服务架构)

---

## 🚀 快速部署

### 第一步：解压部署包

```bash
tar -xzf ai-review-system-*.tar.gz
cd ai-review-system-*
```

### 第二步：配置环境

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必须配置的参数**:
```env
# 数据库配置
DB_TYPE=mssql
DB_HOST=your-database-server
DB_PORT=1433
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=ai_doc_review

# AI配置
ZHIPU_API_KEY=your-api-key
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/anthropic
ZHIPU_MODEL=glm-4.5
```

### 第三步：安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装Python依赖
pip install -r backend/requirements.txt
```

### 第四步：启动服务

**Linux/Mac**:
```bash
./start.sh
```

**Windows**:
```cmd
start.bat
```

### 第五步：访问系统

- 🌐 前端页面: http://your-server:5000/
- 📊 API接口: http://your-server:5000/api/projects
- ⚙️ 配置管理: http://your-server:5000/config-manager.html

---

## 📁 目录结构

```
ai-review-system/
├── backend/                    # 后端核心目录
│   ├── backend_service1126.py  # 主服务文件
│   ├── app.py                  # 启动入口
│   ├── config.py               # 配置管理
│   ├── advanced_document_parser.py  # 文档解析
│   ├── requirements.txt        # Python依赖
│   └── static/                 # 前端静态文件
│       ├── config.js
│       ├── config-manager.html
│       └── project/
│           ├── frontend_improved.html
│           ├── project-detail.html
│           └── ai_pingce_result.html
│
├── .env.example                # 配置模板
├── start.sh                    # Linux/Mac启动脚本
├── start.bat                   # Windows启动脚本
└── README.md                   # 本文件
```

---

## ⚙️ 系统要求

### 最低配置
- **操作系统**: Linux (Ubuntu 20.04+) / Windows Server 2016+
- **Python**: 3.8 或更高版本
- **内存**: 2GB RAM
- **磁盘**: 10GB 可用空间
- **数据库**: SQL Server / MySQL / PostgreSQL

### 推荐配置
- **操作系统**: Ubuntu 22.04 LTS
- **Python**: 3.10+
- **内存**: 4GB+ RAM
- **磁盘**: 50GB+ SSD
- **数据库**: SQL Server 2019+ / MySQL 8.0+

---

## 🔧 常见问题

### 1. 端口被占用

**问题**: 启动时提示 "Address already in use"

**解决**:
```bash
# Linux/Mac
lsof -i :5000
kill -9 <PID>

# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### 2. Python依赖安装失败

**问题**: pip install 报错

**解决**:
```bash
# 升级pip
pip install --upgrade pip

# 使用国内镜像
pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 数据库连接失败

**问题**: "Connection refused"

**解决**:
1. 检查 `.env` 配置是否正确
2. 确认数据库服务运行正常
3. 检查防火墙和网络连接
4. 验证数据库用户权限

### 4. 静态文件404

**问题**: 前端页面显示 "404 Not Found"

**解决**:
```bash
# 检查文件是否存在
ls backend/static/project/

# 确认在backend目录启动
cd backend
python app.py
```

---

## 📊 服务管理

### 启动服务

```bash
# 方式1: 使用启动脚本
./start.sh

# 方式2: 手动启动
cd backend
python app.py
```

### 停止服务

```bash
# 按 Ctrl+C 停止服务
# 或查找进程并kill
ps aux | grep app.py
kill <PID>
```

### 重启服务

```bash
# 停止后重新启动
./start.sh
```

### 查看日志

```bash
# 实时查看日志
tail -f logs/backend_service.log

# 查看错误日志
tail -f logs/backend_error.log
```

---

## 🔐 安全建议

### 生产环境安全配置

1. **修改默认端口**
   - 编辑 `backend/app.py`
   - 修改 `port=5000` 为其他端口

2. **配置HTTPS**
   - 使用Nginx反向代理
   - 配置SSL证书

3. **数据库安全**
   - 使用强密码
   - 限制数据库访问IP
   - 定期备份数据

4. **环境变量**
   - 不要将 `.env` 提交到版本控制
   - 定期更换API密钥

---

## 📈 性能优化

### 推荐配置

**小规模** (< 50用户):
- 当前配置即可
- 使用SQLite或MySQL

**中等规模** (50-200用户):
- 增加并发数: `MAX_CONCURRENT_TASKS=5`
- 使用PostgreSQL
- 配置Nginx反向代理

**大规模** (> 200用户):
- 使用负载均衡
- 配置Redis缓存
- 数据库读写分离
- 部署多实例

---

## 🆘 技术支持

### 日志位置

- **运行日志**: `logs/backend_service.log`
- **错误日志**: `logs/backend_error.log`

### 调试模式

启用调试模式查看详细日志：
```bash
cd backend
export FLASK_ENV=development
python app.py
```

### 联系方式

- 技术文档: 查看项目完整文档
- Issue反馈: GitHub Issues
- 邮件支持: 776815438@qq.com

---

## 📝 更新日志

### v1.0 (2025-12-24)
- ✨ 统一服务架构（前端+后端集成）
- ✨ 支持AI智能文档评测
- ✨ 支持多种文档格式（PDF/Word/Excel/OCR）
- ✨ 完善的日志系统
- ✨ 简化的部署流程

---

## 📄 许可证

本项目为企业内部使用系统，保留所有权利。

---

**部署包版本**: v1.0
**生成时间**: 自动填充
**架构类型**: 统一Flask服务
EOF

echo "  ✅ README.md"

# 6. 创建日志目录
echo "📁 创建日志目录..."
mkdir -p "${PACKAGE_DIR}/logs"
echo "  ✅ logs/"

# 7. 创建快速部署脚本
echo "📁 创建快速部署脚本..."
cat > "${PACKAGE_DIR}/deploy.sh" << 'EOF'
#!/bin/bash
# 快速部署脚本

echo "🚀 开始部署..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到Python3，请先安装"
    exit 1
fi

echo "✅ Python版本: $(python3 --version)"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -q -r backend/requirements.txt

# 检查配置
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env，从模板创建..."
    cp .env.example .env
    echo "❗ 请编辑 .env 配置数据库连接"
    echo "   vim .env"
    exit 1
fi

echo "✅ 配置检查通过"

# 创建日志目录
mkdir -p logs

echo ""
echo "========================================"
echo "🎯 部署完成！"
echo "========================================"
echo ""
echo "启动服务:"
echo "  ./start.sh"
echo ""
echo "访问地址:"
echo "  http://localhost:5000/"
echo ""
EOF
chmod +x "${PACKAGE_DIR}/deploy.sh"
echo "  ✅ deploy.sh"

echo ""
echo "========================================"
echo "📦 开始打包..."
echo "========================================"

# 打包
cd "${BUILD_DIR}"
echo "📦 创建tar.gz压缩包..."
tar -czf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"

echo "📦 创建zip压缩包..."
zip -rq "${PACKAGE_NAME}.zip" "${PACKAGE_NAME}"

# 计算文件大小
TAR_SIZE=$(du -h "${PACKAGE_NAME}.tar.gz" | cut -f1)
ZIP_SIZE=$(du -h "${PACKAGE_NAME}.zip" | cut -f1)

# 统计文件
FILE_COUNT=$(find "${PACKAGE_NAME}" -type f | wc -l)

echo ""
echo "========================================"
echo "✅ 打包完成！"
echo "========================================"
echo ""
echo "📦 部署包信息:"
echo "  目录: ${PACKAGE_DIR}"
echo "  文件数: ${FILE_COUNT}"
echo "  Tar.gz: ${PACKAGE_NAME}.tar.gz (${TAR_SIZE})"
echo "  Zip: ${PACKAGE_NAME}.zip (${ZIP_SIZE})"
echo ""
echo "📋 文件清单:"
echo "  后端核心: 5个Python文件"
echo "  前端文件: 5个HTML/JS文件"
echo "  配置文件: 1个"
echo "  启动脚本: 2个"
echo "  部署脚本: 2个"
echo ""
echo "🚀 部署方法:"
echo "  1. 解压: tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  2. 配置: cd ${PACKAGE_NAME} && cp .env.example .env && vim .env"
echo "  3. 部署: ./deploy.sh"
echo "  4. 启动: ./start.sh"
echo ""
echo "📍 部署包位置:"
echo "  ${BUILD_DIR}/${PACKAGE_NAME}.tar.gz"
echo "  ${BUILD_DIR}/${PACKAGE_NAME}.zip"
echo ""
