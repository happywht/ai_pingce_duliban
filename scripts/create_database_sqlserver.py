#!/usr/bin/env python3
"""
创建SQL Server数据库 - 支持 task_id 隔离功能 + 真实数据存储 (V2.1 SQL Server版)
新增了 ProjectEvaluation 表，支持任务级别的数据隔离
新增了 check_date 和 check_person_name 字段，支持存储来自文件信息接口的真实数据
"""

import pyodbc
import sys
from config import config

def create_database(force_recreate=False):
    try:
        # 连接到SQL Server（不指定数据库）
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.DB_HOST};"
            f"PORT={config.DB_PORT};"
            f"DATABASE=master;"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 如果强制重新创建，先删除现有数据库
        if force_recreate:
            try:
                cursor.execute(f"DROP DATABASE {config.DB_NAME}")
                conn.commit()
                print(f"🗑️ 已删除现有数据库 '{config.DB_NAME}'")
            except:
                pass  # 数据库可能不存在

        # 创建数据库
        cursor.execute(f"""
            CREATE DATABASE {config.DB_NAME}
            COLLATE Chinese_PRC_CI_AS
        """)
        conn.commit()
        print(f"✅ 数据库 '{config.DB_NAME}' 创建成功！")

        # 切换到创建的数据库
        conn.close()
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.DB_HOST};"
            f"PORT={config.DB_PORT};"
            f"DATABASE={config.DB_NAME};"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 如果强制重新创建，先删除现有表
        if force_recreate:
            # 按外键依赖顺序删除表
            tables_to_drop = ['project_file', 'project_evaluation', 'project',
                             'document_categories', 'evaluation_templates']
            for table in tables_to_drop:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"🗑️ 已删除表 {table}")
                except:
                    pass

        # 创建project表（简化版，移除评测相关字段）
        cursor.execute("""
            CREATE TABLE project (
                id NVARCHAR(100) PRIMARY KEY,
                project_code NVARCHAR(100),
                project_name NVARCHAR(255),
                last_update DATETIME2 DEFAULT GETDATE(),
                INDEX idx_project_code (project_code)
            )
        """)
        print("✅ project表创建成功！")

        # 创建project_evaluation表（新增：支持task_id隔离 + 真实数据字段）
        cursor.execute("""
            CREATE TABLE project_evaluation (
                id INT IDENTITY(1,1) PRIMARY KEY,
                project_id NVARCHAR(100) NOT NULL,
                task_id NVARCHAR(100) DEFAULT 'DEFAULT_TASK',
                status NVARCHAR(50) DEFAULT 'IDLE',
                rules_config NVARCHAR(MAX),
                evaluation_result NVARCHAR(MAX),
                -- 新增字段：存储来自文件信息接口的真实数据
                check_date NVARCHAR(20) NULL, -- 检查日期，格式: YYYY-MM-DD，来自文件信息接口
                check_person_name NVARCHAR(100) NULL, -- 检查人员姓名，来自文件信息接口
                check_name NVARCHAR(100) NULL, -- 检查人员姓名，来自任务信息
                created_at DATETIME2 DEFAULT GETDATE(),
                updated_at DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT fk_project_evaluation_project FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
                CONSTRAINT unique_project_task UNIQUE (project_id, task_id)
            )
        """)
        print("✅ project_evaluation表创建成功！")

        # 创建索引
        cursor.execute("CREATE INDEX idx_project_evaluation_project_id ON project_evaluation(project_id)")
        cursor.execute("CREATE INDEX idx_project_evaluation_task_id ON project_evaluation(task_id)")
        cursor.execute("CREATE INDEX idx_project_evaluation_status ON project_evaluation(status)")
        cursor.execute("CREATE INDEX idx_project_evaluation_check_date ON project_evaluation(check_date)")
        cursor.execute("CREATE INDEX idx_project_evaluation_check_person ON project_evaluation(check_person_name)")
        cursor.execute("CREATE INDEX idx_project_evaluation_check_name ON project_evaluation(check_name)")

        # 创建project_file表（增强：支持task_id）
        cursor.execute("""
            CREATE TABLE project_file (
                id INT IDENTITY(1,1) PRIMARY KEY,
                project_id NVARCHAR(100) NOT NULL,
                task_id NVARCHAR(100) DEFAULT 'DEFAULT_TASK',
                category_id NVARCHAR(100),
                category_name NVARCHAR(255),
                file_name NVARCHAR(255),
                file_url NVARCHAR(1000),
                file_type NVARCHAR(50),
                file_hash NVARCHAR(64),
                parsed_content NVARCHAR(MAX),
                update_time DATETIME2 DEFAULT GETDATE(),
                CONSTRAINT fk_project_file_project FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
            )
        """)
        print("✅ project_file表创建成功！")

        # 创建索引
        cursor.execute("CREATE INDEX idx_project_file_project_task ON project_file(project_id, task_id)")
        cursor.execute("CREATE INDEX idx_project_file_category ON project_file(category_id)")
        cursor.execute("CREATE INDEX idx_project_file_hash ON project_file(file_hash)")

        # 创建系统表（可选的增强功能）
        cursor.execute("""
            CREATE TABLE evaluation_templates (
                id NVARCHAR(100) PRIMARY KEY,
                template_name NVARCHAR(255) NOT NULL,
                template_type NVARCHAR(50) NOT NULL DEFAULT 'custom',
                description NVARCHAR(MAX),
                rules_config NVARCHAR(MAX),
                is_active BIT DEFAULT 1,
                created_by NVARCHAR(100),
                created_at DATETIME2 DEFAULT GETDATE(),
                updated_at DATETIME2 DEFAULT GETDATE()
            )
        """)
        print("✅ evaluation_templates表创建成功！")

        cursor.execute("""
            CREATE TABLE document_categories (
                id INT IDENTITY(1,1) PRIMARY KEY,
                category_id NVARCHAR(100) NOT NULL UNIQUE,
                category_name NVARCHAR(255) NOT NULL,
                parent_category_id NVARCHAR(100),
                description NVARCHAR(MAX),
                sort_order INT DEFAULT 0,
                is_active BIT DEFAULT 1,
                created_at DATETIME2 DEFAULT GETDATE()
            )
        """)
        print("✅ document_categories表创建成功！")

        # 插入默认数据
        print("\n📥 插入默认数据...")

        # 默认文档分类
        default_categories = [
            ('cat_001', '施工方案', '', '施工组织设计、专项施工方案等'),
            ('cat_002', '技术资料', '', '技术交底、图纸会审、变更洽商等'),
            ('cat_003', '质量资料', '', '质量保证资料、检验批、验收记录等'),
            ('cat_004', '安全资料', '', '安全方案、检查记录、教育培训等'),
            ('cat_005', '合同资料', '', '合同文件、分包协议、签证变更等'),
            ('cat_006', '进度资料', '', '进度计划、实际进度记录等'),
            ('cat_007', '成本资料', '', '造价文件、成本控制、结算资料等'),
            ('cat_008', '其他资料', '', '其他相关文件资料')
        ]

        for cat_id, name, parent, desc in default_categories:
            cursor.execute("""
                INSERT INTO document_categories (category_id, category_name, parent_category_id, description)
                VALUES (?, ?, ?, ?)
            """, (cat_id, name, parent, desc))

        # 默认评测模板
        default_templates = [
            ('basic_template', '基础质量评测模板', 'basic',
             '适用于一般总承包项目的基础质量评测，包含主要检查项'),
            ('advanced_template', '全面质量评测模板', 'advanced',
             '适用于复杂项目的全面质量评测，检查项更详细全面'),
            ('safety_template', '安全生产评测模板', 'safety',
             '专门用于安全生产管理的评测模板')
        ]

        for template_id, name, template_type, desc in default_templates:
            cursor.execute("""
                INSERT INTO evaluation_templates (id, template_name, template_type, description)
                VALUES (?, ?, ?, ?)
            """, (template_id, name, template_type, desc))

        conn.commit()
        print("✅ 默认数据插入完成！")

        cursor.close()
        conn.close()

        print(f"\n🎉 SQL Server数据库 '{config.DB_NAME}' 初始化完成！")
        print("📋 新功能说明:")
        print("   ✅ 支持 task_id 参数隔离不同任务的评测结果")
        print("   ✅ 项目基础信息与评测数据分离存储")
        print("   ✅ 支持多任务并行评测")
        print("   ✅ 存储来自文件信息接口的真实数据（check_date, check_person_name）")
        print("   ✅ 向后兼容，支持旧版本数据格式")
        print("   ✅ 为真实数据字段添加索引优化查询性能")
        print("   ✅ 使用 NVARCHAR 支持中文字符")
        print("   ✅ 使用 DATETIME2 提供更高精度的时间")

    except Exception as e:
        print(f"❌ 创建数据库失败: {e}")
        raise e

def verify_database():
    """验证数据库结构"""
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.DB_HOST};"
            f"PORT={config.DB_PORT};"
            f"DATABASE={config.DB_NAME};"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['project', 'project_evaluation', 'project_file', 'evaluation_templates', 'document_categories']

        print("\n🔍 SQL Server数据库结构验证:")
        all_exist = True
        for table in expected_tables:
            if table in tables:
                print(f"   ✅ {table} 表存在")
            else:
                print(f"   ❌ {table} 表缺失")
                all_exist = False

        if all_exist:
            print("🎉 所有表创建成功！")

            # 检查关键字段
            print("\n📋 检查关键字段:")

            # 检查 project_evaluation 表的关键字段
            pe_fields_to_check = ['task_id', 'check_date', 'check_person_name', 'check_name']
            for field in pe_fields_to_check:
                cursor.execute(f"""
                    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'project_evaluation' AND COLUMN_NAME = '{field}'
                """)
                if cursor.fetchone():
                    print(f"   ✅ project_evaluation.{field} 字段存在")
                else:
                    print(f"   ❌ project_evaluation.{field} 字段缺失")

            # 检查 project_file 表的 task_id 字段
            cursor.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'project_file' AND COLUMN_NAME = 'task_id'
            """)
            if cursor.fetchone():
                print("   ✅ project_file.task_id 字段存在")
            else:
                print("   ❌ project_file.task_id 字段缺失")

        cursor.close()
        conn.close()

        return all_exist

    except Exception as e:
        print(f"❌ 验证数据库失败: {e}")
        return False

def test_connection():
    """测试SQL Server连接"""
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.DB_HOST};"
            f"PORT={config.DB_PORT};"
            f"DATABASE={config.DB_NAME};"
            f"UID={config.DB_USER};"
            f"PWD={config.DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 测试简单查询
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"✅ SQL Server连接成功！")
        print(f"📋 数据库版本: {version[:100]}...")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ SQL Server连接失败: {e}")
        return False

if __name__ == "__main__":
    # 检查命令行参数
    force_recreate = '--force' in sys.argv or '-f' in sys.argv
    verify_only = '--verify' in sys.argv or '-v' in sys.argv
    test_only = '--test' in sys.argv or '-t' in sys.argv

    if test_only:
        print(f"🔧 测试SQL Server连接...")
        test_connection()
    elif verify_only:
        print(f"🔍 验证SQL Server数据库结构: {config.DB_NAME}")
        verify_database()
    elif force_recreate:
        print(f"🔧 正在强制重新创建SQL Server数据库: {config.DB_NAME} (将删除现有数据)")
        create_database(force_recreate=True)
        verify_database()
    else:
        print(f"🔧 正在创建SQL Server数据库: {config.DB_NAME}")
        create_database(force_recreate=False)
        verify_database()