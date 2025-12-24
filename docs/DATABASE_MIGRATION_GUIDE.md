# 数据库迁移指南：MySQL → SQL Server

## 概述

本指南详细说明了如何将项目数据库从MySQL迁移到SQL Server。

## 迁移前准备

### 1. 安装SQL Server相关依赖

```bash
# 安装pyodbc（SQL Server的Python驱动）
pip install pyodbc

# 安装SQL Server ODBC Driver 17 for SQL Server
# 下载地址：https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

### 2. 安装SQL Server

确保已安装SQL Server（Express版或完整版），并且：
- 启用了SQL Server身份验证
- 启用了TCP/IP协议
- 防火墙允许1433端口访问

### 3. 备份现有数据

```bash
# 备份MySQL数据
mysqldump -u root -p project_eval > mysql_backup.sql
```

## 迁移步骤

### 1. 配置SQL Server环境

```bash
# 复制SQL Server配置模板
cp .env.sqlserver.example .env

# 编辑配置文件，设置SQL Server连接参数
# DB_TYPE=mssql
# DB_HOST=localhost
# DB_PORT=1433
# DB_USER=sa
# DB_PASSWORD=YourPassword
# DB_NAME=project_eval
```

### 2. 创建SQL Server数据库

```bash
# 运行数据库初始化脚本
python scripts/create_database_sqlserver.py

# 验证数据库创建
python scripts/create_database_sqlserver.py --verify

# 测试连接
python scripts/create_database_sqlserver.py --test
```

### 3. 数据迁移（可选）

如果需要迁移现有数据，可以使用以下方法：

#### 方法一：使用ETL工具
1. 使用SQL Server Migration Assistant (SSMA)
2. 使用第三方ETL工具如Talend、Apache NiFi

#### 方法二：自定义脚本
创建数据迁移脚本，导出MySQL数据并导入SQL Server。

### 4. 验证系统功能

```bash
# 启动后端服务
python backend_service1126.py

# 检查日志输出，确认数据库连接成功
# 测试API接口是否正常工作
```

## 主要变更说明

### 1. 数据库类型适配

**字符串字段：**
- MySQL: `VARCHAR`
- SQL Server: `NVARCHAR`（支持Unicode/中文）

**文本字段：**
- MySQL: `TEXT`, `LONGTEXT`
- SQL Server: `NVARCHAR(MAX)`

**时间字段：**
- MySQL: `DATETIME`
- SQL Server: `DATETIME2`（更高精度）

### 2. 连接配置变更

**连接字符串：**
```python
# MySQL
mysql+pymysql://user:pass@host:3306/dbname

# SQL Server
mssql+pyodbc://user:pass@host:1433/dbname?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```

### 3. SQL语法差异

**表创建：**
```sql
-- MySQL
CREATE TABLE test (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) CHARACTER SET utf8mb4
);

-- SQL Server
CREATE TABLE test (
    id NVARCHAR(100) PRIMARY KEY,
    name NVARCHAR(255)
);
```

## 配置详解

### 环境变量配置

| 变量名 | MySQL值 | SQL Server值 | 说明 |
|--------|----------|--------------|------|
| DB_TYPE | mysql | mssql | 数据库类型 |
| DB_PORT | 3306 | 1433 | 默认端口 |
| DB_CHARSET | utf8mb4 | N/A | SQL Server默认支持Unicode |

### SQLAlchemy连接池配置

```python
# SQL Server特定配置
app.config['SQLALCHEMY_POOL_RECYCLE'] = 3600
app.config['SQLALCHEMY_POOL_SIZE'] = 5
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 10
app.config['SQLALCHEMY_POOL_PRE_PING'] = True

engine_options = {
    "connect_args": {
        "timeout": 30,
        "TrustServerCertificate": "yes"
    }
}
```

## 故障排除

### 1. 连接失败

**常见错误：**
```
InterfaceError: (pyodbc.InterfaceError) ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] Data source name not found')
```

**解决方案：**
- 确保已安装SQL Server ODBC Driver 17
- 检查ODBC驱动是否正确注册

### 2. 字符编码问题

**问题：** 中文字符显示为乱码

**解决方案：**
- 使用NVARCHAR而不是VARCHAR
- 确保连接字符串包含Unicode支持参数

### 3. 性能问题

**优化建议：**
- 调整连接池大小
- 定期更新统计信息
- 为查询字段添加索引

## 回滚方案

如果需要回滚到MySQL：

```bash
# 1. 恢复环境配置
cp .env.example .env
# 设置DB_TYPE=mysql及相关配置

# 2. 恢复数据库（如果需要）
mysql -u root -p < mysql_backup.sql

# 3. 重新启动服务
python backend_service1126.py
```

## 测试验证

迁移完成后，进行以下测试：

1. **数据库连接测试**
2. **API接口功能测试**
3. **并发控制功能测试**
4. **文件上传和处理测试**
5. **数据持久化测试**

## 注意事项

1. **性能对比：** SQL Server在某些查询场景下性能可能不同，需要测试验证
2. **功能兼容性：** 确保所有功能在SQL Server下正常工作
3. **备份策略：** 建立SQL Server的备份和恢复策略
4. **监控告警：** 配置SQL Server的监控和告警

---

**完成迁移后，请删除此文档或将其移至归档文件夹。**