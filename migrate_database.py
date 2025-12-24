#!/usr/bin/env python3
"""
数据库迁移脚本：为project表添加epc_manager和entrust_manager字段
用于适配新的项目信息接口响应格式
"""

import sys
import os
import traceback
from config import config

def check_odbc_drivers():
    """检查可用的ODBC驱动程序"""
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
        return drivers
    except ImportError:
        return []
    except Exception:
        return []

def add_manager_fields_to_sqlserver():
    """为SQL Server添加项目经理字段"""
    try:
        # 检查ODBC驱动是否可用
        drivers = check_odbc_drivers()
        if not drivers:
            print("❌ 未找到SQL Server ODBC驱动程序")
            print("💡 请安装以下驱动之一：")
            print("   - Microsoft ODBC Driver 17 for SQL Server")
            print("   - Microsoft ODBC Driver 18 for SQL Server")
            print("   - 或者使用手动SQL脚本")
            return False

        print(f"✅ 找到ODBC驱动: {drivers[0]}")

        import pyodbc

        # 尝试不同的驱动连接字符串
        conn_strs = []

        if 'ODBC Driver 18' in drivers[0]:
            conn_strs.append(
                f"DRIVER={{{drivers[0]}}};"
                f"SERVER={config.DB_HOST},{config.DB_PORT};"
                f"DATABASE={config.DB_NAME};"
                f"UID={config.DB_USER};"
                f"PWD={config.DB_PASSWORD};"
                f"TrustServerCertificate=yes;"
                f"Encrypt=optional;"
            )
        elif 'ODBC Driver 17' in drivers[0]:
            conn_strs.append(
                f"DRIVER={{{drivers[0]}}};"
                f"SERVER={config.DB_HOST},{config.DB_PORT};"
                f"DATABASE={config.DB_NAME};"
                f"UID={config.DB_USER};"
                f"PWD={config.DB_PASSWORD};"
                f"TrustServerCertificate=yes;"
            )
        else:
            conn_strs.append(
                f"DRIVER={{{drivers[0]}}};"
                f"SERVER={config.DB_HOST},{config.DB_PORT};"
                f"DATABASE={config.DB_NAME};"
                f"UID={config.DB_USER};"
                f"PWD={config.DB_PASSWORD};"
            )

        conn = None
        for i, conn_str in enumerate(conn_strs):
            try:
                print(f"🔗 尝试连接方式 {i+1}/{len(conn_strs)}...")
                conn = pyodbc.connect(conn_str, timeout=10)
                print("✅ 数据库连接成功")
                break
            except Exception as e:
                print(f"❌ 连接方式 {i+1} 失败: {e}")
                if i == len(conn_strs) - 1:
                    raise e

        if conn is None:
            raise Exception("所有连接方式都失败了")

        cursor = conn.cursor()

        print("🔍 检查字段是否存在...")
        # 检查epc_manager字段是否存在
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'project' AND COLUMN_NAME = 'epc_manager'
        """)
        epc_exists = cursor.fetchone()[0] > 0

        # 检查entrust_manager字段是否存在
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'project' AND COLUMN_NAME = 'entrust_manager'
        """)
        entrust_exists = cursor.fetchone()[0] > 0

        if not epc_exists:
            print("🔧 添加epc_manager字段...")
            cursor.execute("ALTER TABLE project ADD epc_manager NVARCHAR(100) NULL")
            print("✅ epc_manager字段添加成功")
        else:
            print("ℹ️ epc_manager字段已存在")

        if not entrust_exists:
            print("🔧 添加entrust_manager字段...")
            cursor.execute("ALTER TABLE project ADD entrust_manager NVARCHAR(100) NULL")
            print("✅ entrust_manager字段添加成功")
        else:
            print("ℹ️ entrust_manager字段已存在")

        conn.commit()
        print("✅ SQL Server数据库迁移完成")

    except ImportError as e:
        print(f"❌ 缺少pyodbc库: {e}")
        print("💡 请安装: pip install pyodbc")
        print("🔧 或使用手动SQL脚本: migrate_project_fields.sql")
        return False
    except Exception as e:
        print(f"❌ SQL Server迁移失败: {e}")
        print("🔧 可以尝试以下解决方案：")
        print("   1. 安装正确的ODBC驱动程序")
        print("   2. 使用手动SQL脚本: migrate_project_fields.sql")
        print("   3. 检查数据库连接配置")

        if 'IM002' in str(e):
            print("\n📋 ODBC驱动安装指南：")
            print("   - 下载地址: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server")
            print("   - 推荐安装: Microsoft ODBC Driver 17 for SQL Server")
            print("   - 安装后需要重启Python服务")

        traceback.print_exc()
        return False
    finally:
        if 'conn' in locals():
            conn.close()
    return True

def add_manager_fields_to_mysql():
    """为MySQL添加项目经理字段"""
    try:
        import pymysql
        conn = pymysql.connect(
            host=config.DB_HOST,
            port=int(config.DB_PORT),
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            charset='utf8mb4'
        )

        cursor = conn.cursor()

        print("🔍 检查字段是否存在...")
        # 检查字段是否存在
        cursor.execute("DESCRIBE project")
        columns = [row[0] for row in cursor.fetchall()]

        if 'epc_manager' not in columns:
            print("🔧 添加epc_manager字段...")
            cursor.execute("ALTER TABLE project ADD COLUMN epc_manager VARCHAR(100) COMMENT '项目经理'")
            print("✅ epc_manager字段添加成功")
        else:
            print("ℹ️ epc_manager字段已存在")

        if 'entrust_manager' not in columns:
            print("🔧 添加entrust_manager字段...")
            cursor.execute("ALTER TABLE project ADD COLUMN entrust_manager VARCHAR(100) COMMENT '项目执行经理'")
            print("✅ entrust_manager字段添加成功")
        else:
            print("ℹ️ entrust_manager字段已存在")

        conn.commit()
        print("✅ MySQL数据库迁移完成")

    except Exception as e:
        print(f"❌ MySQL迁移失败: {e}")
        traceback.print_exc()
        return False
    finally:
        if 'conn' in locals():
            conn.close()
    return True

def main():
    print("🚀 开始数据库迁移：添加项目经理字段")
    print(f"📊 数据库类型: {config.DB_TYPE}")
    print(f"📍 服务器: {config.DB_HOST}:{config.DB_PORT}")
    print(f"💾 数据库: {config.DB_NAME}")
    print("-" * 50)

    # 检查是否有手动SQL脚本可用
    sql_script_exists = False
    mysql_script_exists = False

    if config.DB_TYPE == 'mssql':
        sql_script_exists = os.path.exists('migrate_project_fields.sql')
    elif config.DB_TYPE == 'mysql':
        mysql_script_exists = os.path.exists('migrate_project_fields_mysql.sql')

    print("📋 迁移方式选择：")
    print("   1. 自动迁移 (Python脚本)")
    if sql_script_exists:
        print("   2. 手动迁移 (SQL Server脚本)")
    if mysql_script_exists:
        print("   2. 手动迁移 (MySQL脚本)")

    print()

    success = False
    if config.DB_TYPE == 'mssql':
        success = add_manager_fields_to_sqlserver()
        if not success and sql_script_exists:
            print(f"\n🔧 自动迁移失败，建议使用手动SQL脚本：")
            print(f"   脚本位置: migrate_project_fields.sql")
            print(f"   执行方式: 在SQL Server Management Studio中执行该脚本")
    elif config.DB_TYPE == 'mysql':
        success = add_manager_fields_to_mysql()
        if not success and mysql_script_exists:
            print(f"\n🔧 自动迁移失败，建议使用手动SQL脚本：")
            print(f"   脚本位置: migrate_project_fields_mysql.sql")
            print(f"   执行方式: 在MySQL客户端中执行该脚本")
    else:
        print(f"❌ 不支持的数据库类型: {config.DB_TYPE}")
        sys.exit(1)

    if success:
        print("\n🎉 数据库迁移成功完成！")
        print("📝 已为project表添加以下字段：")
        print("   - epc_manager: 项目经理")
        print("   - entrust_manager: 项目执行经理")
        print("\n💡 现在可以重新启动服务以使用新的字段")
    else:
        print("\n❌ 数据库迁移失败，请检查错误信息")
        print("\n💡 其他解决方案：")
        print("   1. 使用手动SQL脚本执行迁移")
        print("   2. 检查数据库连接配置")
        print("   3. 联系系统管理员协助")
        sys.exit(1)

if __name__ == "__main__":
    main()