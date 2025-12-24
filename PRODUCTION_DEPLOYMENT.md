# 生产环境快速部署指南

## 📦 一键打包生产部署包

### Linux/Mac

```bash
# 执行打包脚本
./build-production.sh
```

**打包结果**:
- 位置: `build/ai-review-system-YYYYMMDD-HHMMSS/`
- 格式: tar.gz 和 zip
- 大小: ~500KB (不含虚拟环境)

### Windows

```cmd
# 执行打包脚本
build-production.bat
```

**打包结果**:
- 位置: `build\ai-review-system-YYYYMMDD-HHMMSS\`
- 格式: zip
- 大小: ~500KB

---

## 📋 最小部署文件清单

### 必须文件 (11个核心文件)

```
ai-review-system/
├── backend/
│   ├── backend_service1126.py     # 主服务文件 (~130KB)
│   ├── app.py                      # 启动入口 (~2KB)
│   ├── config.py                   # 配置管理 (~6KB)
│   ├── advanced_document_parser.py # 文档解析 (~15KB)
│   ├── requirements.txt            # 依赖清单 (~1KB)
│   └── static/                     # 前端静态文件 (~100KB)
│       ├── config.js
│       ├── config-manager.html
│       └── project/
│           ├── frontend_improved.html
│           ├── project-detail.html
│           └── ai_pingce_result.html
├── .env                           # 环境配置 (~1KB)
├── start.sh / start.bat           # 启动脚本
└── README.md                      # 部署说明
```

**总大小**: ~255KB (不含虚拟环境)

---

## 🚀 生产环境部署步骤

### 1. 解压部署包

```bash
# Linux/Mac
tar -xzf ai-review-system-*.tar.gz
cd ai-review-system-*

# Windows
# 右键 - 解压到当前文件夹
cd ai-review-system-*
```

### 2. 配置环境

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
vim .env  # Linux/Mac
notepad .env  # Windows
```

**必须配置项**:
```env
DB_TYPE=mssql
DB_HOST=your-database-server
DB_PORT=1433
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=ai_doc_review

ZHIPU_API_KEY=your-api-key
```

### 3. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r backend/requirements.txt
```

### 4. 启动服务

```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

### 5. 访问系统

- 前端页面: http://server-ip:5000/
- API接口: http://server-ip:5000/api/projects

---

## 📊 部署包对比

| 方案 | 文件数 | 大小 | Python环境 | 适用场景 |
|------|--------|------|-----------|---------|
| **源码部署包** | 11个核心文件 | ~500KB | 需要安装 | 通用部署 |
| **含虚拟环境** | +venv目录 | ~200MB | 独立环境 | 生产服务器 |
| **PyInstaller打包** | 1个可执行文件 | ~50-100MB | 无需Python | 独立应用 |

---

## 📁 不需要的文件（开发环境特有）

以下文件在开发环境有用，但生产环境不需要：

### 可以删除的目录
- `.venv/` - 虚拟环境（生产环境重新创建）
- `__pycache__/` - Python缓存
- `.git/` - 版本控制
- `.idea/` - IDE配置
- `frontend/` - 前端源码（已整合到backend/static）
- `scripts/` - 开发工具
- `tools/` - 工具目录
- `docs/` - 详细文档
- `build/` - 构建文件
- `sql/` - 数据库脚本（首次部署后不需要）
- `test_*.py` - 测试脚本

### 可以删除的文件
- `start_frontend.*` - 已废弃的前端启动脚本
- `migrate_*.py` - 一次性迁移脚本
- `.gitignore` - Git配置
- `pytest.ini` - 测试配置

---

## ✅ 部署检查清单

### 部署前
- [ ] 服务器Python版本 >= 3.8
- [ ] 数据库服务正常运行
- [ ] 端口5000未被占用
- [ ] 防火墙允许5000端口
- [ ] 磁盘空间 >= 10GB
- [ ] 内存 >= 2GB

### 配置检查
- [ ] .env文件已创建
- [ ] 数据库连接信息已配置
- [ ] AI API密钥已配置
- [ ] 并发参数已调整

### 部署后验证
- [ ] 服务启动成功
- [ ] 前端页面可访问
- [ ] API接口正常响应
- [ ] 日志文件正常生成
- [ ] 数据库连接正常

---

## 🔧 快速命令参考

```bash
# 打包部署包
./build-production.sh

# 解压并部署
tar -xzf ai-review-system-*.tar.gz
cd ai-review-system-*
cp .env.example .env && vim .env
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
./start.sh

# 查看日志
tail -f logs/backend_service.log

# 停止服务
ps aux | grep app.py
kill <PID>
```

---

## 📚 详细文档

- **完整部署方案**: [docs/最小生产环境部署方案.md](docs/最小生产环境部署方案.md)
- **架构说明**: [统一服务架构说明.md](统一服务架构说明.md)
- **测试指南**: [统一服务测试指南.md](统一服务测试指南.md)

---

**最后更新**: 2025-12-24
**文档版本**: v1.0
