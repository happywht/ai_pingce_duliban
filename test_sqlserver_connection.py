#!/usr/bin/env python3
"""
SQL Server 连接测试
测试连接到指定的 SQL Server 实例
"""

import os
import sys
import urllib.parse
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_sqlserver_connection():
    """测试SQL Server连接"""

    # 设置连接参数
    DB_HOST = '10.1.24.73'
    DB_PORT = '1433'
    DB_NAME = 'ai_doc_review'
    DB_USER = 'sys_ai'
    DB_PASSWORD = 'Cjy@2025Ai'

    print(f"🔧 开始测试 SQL Server 连接...")
    print(f"📍 服务器: {DB_HOST}:{DB_PORT}")
    print(f"💾 数据库: {DB_NAME}")
    print(f"👤 用户名: {DB_USER}")

    # 方法1: 使用 pyodbc 直接测试
    print(f"\n🔍 方法1: 使用 pyodbc 直接连接...")
    try:
        import pyodbc

        # SQL Server 连接字符串
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={DB_HOST},{DB_PORT};"
            f"DATABASE={DB_NAME};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )

        print(f"📡 连接字符串: {conn_str}")

        # 建立连接
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        print(f"✅ pyodbc 连接成功！")

        # 测试简单查询
        cursor.execute("SELECT @@VERSION AS version")
        version_info = cursor.fetchone()
        print(f"📋 SQL Server 版本: {version_info[0][:80]}...")

        # 测试数据库信息
        cursor.execute("SELECT DB_NAME() AS current_db")
        db_info = cursor.fetchone()
        print(f"💾 当前数据库: {db_info[0]}")

        # 列出表（如果有）
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        table_count = cursor.fetchone()
        print(f"📊 表数量: {table_count[0]}")

        # 关闭连接
        cursor.close()
        conn.close()

        return True

    except ImportError:
        print(f"❌ pyodbc 未安装，请运行: pip install pyodbc")
        return False
    except Exception as e:
        print(f"❌ pyodbc 连接失败: {e}")
        return False

    # 方法2: 使用 SQLAlchemy 测试
    print(f"\n🔍 方法2: 使用 SQLAlchemy 连接测试...")
    try:
        from sqlalchemy import create_engine, text

        # 编码密码
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

        # SQLAlchemy 连接字符串
        db_uri = (f"mssql+pyodbc://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                   f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes")

        print(f"📡 SQLAlchemy URI: {db_uri}")

        # 创建引擎
        engine = create_engine(
            db_uri,
            pool_pre_ping=True,
            pool_timeout=30
        )

        # 测试连接
        with engine.connect() as conn:
            print(f"✅ SQLAlchemy 连接成功！")

            # 执行查询
            result = conn.execute(text("SELECT @@VERSION"))
            version = result.fetchone()[0]
            print(f"📋 SQL Server 版本: {version[:80]}...")

            # 测试表存在性
            tables = conn.execute(text("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """))
            count = tables.fetchone()[0]
            print(f"📊 表数量: {count}")

        engine.dispose()
        return True

    except ImportError:
        print(f"❌ SQLAlchemy 未安装，请运行: pip install sqlalchemy")
        return False
    except Exception as e:
        print(f"❌ SQLAlchemy 连接失败: {e}")
        return False

def test_project_models():
    """测试项目模型表是否存在"""
    try:
        import pyodbc

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER=10.1.24.73,1433;"
            f"DATABASE=ai_doc_review;"
            f"UID=sys_ai;"
            f"PWD=Cjy@2025Ai;"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        print(f"\n🔍 检查项目相关表...")

        # 检查表是否存在
        expected_tables = ['project', 'project_evaluation', 'project_file']
        for table in expected_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table}'")
                exists = cursor.fetchone()[0] > 0
                if exists:
                    print(f"   ✅ {table} 表存在")

                    # 获取表结构信息
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = '{table}'
                    """)
                    column_count = cursor.fetchone()[0]
                    print(f"      📋 字段数量: {column_count}")
                else:
                    print(f"   ❌ {table} 表不存在")
            except Exception as e:
                print(f"   ❌ 检查 {table} 表失败: {e}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ 检查模型表失败: {e}")

def create_sample_data():
    """创建示例数据（如果需要）"""
    try:
        import pyodbc

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER=10.1.24.73,1433;"
            f"DATABASE=ai_doc_review;"
            f"UID=sys_ai;"
            f"PWD=Cjy@2025Ai;"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        print(f"\n🔧 创建示例项目数据...")

        # 创建项目表（如果不存在）
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='project' AND xtype='U')
            CREATE TABLE project (
                id NVARCHAR(100) PRIMARY KEY,
                project_code NVARCHAR(100),
                project_name NVARCHAR(255),
                last_update DATETIME2 DEFAULT GETDATE()
            )
        """)

        # 创建项目评测表
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='project_evaluation' AND xtype='U')
            CREATE TABLE project_evaluation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                project_id NVARCHAR(100) NOT NULL,
                task_id NVARCHAR(100) DEFAULT 'DEFAULT_TASK',
                status NVARCHAR(50) DEFAULT 'IDLE',
                rules_config NVARCHAR(MAX),
                evaluation_result NVARCHAR(MAX),
                check_date NVARCHAR(20),
                check_person_name NVARCHAR(100),
                created_at DATETIME2 DEFAULT GETDATE(),
                updated_at DATETIME2 DEFAULT GETDATE()
            )
        """)

        # 插入示例项目
        sample_projects = [
            ('proj_001', 'PRJ001', '测试项目1'),
            ('proj_002', 'PRJ002', '测试项目2'),
            ('proj_003', 'PRJ003', '总承包项目示例')
        ]

        for proj_id, code, name in sample_projects:
            cursor.execute("""
                INSERT INTO project (id, project_code, project_name)
                VALUES (?, ?, ?)
            """, (proj_id, code, name))

        conn.commit()
        print(f"✅ 创建了 {len(sample_projects)} 个示例项目")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ 创建示例数据失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 SQL Server 连接测试工具")
    print("=" * 50)

    # 连接测试
    connection_ok = test_sqlserver_connection()

    if connection_ok:
        # 模型测试
        test_project_models()

        # 询问是否创建示例数据
        try:
            create_data = input("\n💡 是否创建示例数据？(y/n): ").lower().strip()
            if create_data in ['y', 'yes']:
                create_sample_data()
        except KeyboardInterrupt:
            print(f"\n用户取消操作")

    print(f"\n🎉 测试完成！")

    if connection_ok:
        print(f"✅ SQL Server 连接成功，可以开始使用系统")
        print(f"💡 下一步: 运行 python scripts/create_database_sqlserver.py")
    else:
        print(f"❌ SQL Server 连接失败，请检查配置")
        print(f"📋 检查项:")
        print(f"   1. SQL Server 是否正常运行")
        print(f"   2. 网络连接是否正常")
        print(f"   3. 用户名和密码是否正确")
        print(f"   4. 数据库权限是否充足")

if __name__ == "__main__":
    main()