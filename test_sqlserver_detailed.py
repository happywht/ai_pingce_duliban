#!/usr/bin/env python3
"""
SQL Server 详细连接测试和诊断工具
包含ODBC驱动检查和多种连接方式测试
"""

import os
import sys
import urllib.parse
import subprocess
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def check_odbc_drivers():
    """检查系统中可用的ODBC驱动"""
    print("🔍 检查系统ODBC驱动...")

    try:
        import pyodbc
        drivers = pyodbc.drivers()

        print(f"📋 找到的ODBC驱动:")
        for i, driver in enumerate(drivers, 1):
            print(f"   {i}. {driver}")

        # 检查SQL Server驱动
        sqlserver_drivers = [d for d in drivers if 'sql server' in d.lower()]

        if sqlserver_drivers:
            print(f"✅ 找到SQL Server驱动:")
            for driver in sqlserver_drivers:
                print(f"   🚀 {driver}")
            return True, sqlserver_drivers
        else:
            print(f"❌ 未找到SQL Server驱动")
            return False, []

    except ImportError:
        print(f"❌ pyodbc 未安装，请运行: pip install pyodbc")
        return False, []

def install_odbc_driver_guidance():
    """提供ODBC驱动安装指导"""
    print(f"\n📖 SQL Server ODBC Driver 安装指导:")
    print(f"=" * 60)
    print(f"方法1: 使用Windows安装包")
    print(f"   1. 访问: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
    print(f"   2. 下载 'ODBC Driver 17 for SQL Server'")
    print(f"   3. 运行安装程序并按照向导完成安装")
    print(f"")
    print(f"方法2: 使用Chocolatey包管理器")
    print(f"   1. 安装Chocolatey: https://chocolatey.org/install")
    print(f"   2. 运行: choco install sqlserver-odbcdriver")
    print(f"")
    print(f"方法3: 使用Scoop包管理器")
    print(f"   1. 安装Scoop: https://scoop.sh/")
    print(f"   2. 运行: scoop install mssql-odbc-driver")
    print(f"=" * 60)

def test_sqlalchemy_connection():
    """使用SQLAlchemy测试连接"""
    print(f"\n🔍 使用SQLAlchemy测试连接...")

    # 连接参数
    DB_HOST = '10.1.24.73'
    DB_PORT = '1433'
    DB_NAME = 'ai_doc_review'
    DB_USER = 'sys_ai'
    DB_PASSWORD = urllib.parse.quote_plus('Cjy@2025Ai')

    try:
        from sqlalchemy import create_engine, text

        # SQLAlchemy连接字符串
        db_uri = (f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                   f"?driver=SQL+Server+Native+Client+11.0"
                   f"&TrustServerCertificate=yes")

        print(f"📡 SQLAlchemy URI: {db_uri}")

        # 创建引擎
        engine = create_engine(
            db_uri,
            pool_pre_ping=True,
            pool_timeout=30,
            echo=False  # 设置为True可以看到SQL查询
        )

        # 测试连接
        with engine.connect() as conn:
            print(f"✅ SQLAlchemy连接成功！")

            # 执行简单查询
            result = conn.execute(text("SELECT @@VERSION as version, DB_NAME() as db_name"))
            row = result.fetchone()

            print(f"📋 SQL Server版本: {row[0][:80]}...")
            print(f"💾 当前数据库: {row[1]}")

            # 获取数据库信息
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as table_count
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """))
            table_info = result.fetchone()
            print(f"📊 数据库表数量: {table_info[0]}")

            engine.dispose()
            return True

    except ImportError:
        print(f"❌ SQLAlchemy未安装，请运行: pip install sqlalchemy")
        return False
    except Exception as e:
        print(f"❌ SQLAlchemy连接失败: {e}")
        return False

def test_pymssql_connection():
    """使用pymssql测试连接（备用方案）"""
    print(f"\n🔍 尝试使用pymssql连接（备用方案）...")

    DB_HOST = '10.1.24.73'
    DB_PORT = 1433
    DB_NAME = 'ai_doc_review'
    DB_USER = 'sys_ai'
    DB_PASSWORD = 'Cjy@2025Ai'

    try:
        import pymssql

        print(f"📡 连接参数: {DB_HOST}:{DB_PORT}, 数据库: {DB_NAME}")

        # 连接数据库
        conn = pymssql.connect(
            server=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            as_dict=True
        )

        print(f"✅ pymssql连接成功！")

        cursor = conn.cursor()

        # 测试查询
        cursor.execute("SELECT @@VERSION as version, DB_NAME() as db_name")
        row = cursor.fetchone()

        print(f"📋 SQL Server版本: {row['version'][:80]}...")
        print(f"💾 当前数据库: {row['db_name']}")

        # 获取表信息
        cursor.execute("""
            SELECT COUNT(*) as table_count
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        table_info = cursor.fetchone()
        print(f"📊 数据库表数量: {table_info['table_count']}")

        cursor.close()
        conn.close()
        return True

    except ImportError:
        print(f"❌ pymssql未安装，请运行: pip install pymssql")
        return False
    except Exception as e:
        print(f"❌ pymssql连接失败: {e}")
        return False

def test_network_connectivity():
    """测试网络连接性"""
    print(f"\n🌐 测试网络连接性...")

    import socket

    try:
        # 测试TCP连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10秒超时

        result = sock.connect_ex(('10.1.24.73', 1433))

        if result == 0:
            print(f"✅ 网络连接成功！")
            sock.close()
            return True
        else:
            print(f"❌ 网络连接失败，错误码: {result}")
            return False

    except Exception as e:
        print(f"❌ 网络测试失败: {e}")
        return False

def create_env_file():
    """创建SQL Server环境变量文件"""
    print(f"\n📝 创建SQL Server配置文件...")

    env_content = f"""# SQL Server 数据库配置
DB_TYPE=mssql
DB_HOST=10.1.24.73
DB_PORT=1433
DB_USER=sys_ai
DB_PASSWORD=Cjy@2025Ai
DB_NAME=ai_doc_review

# AI服务配置
ZHIPU_API_KEY=your_api_key_here
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/anthropic
ZHIPU_MODEL=glm-4.5

# 系统配置
MAX_CONCURRENT_PROJECTS=3

# Flask配置
FLASK_ENV=development
FLASK_DEBUG=true
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
"""

    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"✅ 已创建 .env 文件")
        print(f"📝 配置内容已写入，请根据需要修改")
        return True
    except Exception as e:
        print(f"❌ 创建 .env 文件失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 SQL Server 详细连接诊断工具")
    print("=" * 60)

    # 1. 检查ODBC驱动
    drivers_ok, sqlserver_drivers = check_odbc_drivers()

    if not drivers_ok:
        print(f"🔧 需要安装SQL Server ODBC驱动")
        install_odbc_driver_guidance()

        # 询问是否继续
        try:
            continue_test = input(f"\n❓ 是否继续进行其他连接测试？(y/n): ").lower().strip()
            if continue_test not in ['y', 'yes']:
                return
        except KeyboardInterrupt:
            print(f"\n用户取消操作")
            return

    # 2. 测试网络连接
    network_ok = test_network_connectivity()
    if not network_ok:
        print(f"❌ 网络连接失败，请检查:")
        print(f"   1. SQL Server服务器是否运行")
        print(f"   2. 防火墙是否允许1433端口")
        print(f"   3. 网络连接是否正常")

    # 3. 测试数据库连接
    print(f"\n🔍 开始数据库连接测试...")

    # 尝试SQLAlchemy连接
    sqlalchemy_ok = test_sqlalchemy_connection()

    # 如果SQLAlchemy失败，尝试pymssql
    if not sqlalchemy_ok:
        print(f"\n🔄 尝试使用pymssql...")
        pymssql_ok = test_pymssql_connection()
    else:
        pymssql_ok = False

    # 4. 总结测试结果
    print(f"\n" + "=" * 60)
    print(f"📊 测试结果总结:")
    print(f"   🔍 ODBC驱动: {'✅ 正常' if drivers_ok else '❌ 需要安装'}")
    print(f"   🌐 网络连接: {'✅ 正常' if network_ok else '❌ 连接失败'}")
    print(f"   🔗 SQLAlchemy: {'✅ 正常' if sqlalchemy_ok else '❌ 连接失败'}")
    print(f"   🔄 pymssql: {'✅ 正常' if pymssql_ok else '❌ 未测试'}")

    if sqlalchemy_ok or pymssql_ok:
        print(f"\n✅ 至少有一种连接方式正常！")

        # 询问是否创建配置文件
        try:
            create_env = input(f"\n❓ 是否创建 .env 配置文件？(y/n): ").lower().strip()
            if create_env in ['y', 'yes']:
                create_env_file()
        except KeyboardInterrupt:
            print(f"\n用户取消操作")

        print(f"\n🎉 测试完成！SQL Server连接已准备就绪。")
        print(f"💡 下一步: 运行 python scripts/create_database_sqlserver.py")

    else:
        print(f"\n❌ 所有连接方式都失败，请检查配置。")
        print(f"📋 故障排除建议:")
        print(f"   1. 安装SQL Server ODBC Driver 17")
        print(f"   2. 确认SQL Server服务正常运行")
        print(f"   3. 检查网络连接和防火墙设置")
        print(f"   4. 验证用户名和密码是否正确")

if __name__ == "__main__":
    main()