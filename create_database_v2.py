#!/usr/bin/env python3
"""
创建MySQL数据库 - 支持 task_id 隔离功能 + 真实数据存储 (V2.1)
新增了 ProjectEvaluation 表，支持任务级别的数据隔离
新增了 check_date 和 check_person_name 字段，支持存储来自文件信息接口的真实数据
"""

import pymysql
import sys
from config import config

def create_database(force_recreate=False):
    try:
        # 先连接到MySQL服务器（不指定数据库）
        conn = pymysql.connect(
            host=config.DB_HOST,
            port=int(config.DB_PORT),
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            charset='utf8mb4'
        )

        cursor = conn.cursor()

        # 如果强制重新创建，先删除现有数据库
        if force_recreate:
            cursor.execute(f"DROP DATABASE IF EXISTS {config.DB_NAME}")
            print(f"🗑️ 已删除现有数据库 '{config.DB_NAME}'")

        # 创建数据库
        cursor.execute(f"CREATE DATABASE {config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ 数据库 '{config.DB_NAME}' 创建成功！")

        # 检查数据库是否存在
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]

        if config.DB_NAME in databases:
            print(f"✅ 确认数据库 '{config.DB_NAME}' 已存在")
        else:
            print(f"❌ 数据库 '{config.DB_NAME}' 创建失败")
            cursor.close()
            conn.close()
            return

        # 切换到创建的数据库
        cursor.execute(f"USE {config.DB_NAME}")

        # 如果强制重新创建，先删除现有表
        if force_recreate:
            cursor.execute("DROP TABLE IF EXISTS project_file")
            cursor.execute("DROP TABLE IF EXISTS project_evaluation")
            cursor.execute("DROP TABLE IF EXISTS project")
            print("🗑️ 已删除现有表")

        # 创建project表（简化版，移除评测相关字段，新增项目经理字段）
        cursor.execute("""
            CREATE TABLE project (
                id VARCHAR(100) PRIMARY KEY,
                project_code VARCHAR(100),
                project_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                epc_manager VARCHAR(100) COMMENT '项目经理',
                entrust_manager VARCHAR(100) COMMENT '项目执行经理',
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_project_code (project_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("✅ project表创建成功！")

        # 创建project_evaluation表（新增：支持task_id隔离 + 真实数据字段）
        cursor.execute("""
            CREATE TABLE project_evaluation (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id VARCHAR(100) NOT NULL,
                task_id VARCHAR(100) DEFAULT 'DEFAULT_TASK',
                status VARCHAR(50) DEFAULT 'IDLE',
                rules_config TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                evaluation_result LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                -- 新增字段：存储来自文件信息接口的真实数据
                check_date VARCHAR(20) COMMENT '检查日期，格式: YYYY-MM-DD，来自文件信息接口',
                check_person_name VARCHAR(100) COMMENT '检查人员姓名，来自文件信息接口',
                check_name VARCHAR(100) COMMENT '检查人员姓名，来自任务信息',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
                UNIQUE KEY unique_project_task (project_id, task_id),
                INDEX idx_project_id (project_id),
                INDEX idx_task_id (task_id),
                INDEX idx_status (status),
                -- 为新字段添加索引以提高查询性能
                INDEX idx_project_evaluation_check_date (check_date),
                INDEX idx_project_evaluation_check_person (check_person_name),
                INDEX idx_project_evaluation_check_name (check_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("✅ project_evaluation表创建成功！")

        # 创建project_file表（增强：支持task_id）
        cursor.execute("""
            CREATE TABLE project_file (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id VARCHAR(100) NOT NULL,
                task_id VARCHAR(100) DEFAULT 'DEFAULT_TASK',
                category_id VARCHAR(100),
                category_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                file_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                file_url VARCHAR(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                file_type VARCHAR(50),
                file_hash VARCHAR(64),
                parsed_content LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
                INDEX idx_project_file (project_id, task_id),
                INDEX idx_category (category_id),
                INDEX idx_file_hash (file_hash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("✅ project_file表创建成功！")

        # 创建系统表（可选的增强功能）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_templates (
                id VARCHAR(100) PRIMARY KEY,
                template_name VARCHAR(255) NOT NULL,
                template_type VARCHAR(50) NOT NULL DEFAULT 'custom',
                description TEXT,
                rules_config TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("✅ evaluation_templates表创建成功！")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category_id VARCHAR(100) NOT NULL UNIQUE,
                category_name VARCHAR(255) NOT NULL,
                parent_category_id VARCHAR(100),
                description TEXT,
                sort_order INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
                INSERT IGNORE INTO document_categories (category_id, category_name, parent_category_id, description)
                VALUES (%s, %s, %s, %s)
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
                INSERT IGNORE INTO evaluation_templates
                (id, template_name, template_type, description)
                VALUES (%s, %s, %s, %s)
            """, (template_id, name, template_type, desc))

        print("✅ 默认数据插入完成！")

        cursor.close()
        conn.close()

        print(f"\n🎉 数据库 '{config.DB_NAME}' 初始化完成！")
        print("📋 新功能说明:")
        print("   ✅ 支持 task_id 参数隔离不同任务的评测结果")
        print("   ✅ 项目基础信息与评测数据分离存储")
        print("   ✅ 支持多任务并行评测")
        print("   ✅ 存储来自文件信息接口的真实数据（check_date, check_person_name）")
        print("   ✅ 向后兼容，支持旧版本数据格式")
        print("   ✅ 为真实数据字段添加索引优化查询性能")

    except Exception as e:
        print(f"❌ 创建数据库失败: {e}")
        raise e

def verify_database():
    """验证数据库结构"""
    try:
        conn = pymysql.connect(
            host=config.DB_HOST,
            port=int(config.DB_PORT),
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            charset='utf8mb4'
        )

        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

        expected_tables = ['project', 'project_evaluation', 'project_file', 'evaluation_templates', 'document_categories']

        print("\n🔍 数据库结构验证:")
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
                cursor.execute(f"SHOW COLUMNS FROM project_evaluation WHERE Field = '{field}'")
                if cursor.fetchone():
                    print(f"   ✅ project_evaluation.{field} 字段存在")
                else:
                    print(f"   ❌ project_evaluation.{field} 字段缺失")

            # 检查 project_file 表的 task_id 字段
            cursor.execute("SHOW COLUMNS FROM project_file WHERE Field = 'task_id'")
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

if __name__ == "__main__":
    # 检查命令行参数
    force_recreate = '--force' in sys.argv or '-f' in sys.argv
    verify_only = '--verify' in sys.argv or '-v' in sys.argv

    if verify_only:
        print(f"🔍 验证数据库结构: {config.DB_NAME}")
        verify_database()
    elif force_recreate:
        print(f"🔧 正在强制重新创建数据库: {config.DB_NAME} (将删除现有数据)")
        create_database(force_recreate=True)
        verify_database()
    else:
        print(f"🔧 正在创建数据库: {config.DB_NAME}")
        create_database(force_recreate=False)
        verify_database()