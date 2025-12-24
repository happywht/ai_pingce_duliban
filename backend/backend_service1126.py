import json
import time
import hashlib
import threading
import os
import requests
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import threading
from sqlalchemy import orm
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, text
from config import config



# ==========================================
# 0. 日志配置 (核心优化)
# ==========================================

def setup_logging():
    """
    配置日志系统
    优化点：
    1. 使用 RotatingFileHandler 防止日志文件无限增长
    2. 移除 setup_thread_logging，避免多线程环境下的句柄泄露
    3. 统一日志格式，确保所有线程日志都被捕获
    """
    # 确保日志目录存在（项目根目录的logs）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 主日志文件 (自动轮转，最大10MB，保留10个备份)
    log_filename = os.path.join(log_dir, 'backend_service.log')

    # 配置格式：增加 [ThreadName] 以便区分多线程日志
    log_format = config.LOG_FORMAT
    formatter = logging.Formatter(log_format)

    # 获取根 Logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # 清除旧的处理器，防止重复打印
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. 轮转文件处理器 (解决日志记录不全、文件过大的问题)
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # 2. 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 3. 错误单独记录
    error_log_filename = os.path.join(log_dir, 'backend_error.log')
    error_handler = RotatingFileHandler(
        error_log_filename,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)

    return logger


# 初始化日志系统
logger = setup_logging()

logger.info("=" * 60)
logger.info("🚀 后端服务启动 - 日志系统优化版 (Unified Logging)")
logger.info(f"📂 数据库类型: {config.DB_TYPE}")
logger.info("=" * 60)

# ==========================================
# 1. 依赖库检查与初始化
# ==========================================

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("⚠️ [提示] 未检测到 anthropic，真实AI评测将跳过。")

try:
    from advanced_document_parser import AdvancedDocumentProcessor

    doc_parser = AdvancedDocumentProcessor(ocr_lang='chi_sim+eng')
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False
    logger.warning("⚠️ [提示] 未检测到 advanced_document_parser，将使用Mock解析。")

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("⚠️ [提示] 未检测到 pandas，Excel 规则表仅作为兜底。")

app = Flask(__name__)

# ==========================================
# 1. 全局并发任务配置
# ==========================================

# 全局并发任务配置
GLOBAL_CONFIG = {
    'MAX_CONCURRENT_TASKS': int(os.getenv('MAX_CONCURRENT_TASKS', 3)),  # 从环境变量读取，默认3个
    'RUNNING_STATES': ['SYNCING', 'EVALUATING', 'PENDING'],  # 运行中的状态
    'RERUNNABLE_STATES': ['COMPLETED', 'ERROR', 'IDLE']     # 可重新运行的状态
}

# 全局锁，用于并发控制
task_management_lock = threading.Lock()

def get_running_tasks_count():
    """
    获取当前正在运行的任务数量
    注意：这个函数需要在有数据库session的上下文中调用
    """
    try:
        # 使用正确的模型名称 ProjectEvaluation
        running_count = ProjectEvaluation.query.filter(
            ProjectEvaluation.status.in_(GLOBAL_CONFIG['RUNNING_STATES'])
        ).count()
        logger.info(f"当前运行任务数量: {running_count}")
        return running_count
    except Exception as e:
        logger.error(f"获取运行任务数量失败: {e}")
        return 0

def check_task_concurrency_limit():
    """
    检查是否达到并发任务限制
    返回: (is_allowed, current_count, max_count, running_tasks)
    """
    try:
        current_count = get_running_tasks_count()
        max_count = GLOBAL_CONFIG['MAX_CONCURRENT_TASKS']

        # 获取当前运行的任务列表
        running_tasks = ProjectEvaluation.query.filter(
            ProjectEvaluation.status.in_(GLOBAL_CONFIG['RUNNING_STATES'])
        ).all()

        running_task_info = [
            {
                'task_id': task.task_id,
                'project_id': task.project_id,
                'status': task.status,
                'created_at': task.created_at.isoformat() if task.created_at else None
            }
            for task in running_tasks
        ]

        is_allowed = current_count < max_count

        result = {
            'is_allowed': is_allowed,
            'current_count': current_count,
            'max_count': max_count,
            'available_slots': max_count - current_count,
            'running_tasks': running_task_info
        }

        logger.info(f"并发状态检查结果: {result}")
        return result

    except Exception as e:
        logger.error(f"检查并发任务限制失败: {e}")
        return {
            'is_allowed': False,
            'current_count': 0,
            'max_count': GLOBAL_CONFIG['MAX_CONCURRENT_TASKS'],
            'available_slots': 0,
            'running_tasks': [],
            'error': str(e)
        }

# ==========================================
# 2. 数据库配置 (从 config 读取)
# ==========================================

# 直接使用 Config 中生成的 URI
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 针对不同数据库的引擎参数优化
engine_options = {"connect_args": {}}

if config.DB_TYPE == 'sqlite':
    # SQLite 特有超时设置
    engine_options["connect_args"]["timeout"] = 30
    engine_options["pool_pre_ping"] = True
    engine_options["pool_recycle"] = 3600
elif config.DB_TYPE == 'mysql':
    # MySQL 连接回收时间
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20
    # 添加字符集设置以防止编码问题
    db_uri = config.SQLALCHEMY_DATABASE_URI
    if '?' in db_uri:
        # 如果URL已有参数，添加字符集参数
        if 'charset=' not in db_uri:
            app.config['SQLALCHEMY_DATABASE_URI'] = db_uri + '&charset=utf8mb4'
    else:
        # 如果URL没有参数，添加字符集参数
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri + '?charset=utf8mb4'
    
    # 确保连接使用UTF8MB4字符集
    engine_options["connect_args"] = {
        'charset': 'utf8mb4',
        'use_unicode': True
    }
    engine_options["pool_recycle"] = 280
    engine_options["pool_size"] = 10
    engine_options["max_overflow"] = 20

elif config.DB_TYPE == 'mssql':
    # SQL Server 配置
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 3600
    app.config['SQLALCHEMY_POOL_SIZE'] = 5
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 10
    app.config['SQLALCHEMY_POOL_PRE_PING'] = True

    # SQL Server 特定配置 - 修复NVARCHAR(max)精度问题
    engine_options["connect_args"] = {
        'timeout': 30,
        'TrustServerCertificate': 'yes',
        'autocommit': True,
        'ansi': True,
        'use_native_datetime': True
    }
    engine_options["pool_recycle"] = 3600
    engine_options["pool_size"] = 5
    engine_options["max_overflow"] = 10
    # 修复NVARCHAR(max)问题的SQLAlchemy配置
    engine_options["echo"] = False  # 关闭SQL日志以避免精度问题
    engine_options["max_identifier_length"] = 128  # 限制标识符长度
    # 禁用 OUTPUT 子句，避免与触发器冲突
    engine_options["use_insertmanyvalues"] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

db = SQLAlchemy(app)

# 仅 SQLite 需要开启 WAL 模式
if config.DB_TYPE == 'sqlite':
    with app.app_context():
        try:
            # 检查文件是否存在，避免初次运行报错
            if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
                db_path = config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
                if not os.path.exists(db_path):
                    logger.info("创建新的 SQLite 数据库...")
                    db.create_all()


            @event.listens_for(db.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
        except Exception as e:
            logger.error(f"SQLite WAL 配置失败: {e}")
else:
    # 生产数据库不需要手动建表，但开发环境为了方便仍保留
    with app.app_context():
        try:
            db.create_all()
            logger.info(f"✅ 数据库连接成功: {config.DB_TYPE}")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")

# 线程池
doc_parser_executor = ThreadPoolExecutor(
    max_workers=config.MAX_CONCURRENT_PROJECTS,
    thread_name_prefix="DocParser"
)


# ==========================================
# 3. 数据库模型 - 适配多种数据库类型
# ==========================================

# 根据数据库类型选择合适的字符串类型
def get_string_field(length):
    """根据数据库类型返回合适的字符串字段类型"""
    if config.DB_TYPE == 'mssql':
        # SQL Server 使用 NVARCHAR 支持中文
        return db.NVARCHAR(length)
    else:
        # MySQL, PostgreSQL, SQLite 使用 String
        return db.String(length)

def get_text_field():
    """根据数据库类型返回合适的文本字段类型"""
    if config.DB_TYPE == 'mssql':
        # ODBC Driver 13 对 NVARCHAR(max) 支持有限，使用固定长度
        return db.NVARCHAR(4000)
    else:
        # 其他数据库使用 Text
        return db.Text

def safe_datetime_format(dt, format_str='%Y-%m-%d %H:%M:%S', default=''):
    """安全的datetime格式化函数，处理各种数据类型包括datetime2"""
    if dt is None:
        return default

    try:
        if isinstance(dt, str):
            # 如果已经是字符串，直接返回
            # 处理datetime2字符串格式，去掉微秒部分
            if '.' in dt:
                # 处理 "2025-12-09 16:02:46.5366667" 格式
                date_part = dt.split('.')[0]
                return date_part
            return dt
        elif hasattr(dt, 'strftime'):
            # 如果是datetime对象，进行格式化
            # 对于datetime2对象，可能需要特殊处理
            try:
                formatted = dt.strftime(format_str)
                return formatted
            except (ValueError, OSError, AttributeError) as format_error:
                # 如果strftime失败，尝试其他方法
                logger.warning(f"strftime失败，尝试替代方法: {format_error}")
                # 尝试转换为字符串再处理
                dt_str = str(dt)
                if '.' in dt_str:
                    return dt_str.split('.')[0]
                return dt_str
        else:
            # 其他情况，尝试转换为字符串
            dt_str = str(dt)
            # 处理可能的datetime2字符串格式
            if '.' in dt_str:
                return dt_str.split('.')[0]
            return dt_str
    except Exception as e:
        logger.warning(f"日期格式化失败: {e}, 原始数据类型: {type(dt)}, 原始值: {dt}")
        return default

class Project(db.Model):
    # 根据数据库类型调整字段类型
    id = db.Column(get_string_field(100), primary_key=True)
    project_code = db.Column(get_string_field(100))
    project_name = db.Column(get_string_field(255))
    # 新增项目经理相关字段
    epc_manager = db.Column(get_string_field(100))  # 项目经理
    entrust_manager = db.Column(get_string_field(100))  # 项目执行经理
    # 移除 status, rules_config, evaluation_result 字段，这些现在在 ProjectEvaluation 中管理
    last_update = db.Column(db.DateTime, default=datetime.now)


class ProjectEvaluation(db.Model):
    """项目评测表 - 支持同一项目多个任务ID的独立评测"""
    __tablename__ = 'project_evaluation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(get_string_field(100), db.ForeignKey('project.id'), nullable=False, index=True)
    task_id = db.Column(get_string_field(100), nullable=True, index=True)  # 可以为空，兼容旧数据
    status = db.Column(get_string_field(50), default='IDLE')
    rules_config = db.Column(get_text_field(), nullable=True)
    evaluation_result = db.Column(get_text_field(), nullable=True)

    # 新增字段：存储来自文件信息接口的真实数据
    check_date = db.Column(get_string_field(20), nullable=True)  # 检查日期，格式: YYYY-MM-DD
    check_person_name = db.Column(get_string_field(100), nullable=True)  # 检查人员姓名
    check_name = db.Column(get_string_field(100), nullable=True)  # 检查人员姓名，来自任务信息

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 添加唯一约束：同一项目同一任务ID只能有一条记录
    __table_args__ = (
        db.UniqueConstraint('project_id', 'task_id', name='unique_project_task'),
        {'implicit_returning': False}  # 禁用隐式 RETURNING，避免 OUTPUT 子句
    )


class ProjectFile(db.Model):
    __tablename__ = 'project_file'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(get_string_field(100), db.ForeignKey('project.id'), index=True)
    task_id = db.Column(get_string_field(100), nullable=True, index=True)  # 新增：支持任务ID隔离
    category_id = db.Column(get_string_field(100))
    category_name = db.Column(get_string_field(255))
    file_name = db.Column(get_string_field(255))
    file_url = db.Column(get_string_field(1000))  # URL可能很长
    file_type = db.Column(get_string_field(50))
    file_hash = db.Column(get_string_field(64))
    # 使用适配多数据库的文本字段类型
    parsed_content = db.Column(get_text_field(), nullable=True)  # 存储大文本
    update_time = db.Column(db.DateTime, default=datetime.now)

    # SQL Server 特定配置：禁用隐式 RETURNING，避免 OUTPUT 子句与触发器冲突
    __table_args__ = {'implicit_returning': False}


# 数据库字段自愈检测 (主要针对 SQLite/MySQL 迁移时的字段缺失)
with app.app_context():
    try:
        db.create_all()

        # 更智能的字段检查 - 检查表结构而不是查询
        with db.engine.connect() as conn:
            if config.DB_TYPE == 'mssql':
                # SQL Server 检查字段是否存在
                check_result = conn.execute(text("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'project' AND COLUMN_NAME = 'rules_config'
                """))
            else:
                # 其他数据库的通用检查
                check_result = conn.execute(text("""
                    PRAGMA table_info(project)
                """))

            field_exists = False
            if config.DB_TYPE == 'mssql':
                field_exists = check_result.fetchone()[0] > 0
            else:
                field_exists = any(row[1] == 'rules_config' for row in check_result.fetchall())

            if not field_exists:
                logger.warning("⚠️ rules_config 字段不存在，正在添加...")
                if config.DB_TYPE == 'mssql':
                    conn.execute(text("ALTER TABLE project ADD rules_config TEXT NULL"))
                else:
                    conn.execute(text("ALTER TABLE project ADD COLUMN rules_config TEXT"))
                logger.info("✅ 自动修复: 添加 rules_config 字段")
            else:
                logger.info("✅ rules_config 字段已存在，跳过添加")

    except Exception as e:
        logger.warning(f"⚠️ 数据库检查时出现问题: {e}")
        logger.info("ℹ️ 这通常不是严重问题，服务将正常运行")
    #
    # # 检查 parsed_content 字段是否需要修改为 LONGTEXT (MySQL)
    # if config.DB_TYPE == 'mysql':
    #     try:
    #         with db.engine.connect() as conn:
    #             # 检查字段类型
    #             result = conn.execute(text("SHOW COLUMNS FROM project_file WHERE Field = 'parsed_content'"))
    #             column_info = result.fetchone()
    #             if column_info and 'longtext' not in column_info[1].lower():
    #                 logger.warning(f"⚠️ parsed_content 字段类型为 {column_info[1]}，可能需要修改为 LONGTEXT")
    #                 try:
    #                     # 修改字段类型为 LONGTEXT
    #                     conn.execute(text("ALTER TABLE project_file MODIFY COLUMN parsed_content LONGTEXT"))
    #                     logger.info("✅ 自动修复: 将 parsed_content 字段修改为 LONGTEXT")
    #                 except Exception as ex:
    #                     logger.error(f"❌ 修改 parsed_content 字段类型失败: {ex}")
    #     except Exception as e:
    #         logger.warning(f"⚠️ 检查 parsed_content 字段类型失败: {e}")


# ==========================================
# 3.5. 智能任务恢复管理器
# ==========================================

class TaskStatus(Enum):
    """任务状态枚举"""
    IDLE = "IDLE"
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"

class TaskRecoveryManager:
    """智能任务恢复管理器

    替换简单粗暴的 reset_stuck_tasks 函数，实现：
    1. 基于时间的智能任务恢复策略
    2. 区分可恢复和不可恢复任务状态
    3. 详细的错误记录和恢复日志
    4. 支持任务自愈和人工干预
    """

    def __init__(self):
        self.recovery_threshold_hours = 1  # 任务卡住超过2小时才认为是需要恢复的任务
        self.max_recovery_attempts = 3  # 最大恢复尝试次数

    def recover_stuck_tasks(self):
        """智能恢复卡住的任务

        Returns:
            dict: 恢复结果统计
        """
        logger.info("🔧 开始智能任务恢复检测...")
        recovery_stats = {
            'total_checked': 0,
            'recoverable_tasks': 0,
            'recovered_tasks': 0,
            'failed_tasks': 0,
            'ignored_tasks': 0
        }

        with app.app_context():
            try:
                # 查找可能卡住的任务
                threshold = datetime.now() - timedelta(hours=self.recovery_threshold_hours)
                stuck_tasks = ProjectEvaluation.query.filter(
                    ProjectEvaluation.status.in_(['SYNCING', 'EVALUATING']),
                    ProjectEvaluation.created_at < threshold
                ).all()

                recovery_stats['total_checked'] = len(stuck_tasks)

                if not stuck_tasks:
                    logger.info("✅ 未发现需要恢复的卡住任务")
                    return recovery_stats

                logger.info(f"🔍 发现 {len(stuck_tasks)} 个可能卡住的任务")

                for task in stuck_tasks:
                    try:
                        result = self._attempt_recovery(task)
                        if result['action'] == 'recovered':
                            recovery_stats['recovered_tasks'] += 1
                        elif result['action'] == 'failed':
                            recovery_stats['failed_tasks'] += 1
                        elif result['action'] == 'ignored':
                            recovery_stats['ignored_tasks'] += 1

                        if result['is_recoverable']:
                            recovery_stats['recoverable_tasks'] += 1

                    except Exception as e:
                        logger.error(f"恢复任务失败 {task.project_id}:{task.task_id} - {e}")
                        recovery_stats['failed_tasks'] += 1

                db.session.commit()

                logger.info(f"📊 任务恢复完成统计: {recovery_stats}")

            except Exception as e:
                logger.error(f"任务恢复过程发生错误: {e}")
                db.session.rollback()

        return recovery_stats

    def _attempt_recovery(self, task):
        """尝试恢复单个任务

        Args:
            task: ProjectEvaluation 实例

        Returns:
            dict: 恢复结果
        """
        task_duration = datetime.now() - task.created_at
        duration_hours = task_duration.total_seconds() / 3600

        # 记录中断信息
        error_info = {
            "reason": "服务重启，任务被中断",
            "original_status": task.status,
            "interrupted_at": datetime.now().isoformat(),
            "duration_hours": round(duration_hours, 2),
            "is_recoverable": self._is_recoverable(task),
            "recovery_strategy": self._determine_recovery_strategy(task)
        }

        logger.info(f"🔧 分析任务 {task.project_id}:{task.task_id} - "
                   f"状态: {task.status}, 持续: {duration_hours:.1f}小时")

        if error_info["is_recoverable"]:
            # 可恢复的任务：创建恢复任务记录
            recovery_strategy = error_info["recovery_strategy"]

            if recovery_strategy == "auto_resume":
                # 自动恢复：重新启动任务
                return self._auto_resume_task(task, error_info)
            elif recovery_strategy == "mark_retry":
                # 标记为可重试
                return self._mark_for_retry(task, error_info)
            else:
                # 标记为错误但保留详细信息
                return self._mark_as_error_with_info(task, error_info)
        else:
            # 不可恢复的任务：直接标记为错误
            return self._mark_as_unrecoverable(task, error_info)

    def _is_recoverable(self, task):
        """判断任务是否可恢复

        Args:
            task: ProjectEvaluation 实例

        Returns:
            bool: 是否可恢复
        """
        # 基于任务状态和持续时间判断
        task_duration = datetime.now() - task.created_at
        duration_hours = task_duration.total_seconds() / 3600

        # 超过24小时的任务不进行自动恢复
        if duration_hours > 24:
            return False

        # 检查之前的恢复次数
        recovery_count = self._get_recovery_count(task)
        if recovery_count >= self.max_recovery_attempts:
            logger.warning(f"任务 {task.project_id}:{task.task_id} 恢复次数已达上限")
            return False

        # 基于任务状态的恢复策略
        if task.status == 'SYNCING':
            # 同步阶段的任务通常可以安全恢复
            return True
        elif task.status == 'EVALUATING':
            # 评测阶段的任务需要更谨慎
            # 检查是否有部分结果
            if task.evaluation_result:
                try:
                    result_data = json.loads(task.evaluation_result)
                    if len(result_data) > 0:
                        logger.info(f"任务 {task.project_id}:{task.task_id} 有部分结果，标记为可重试")
                        return True
                except:
                    pass
            return True

        return False

    def _determine_recovery_strategy(self, task):
        """确定恢复策略

        Args:
            task: ProjectEvaluation 实例

        Returns:
            str: 恢复策略 (auto_resume, mark_retry, mark_error)
        """
        task_duration = datetime.now() - task.created_at
        duration_hours = task_duration.total_seconds() / 3600
        recovery_count = self._get_recovery_count(task)

        # 首次恢复且持续时间较短（<6小时）：尝试自动恢复
        if recovery_count == 0 and duration_hours < 6:
            return "auto_resume"

        # 多次恢复或持续时间较长：标记为可重试
        if recovery_count < self.max_recovery_attempts:
            return "mark_retry"

        # 其他情况：标记为错误
        return "mark_error"

    def _get_recovery_count(self, task):
        """获取任务已恢复次数

        Args:
            task: ProjectEvaluation 实例

        Returns:
            int: 恢复次数
        """
        if not task.evaluation_result:
            return 0

        try:
            result_data = json.loads(task.evaluation_result)
            recovery_count = 0

            for item in result_data:
                if isinstance(item, dict) and item.get("reason", "").startswith("服务重启"):
                    recovery_count += 1

            return recovery_count
        except:
            return 0

    def _auto_resume_task(self, task, error_info):
        """自动恢复任务

        Args:
            task: ProjectEvaluation 实例
            error_info: 错误信息

        Returns:
            dict: 恢复结果
        """
        try:
            # 重新启动任务（这里可以调用完整的评测流程）
            logger.info(f"🔄 自动恢复任务: {task.project_id}:{task.task_id}")

            # 更新任务状态为待处理
            task.status = TaskStatus.PENDING.value
            task.updated_at = datetime.now()

            # 记录恢复信息
            recovery_log = {
                **error_info,
                "recovery_action": "auto_resume",
                "recovered_at": datetime.now().isoformat()
            }

            if task.evaluation_result:
                existing_result = json.loads(task.evaluation_result)
                existing_result.append(recovery_log)
            else:
                existing_result = [recovery_log]

            task.evaluation_result = json.dumps(existing_result)

            logger.info(f"✅ 任务 {task.project_id}:{task.task_id} 已标记为自动恢复")
            return {
                'action': 'recovered',
                'is_recoverable': True,
                'message': '任务已标记为自动恢复'
            }

        except Exception as e:
            logger.error(f"自动恢复任务失败 {task.project_id}:{task.task_id} - {e}")
            return self._mark_as_error_with_info(task, error_info)

    def _mark_for_retry(self, task, error_info):
        """标记任务为可重试

        Args:
            task: ProjectEvaluation 实例
            error_info: 错误信息

        Returns:
            dict: 恢复结果
        """
        try:
            task.status = TaskStatus.ERROR.value
            task.updated_at = datetime.now()

            # 记录重试信息
            retry_log = {
                **error_info,
                "recovery_action": "mark_for_retry",
                "retry_eligible": True,
                "marked_at": datetime.now().isoformat()
            }

            if task.evaluation_result:
                existing_result = json.loads(task.evaluation_result)
                existing_result.append(retry_log)
            else:
                existing_result = [retry_log]

            task.evaluation_result = json.dumps(existing_result)

            logger.info(f"🔄 任务 {task.project_id}:{task.task_id} 已标记为可重试")
            return {
                'action': 'recovered',
                'is_recoverable': True,
                'message': '任务已标记为可重试'
            }

        except Exception as e:
            logger.error(f"标记重试失败 {task.project_id}:{task.task_id} - {e}")
            return {'action': 'failed', 'is_recoverable': False, 'message': str(e)}

    def _mark_as_error_with_info(self, task, error_info):
        """标记任务为错误并保留详细信息

        Args:
            task: ProjectEvaluation 实例
            error_info: 错误信息

        Returns:
            dict: 恢复结果
        """
        try:
            task.status = TaskStatus.ERROR.value
            task.updated_at = datetime.now()

            # 记录详细错误信息
            error_log = {
                **error_info,
                "recovery_action": "marked_error",
                "marked_at": datetime.now().isoformat()
            }

            if task.evaluation_result:
                existing_result = json.loads(task.evaluation_result)
                existing_result.append(error_log)
            else:
                existing_result = [error_log]

            task.evaluation_result = json.dumps(existing_result)

            logger.info(f"❌ 任务 {task.project_id}:{task.task_id} 已标记为错误")
            return {
                'action': 'failed',
                'is_recoverable': error_info["is_recoverable"],
                'message': '任务已标记为错误'
            }

        except Exception as e:
            logger.error(f"标记错误失败 {task.project_id}:{task.task_id} - {e}")
            return {'action': 'failed', 'is_recoverable': False, 'message': str(e)}

    def _mark_as_unrecoverable(self, task, error_info):
        """标记任务为不可恢复

        Args:
            task: ProjectEvaluation 实例
            error_info: 错误信息

        Returns:
            dict: 恢复结果
        """
        try:
            task.status = TaskStatus.ERROR.value
            task.updated_at = datetime.now()

            # 记录不可恢复信息
            unrecoverable_log = {
                **error_info,
                "recovery_action": "marked_unrecoverable",
                "reason": "任务持续时间过长或恢复次数超限",
                "marked_at": datetime.now().isoformat()
            }

            if task.evaluation_result:
                existing_result = json.loads(task.evaluation_result)
                existing_result.append(unrecoverable_log)
            else:
                existing_result = [unrecoverable_log]

            task.evaluation_result = json.dumps(existing_result)

            logger.info(f"🚫 任务 {task.project_id}:{task.task_id} 已标记为不可恢复")
            return {
                'action': 'ignored',
                'is_recoverable': False,
                'message': '任务已标记为不可恢复'
            }

        except Exception as e:
            logger.error(f"标记不可恢复失败 {task.project_id}:{task.task_id} - {e}")
            return {'action': 'failed', 'is_recoverable': False, 'message': str(e)}


class TaskStateMachine:
    """任务状态机管理器

    负责管理任务状态的转换规则和验证：
    1. 定义合法的状态转换路径
    2. 验证状态转换的合法性
    3. 提供状态变更的事务处理
    4. 记录状态变更历史
    """

    # 定义合法的状态转换规则
    VALID_TRANSITIONS = {
        TaskStatus.IDLE.value: [TaskStatus.PENDING.value],
        TaskStatus.PENDING.value: [TaskStatus.SYNCING.value, TaskStatus.CANCELLED.value, TaskStatus.ERROR.value],
        TaskStatus.SYNCING.value: [TaskStatus.EVALUATING.value, TaskStatus.ERROR.value, TaskStatus.CANCELLED.value],
        TaskStatus.EVALUATING.value: [TaskStatus.COMPLETED.value, TaskStatus.ERROR.value, TaskStatus.PAUSED.value],
        TaskStatus.PAUSED.value: [TaskStatus.EVALUATING.value, TaskStatus.CANCELLED.value],
        TaskStatus.COMPLETED.value: [TaskStatus.PENDING.value],  # 可以重新开始评测
        TaskStatus.ERROR.value: [TaskStatus.PENDING.value],      # 可以重试
        TaskStatus.CANCELLED.value: [TaskStatus.PENDING.value]   # 可以重新开始
    }

    # 终端状态（无法再转换到其他状态，除非特殊处理）
    TERMINAL_STATES = [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]

    @classmethod
    def is_valid_transition(cls, current_status, new_status):
        """检查状态转换是否合法

        Args:
            current_status: 当前状态
            new_status: 目标状态

        Returns:
            bool: 转换是否合法
        """
        if current_status not in cls.VALID_TRANSITIONS:
            logger.warning(f"未知状态: {current_status}")
            return False

        return new_status in cls.VALID_TRANSITIONS[current_status]

    @classmethod
    def get_valid_next_states(cls, current_status):
        """获取当前状态可以转换到的所有合法状态

        Args:
            current_status: 当前状态

        Returns:
            list: 可转换的状态列表
        """
        return cls.VALID_TRANSITIONS.get(current_status, [])

    @classmethod
    def is_terminal_state(cls, status):
        """检查是否为终端状态

        Args:
            status: 状态值

        Returns:
            bool: 是否为终端状态
        """
        return status in cls.TERMINAL_STATES

    @classmethod
    def validate_state_transition(cls, project_id, task_id, current_status, new_status, reason=None):
        """验证状态转换并返回详细信息

        Args:
            project_id: 项目ID
            task_id: 任务ID
            current_status: 当前状态
            new_status: 目标状态
            reason: 转换原因

        Returns:
            dict: 验证结果
        """
        result = {
            'valid': False,
            'current_status': current_status,
            'new_status': new_status,
            'reason': reason or '状态变更',
            'error_message': None
        }

        # 检查当前状态是否有效
        if current_status not in cls.VALID_TRANSITIONS:
            result['error_message'] = f'无效的当前状态: {current_status}'
            return result

        # 检查新状态是否有效
        if new_status not in cls.VALID_TRANSITIONS:
            result['error_message'] = f'无效的目标状态: {new_status}'
            return result

        # 检查转换是否合法
        if not cls.is_valid_transition(current_status, new_status):
            valid_states = cls.get_valid_next_states(current_status)
            result['error_message'] = (
                f'状态转换 {current_status} -> {new_status} 不合法。'
                f'当前状态可转换到: {", ".join(valid_states)}'
            )
            return result

        result['valid'] = True
        return result

    @classmethod
    def update_task_status_safely(cls, project_id, task_id, new_status, error_msg=None, session=None):
        """安全更新任务状态（带事务处理）

        Args:
            project_id: 项目ID
            task_id: 任务ID
            new_status: 新状态
            error_msg: 错误信息（如果状态为ERROR）
            session: 数据库会话（可选）

        Returns:
            dict: 更新结果
        """
        result = {
            'success': False,
            'old_status': None,
            'new_status': new_status,
            'message': None,
            'error': None
        }

        use_external_session = session is not None
        if not use_external_session:
            session = db.session

        try:
            # 查找任务记录
            evaluation = session.query(ProjectEvaluation).filter_by(
                project_id=project_id,
                task_id=task_id
            ).first()

            if not evaluation:
                result['error'] = f'任务不存在: {project_id}:{task_id}'
                return result

            old_status = evaluation.status
            result['old_status'] = old_status

            # 验证状态转换
            validation = cls.validate_state_transition(
                project_id, task_id, old_status, new_status
            )

            if not validation['valid']:
                result['error'] = f'状态转换验证失败: {validation["error_message"]}'
                return result

            # 记录状态变更历史
            state_change_log = {
                'timestamp': datetime.now().isoformat(),
                'old_status': old_status,
                'new_status': new_status,
                'reason': validation['reason'],
                'validation_passed': True
            }

            # 更新任务状态
            evaluation.status = new_status
            evaluation.updated_at = datetime.now()

            # 如果是错误状态，记录错误信息
            if new_status == TaskStatus.ERROR.value and error_msg:
                error_record = {
                    'timestamp': datetime.now().isoformat(),
                    'error_message': error_msg,
                    'state_change_log': state_change_log
                }

                if evaluation.evaluation_result:
                    existing_result = json.loads(evaluation.evaluation_result)
                    if isinstance(existing_result, list):
                        existing_result.append(error_record)
                    else:
                        existing_result = [existing_result, error_record]
                else:
                    existing_result = [error_record]

                evaluation.evaluation_result = json.dumps(existing_result)

            # 提交事务（如果使用外部会话，由外部管理提交）
            if not use_external_session:
                session.commit()

            logger.info(f"✅ 状态更新成功: {project_id}:{task_id} {old_status} -> {new_status}")
            result['success'] = True
            result['message'] = f'状态已从 {old_status} 更新为 {new_status}'

            return result

        except Exception as e:
            if not use_external_session:
                session.rollback()

            logger.error(f"状态更新失败 {project_id}:{task_id} - {e}")
            result['error'] = f'数据库操作失败: {str(e)}'
            return result

    @classmethod
    def create_task(cls, project_id, task_id, initial_status=None):
        """创建新任务并设置初始状态

        Args:
            project_id: 项目ID
            task_id: 任务ID
            initial_status: 初始状态（默认为PENDING）

        Returns:
            dict: 创建结果
        """
        if initial_status is None:
            initial_status = TaskStatus.PENDING.value

        # 验证初始状态
        if initial_status not in [TaskStatus.IDLE.value, TaskStatus.PENDING.value]:
            return {
                'success': False,
                'error': f'无效的初始状态: {initial_status}。必须是 IDLE 或 PENDING'
            }

        try:
            # 检查任务是否已存在
            existing_task = ProjectEvaluation.query.filter_by(
                project_id=project_id,
                task_id=task_id
            ).first()

            if existing_task:
                return {
                    'success': False,
                    'error': f'任务已存在: {project_id}:{task_id}',
                    'existing_status': existing_task.status
                }

            # 创建新任务
            new_task = ProjectEvaluation(
                project_id=project_id,
                task_id=task_id,
                status=initial_status,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            db.session.add(new_task)
            db.session.commit()

            logger.info(f"✅ 任务创建成功: {project_id}:{task_id} (状态: {initial_status})")

            return {
                'success': True,
                'task_id': task_id,
                'project_id': project_id,
                'status': initial_status,
                'message': f'任务创建成功，初始状态: {initial_status}'
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"任务创建失败 {project_id}:{task_id} - {e}")

            return {
                'success': False,
                'error': f'任务创建失败: {str(e)}'
            }

    @classmethod
    def get_task_state_history(cls, project_id, task_id):
        """获取任务状态变更历史

        Args:
            project_id: 项目ID
            task_id: 任务ID

        Returns:
            dict: 状态历史
        """
        try:
            evaluation = ProjectEvaluation.query.filter_by(
                project_id=project_id,
                task_id=task_id
            ).first()

            if not evaluation:
                return {
                    'success': False,
                    'error': f'任务不存在: {project_id}:{task_id}'
                }

            # 解析状态变更历史
            history = []
            if evaluation.evaluation_result:
                try:
                    result_data = json.loads(evaluation.evaluation_result)
                    for entry in result_data:
                        if isinstance(entry, dict) and 'state_change_log' in entry:
                            history.append(entry['state_change_log'])
                        elif isinstance(entry, dict) and 'timestamp' in entry and 'reason' in entry:
                            # 简单的状态变更记录
                            history.append(entry)
                except:
                    logger.warning(f"解析状态历史失败: {project_id}:{task_id}")

            # 添加当前状态信息
            current_info = {
                'timestamp': datetime.now().isoformat(),
                'current_status': evaluation.status,
                'last_updated': evaluation.updated_at.isoformat() if evaluation.updated_at else None,
                'created_at': evaluation.created_at.isoformat() if evaluation.created_at else None
            }

            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'current_status': evaluation.status,
                'state_history': history,
                'current_info': current_info
            }

        except Exception as e:
            logger.error(f"获取状态历史失败 {project_id}:{task_id} - {e}")
            return {
                'success': False,
                'error': f'获取状态历史失败: {str(e)}'
            }


class TaskMonitor:
    """任务监控器

    负责监控活跃任务并处理超时情况：
    1. 实时监控任务执行状态
    2. 检测和处理超时任务
    3. 提供任务健康检查
    4. 自动处理异常情况
    """

    def __init__(self):
        self.default_timeout_minutes = 30  # 默认超时时间：30分钟
        self.check_interval_seconds = 60   # 检查间隔：60秒
        self.max_consecutive_failures = 3  # 最大连续失败次数
        self.monitoring_enabled = True
        self.monitoring_thread = None
        self.stop_event = threading.Event()

        # 任务状态超时配置（分钟）
        self.state_timeouts = {
            TaskStatus.PENDING.value: 5,      # 待处理状态：5分钟
            TaskStatus.SYNCING.value: 15,     # 同步状态：15分钟
            TaskStatus.EVALUATING.value: 30,  # 评测状态：30分钟
            TaskStatus.PAUSED.value: 120      # 暂停状态：120分钟
        }

    def start_monitoring(self):
        """启动任务监控"""
        if not self.monitoring_enabled:
            logger.info("⚠️ 任务监控已禁用")
            return

        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.info("📊 任务监控已在运行中")
            return

        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="TaskMonitor",
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"📊 任务监控已启动，检查间隔: {self.check_interval_seconds}秒")

    def stop_monitoring(self):
        """停止任务监控"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.info("🛑 正在停止任务监控...")
            self.stop_event.set()
            self.monitoring_thread.join(timeout=10)
            logger.info("✅ 任务监控已停止")

    def _monitoring_loop(self):
        """监控主循环"""
        consecutive_failures = 0

        while not self.stop_event.is_set():
            try:
                # 执行健康检查
                health_result = self.perform_health_check()

                if health_result['issues_found'] > 0:
                    logger.warning(f"🔍 发现 {health_result['issues_found']} 个任务问题")

                # 检查超时任务
                timeout_result = self.check_timeout_tasks()

                if timeout_result['timeout_tasks'] > 0:
                    logger.warning(f"⏰ 发现 {timeout_result['timeout_tasks']} 个超时任务")

                # 重置失败计数
                consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"❌ 任务监控检查失败 ({consecutive_failures}/{self.max_consecutive_failures}): {e}")

                # 连续失败过多时停止监控
                if consecutive_failures >= self.max_consecutive_failures:
                    logger.error(f"🚨 任务监控连续失败 {consecutive_failures} 次，停止监控")
                    break

            # 等待下次检查
            self.stop_event.wait(self.check_interval_seconds)

    def perform_health_check(self):
        """执行任务健康检查

        Returns:
            dict: 健康检查结果
        """
        health_result = {
            'total_tasks': 0,
            'active_tasks': 0,
            'issues_found': 0,
            'issues': []
        }

        try:
            with app.app_context():
                # 查询所有活跃任务
                active_tasks = ProjectEvaluation.query.filter(
                    ProjectEvaluation.status.in_([
                        TaskStatus.PENDING.value,
                        TaskStatus.SYNCING.value,
                        TaskStatus.EVALUATING.value,
                        TaskStatus.PAUSED.value
                    ])
                ).all()

                health_result['total_tasks'] = len(active_tasks)
                health_result['active_tasks'] = len(active_tasks)

                current_time = datetime.now()

                for task in active_tasks:
                    task_age = current_time - task.created_at
                    timeout_limit = self.state_timeouts.get(
                        task.status,
                        self.default_timeout_minutes
                    )
                    timeout_threshold = timedelta(minutes=timeout_limit)

                    issues = []

                    # 检查更新时间（主要依据）
                    update_age = current_time - task.updated_at if task.updated_at else task_age
                    if update_age > timeout_threshold:
                        issues.append(f"任务在状态停留过久（{update_age.total_seconds()/60:.1f}分钟）")

                    # 检查任务状态一致性（使用update_age）
                    if task.status == TaskStatus.PENDING.value and update_age > timedelta(minutes=10):
                        issues.append("任务长时间处于待处理状态")

                    # 如果发现问题，记录到结果中
                    if issues:
                        health_result['issues_found'] += 1
                        health_result['issues'].append({
                            'project_id': task.project_id,
                            'task_id': task.task_id,
                            'status': task.status,
                            'age_minutes': task_age.total_seconds() / 60,
                            'created_at': task.created_at.isoformat(),
                            'updated_at': task.updated_at.isoformat() if task.updated_at else None,
                            'issues': issues
                        })

        except Exception as e:
            logger.error(f"健康检查执行失败: {e}")
            health_result['error'] = str(e)

        return health_result

    def check_timeout_tasks(self):
        """检查并处理超时任务

        Returns:
            dict: 超时检查结果
        """
        timeout_result = {
            'timeout_tasks': 0,
            'processed_tasks': 0,
            'failed_tasks': 0,
            'details': []
        }

        try:
            with app.app_context():
                current_time = datetime.now()
                timeout_threshold = timedelta(minutes=self.default_timeout_minutes)

                # 查询可能的超时任务
                potential_timeout_tasks = ProjectEvaluation.query.filter(
                    ProjectEvaluation.status.in_([
                        TaskStatus.PENDING.value,
                        TaskStatus.SYNCING.value,
                        TaskStatus.EVALUATING.value,
                        TaskStatus.PAUSED.value
                    ])
                ).all()

                for task in potential_timeout_tasks:
                    task_result = self._check_single_task_timeout(task, current_time)
                    timeout_result['details'].append(task_result)

                    if task_result['is_timeout']:
                        timeout_result['timeout_tasks'] += 1

                        # 尝试处理超时任务
                        if self._handle_timeout_task(task, task_result):
                            timeout_result['processed_tasks'] += 1
                        else:
                            timeout_result['failed_tasks'] += 1

        except Exception as e:
            logger.error(f"超时检查执行失败: {e}")
            timeout_result['error'] = str(e)

        return timeout_result

    def _check_single_task_timeout(self, task, current_time):
        """检查单个任务是否超时

        Args:
            task: ProjectEvaluation 实例
            current_time: 当前时间

        Returns:
            dict: 超时检查结果
        """
        task_age = current_time - task.created_at
        update_age = current_time - task.updated_at if task.updated_at else task_age

        # 获取状态特定的超时时间
        state_timeout = self.state_timeouts.get(
            task.status,
            self.default_timeout_minutes
        )
        state_timeout_threshold = timedelta(minutes=state_timeout)

        # 默认超时检查
        default_timeout_threshold = timedelta(minutes=self.default_timeout_minutes)

        result = {
            'project_id': task.project_id,
            'task_id': task.task_id,
            'status': task.status,
            'task_age_minutes': task_age.total_seconds() / 60,
            'update_age_minutes': update_age.total_seconds() / 60,
            'state_timeout_minutes': state_timeout,
            'is_timeout': False,
            'timeout_type': None,
            'timeout_reason': None
        }

        # 检查状态超时（使用update_age而不是task_age）
        if update_age > state_timeout_threshold:
            result['is_timeout'] = True
            result['timeout_type'] = 'state_timeout'
            result['timeout_reason'] = f"任务在 {task.status} 状态超过 {state_timeout} 分钟"

        # 检查默认超时（使用update_age而不是task_age）
        elif update_age > default_timeout_threshold:
            result['is_timeout'] = True
            result['timeout_type'] = 'default_timeout'
            result['timeout_reason'] = f"任务执行超过 {self.default_timeout_minutes} 分钟"

        # 检查长时间未更新
        elif update_age > state_timeout_threshold * 2:  # 更新时间的阈值更宽松
            result['is_timeout'] = True
            result['timeout_type'] = 'update_timeout'
            result['timeout_reason'] = f"任务超过 {state_timeout * 2} 分钟未更新"

        return result

    def _handle_timeout_task(self, task, timeout_info):
        """处理超时任务

        Args:
            task: ProjectEvaluation 实例
            timeout_info: 超时信息

        Returns:
            bool: 处理是否成功
        """
        try:
            logger.warning(f"⏰ 处理超时任务: {task.project_id}:{task.task_id} "
                         f"({timeout_info['timeout_reason']})")

            # 根据任务状态和超时类型采取不同处理策略
            if task.status == TaskStatus.PENDING.value:
                # 待处理任务超时：标记为错误，允许重试
                state_machine_result = TaskStateMachine.update_task_status_safely(
                    task.project_id,
                    task.task_id,
                    TaskStatus.ERROR.value,
                    f"任务待处理超时: {timeout_info['timeout_reason']}"
                )

                return state_machine_result['success']

            elif task.status in [TaskStatus.SYNCING.value, TaskStatus.EVALUATING.value]:
                # 执行中任务超时：根据超时时间决定处理方式
                task_age = timeout_info['task_age_minutes']

                if task_age > self.default_timeout_minutes * 2:
                    # 超时时间过长：标记为错误但不允许自动重试
                    timeout_record = {
                        'timestamp': datetime.now().isoformat(),
                        'timeout_type': timeout_info['timeout_type'],
                        'timeout_reason': timeout_info['timeout_reason'],
                        'task_age_minutes': task_age,
                        'action_taken': 'marked_as_error_no_retry'
                    }

                    # 更新任务状态
                    task.status = TaskStatus.ERROR.value
                    task.updated_at = datetime.now()

                    # 记录超时信息
                    if task.evaluation_result:
                        existing_result = json.loads(task.evaluation_result)
                        existing_result.append(timeout_record)
                    else:
                        existing_result = [timeout_record]

                    task.evaluation_result = json.dumps(existing_result)
                    db.session.commit()

                    logger.info(f"❌ 任务 {task.project_id}:{task.task_id} 超时过长，标记为错误（不允许重试）")
                    return True
                else:
                    # 超时时间较短：标记为错误，允许重试
                    state_machine_result = TaskStateMachine.update_task_status_safely(
                        task.project_id,
                        task.task_id,
                        TaskStatus.ERROR.value,
                        f"任务执行超时: {timeout_info['timeout_reason']}"
                    )

                    return state_machine_result['success']

            elif task.status == TaskStatus.PAUSED.value:
                # 暂停任务超时：自动取消
                state_machine_result = TaskStateMachine.update_task_status_safely(
                    task.project_id,
                    task.task_id,
                    TaskStatus.CANCELLED.value,
                    f"暂停任务超时自动取消: {timeout_info['timeout_reason']}"
                )

                return state_machine_result['success']

            else:
                logger.warning(f"未知任务状态超时: {task.project_id}:{task.task_id} ({task.status})")
                return False

        except Exception as e:
            logger.error(f"处理超时任务失败 {task.project_id}:{task.task_id} - {e}")
            return False

    def get_monitoring_status(self):
        """获取监控状态信息

        Returns:
            dict: 监控状态
        """
        return {
            'monitoring_enabled': self.monitoring_enabled,
            'is_running': self.monitoring_thread and self.monitoring_thread.is_alive(),
            'check_interval_seconds': self.check_interval_seconds,
            'default_timeout_minutes': self.default_timeout_minutes,
            'state_timeouts': self.state_timeouts,
            'start_time': getattr(self, 'start_time', None)
        }

    def update_config(self, **kwargs):
        """更新监控配置

        Args:
            **kwargs: 配置参数
        """
        if 'check_interval_seconds' in kwargs:
            self.check_interval_seconds = max(10, kwargs['check_interval_seconds'])

        if 'default_timeout_minutes' in kwargs:
            self.default_timeout_minutes = max(5, kwargs['default_timeout_minutes'])

        if 'state_timeouts' in kwargs:
            self.state_timeouts.update(kwargs['state_timeouts'])

        if 'monitoring_enabled' in kwargs:
            was_enabled = self.monitoring_enabled
            self.monitoring_enabled = kwargs['monitoring_enabled']

            # 状态改变时启动或停止监控
            if not was_enabled and self.monitoring_enabled:
                self.start_monitoring()
            elif was_enabled and not self.monitoring_enabled:
                self.stop_monitoring()

        logger.info(f"📊 任务监控配置已更新: {kwargs}")


class ThreadSafeManager:
    """线程安全管理器

    提供线程安全的数据库操作和资源管理：
    1. 线程本地存储管理
    2. 数据库连接池管理
    3. 线程锁和同步机制
    4. 资源生命周期管理
    """

    def __init__(self):
        self._local = threading.local()
        self._locks = {}
        self._connection_pool_size = 20
        self._session_timeout = 300  # 5分钟超时

    @contextmanager
    def get_session(self, with_lock=False, lock_key=None):
        """获取线程安全的数据库会话

        Args:
            with_lock: 是否使用锁
            lock_key: 锁的键名

        Yields:
            Session: 数据库会话对象
        """
        session = None
        lock = None

        try:
            # 获取或创建线程本地的会话
            if not hasattr(self._local, 'session') or not self._local.session:
                self._local.session = db.session()

            session = self._local.session

            # 如果需要锁
            if with_lock:
                lock_key = lock_key or 'default_db_lock'
                lock = self._get_lock(lock_key)
                lock.acquire()

            yield session

        except Exception as e:
            if session:
                try:
                    session.rollback()
                except:
                    pass
            logger.error(f"数据库操作异常: {e}")
            raise
        finally:
            if lock:
                lock.release()

    def _get_lock(self, key):
        """获取或创建锁对象"""
        if key not in self._locks:
            self._locks[key] = threading.RLock()
        return self._locks[key]

    @contextmanager
    def with_lock(self, key, timeout=30):
        """使用指定锁的上下文管理器

        Args:
            key: 锁的键名
            timeout: 超时时间（秒）

        Yields:
            None
        """
        lock = self._get_lock(key)
        acquired = lock.acquire(timeout=timeout)

        if not acquired:
            raise TimeoutError(f"获取锁 {key} 超时")

        try:
            yield
        finally:
            lock.release()

    def cleanup_thread_resources(self):
        """清理线程资源"""
        if hasattr(self._local, 'session'):
            try:
                self._local.session.remove()
                del self._local.session
            except:
                pass

    def get_thread_id(self):
        """获取当前线程ID"""
        return threading.current_thread().ident


class TransactionManager:
    """事务管理器

    提供增强的事务管理功能：
    1. 自动重试机制
    2. 嵌套事务支持
    3. 事务隔离级别控制
    4. 异常处理和回滚
    """

    def __init__(self, max_retries=3, retry_delay=1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.thread_manager = ThreadSafeManager()

    @contextmanager
    def transaction(self, isolation_level=None, auto_retry=True, retry_on=None):
        """事务上下文管理器

        Args:
            isolation_level: 事务隔离级别
            auto_retry: 是否自动重试
            retry_on: 需要重试的异常类型（元组）

        Yields:
            Session: 数据库会话对象
        """
        if retry_on is None:
            retry_on = (Exception,)

        session = None
        retry_count = 0
        last_exception = None

        while retry_count <= self.max_retries:
            try:
                with self.thread_manager.get_session() as session:
                    # 设置隔离级别
                    if isolation_level:
                        if hasattr(session, 'execute'):
                            session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))

                    # 开始事务
                    session.begin_nested()

                    yield session

                    # 提交事务
                    session.commit()
                    break

            except Exception as e:
                last_exception = e

                # 回滚事务
                if session:
                    try:
                        session.rollback()
                    except:
                        pass

                retry_count += 1

                # 检查是否需要重试
                if auto_retry and retry_count <= self.max_retries and any(isinstance(e, exc) for exc in retry_on):
                    logger.warning(f"事务失败，准备第 {retry_count} 次重试: {e}")
                    time.sleep(self.retry_delay * (2 ** (retry_count - 1)))  # 指数退避
                    continue
                else:
                    logger.error(f"事务最终失败: {e}")
                    break

        if last_exception and retry_count > self.max_retries:
            raise last_exception

    def execute_with_retry(self, func, *args, **kwargs):
        """带重试机制执行函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果
        """
        retry_count = 0
        last_exception = None

        while retry_count <= self.max_retries:
            try:
                with self.transaction(auto_retry=False):
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                retry_count += 1

                if retry_count <= self.max_retries:
                    logger.warning(f"函数执行失败，准备第 {retry_count} 次重试: {e}")
                    time.sleep(self.retry_delay * (2 ** (retry_count - 1)))
                    continue
                else:
                    logger.error(f"函数执行最终失败: {e}")
                    break

        if last_exception:
            raise last_exception

    def atomic_update(self, model_class, filter_conditions, update_data, **kwargs):
        """原子性更新操作

        Args:
            model_class: 模型类
            filter_conditions: 过滤条件
            update_data: 更新数据
            **kwargs: 额外参数

        Returns:
            dict: 更新结果
        """
        result = {
            'success': False,
            'affected_rows': 0,
            'error': None
        }

        try:
            with self.transaction(auto_retry=True) as session:
                query = session.query(model_class)

                # 应用过滤条件
                for key, value in filter_conditions.items():
                    if hasattr(model_class, key):
                        query = query.filter(getattr(model_class, key) == value)

                # 执行更新
                affected_rows = query.update(update_data, synchronize_session=False)

                result['success'] = True
                result['affected_rows'] = affected_rows
                result['updated_count'] = affected_rows

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"原子更新失败: {e}")

        return result

    def batch_operations(self, operations, batch_size=100):
        """批量操作管理

        Args:
            operations: 操作列表
            batch_size: 批次大小

        Returns:
            dict: 批量操作结果
        """
        result = {
            'total_operations': len(operations),
            'success_count': 0,
            'failed_count': 0,
            'failed_operations': []
        }

        try:
            with self.transaction(auto_retry=True) as session:
                for i in range(0, len(operations), batch_size):
                    batch = operations[i:i + batch_size]

                    for operation in batch:
                        try:
                            operation['func'](session, *operation.get('args', []), **operation.get('kwargs', {}))
                            result['success_count'] += 1
                        except Exception as e:
                            result['failed_count'] += 1
                            result['failed_operations'].append({
                                'operation': operation,
                                'error': str(e)
                            })

        except Exception as e:
            logger.error(f"批量操作执行失败: {e}")
            result['batch_error'] = str(e)

        return result


class GracefulShutdownManager:
    """优雅关闭管理器

    负责系统的优雅关闭：
    1. 信号处理
    2. 资源清理
    3. 任务完成等待
    4. 状态保存
    """

    def __init__(self):
        self.shutdown_requested = threading.Event()
        self.active_connections = set()
        self.active_tasks = set()
        self.shutdown_timeout = 30  # 30秒关闭超时
        self.cleanup_handlers = []

    def register_cleanup_handler(self, handler):
        """注册清理处理器"""
        self.cleanup_handlers.append(handler)

    def register_active_connection(self, connection_id):
        """注册活跃连接"""
        self.active_connections.add(connection_id)

    def unregister_active_connection(self, connection_id):
        """取消注册活跃连接"""
        self.active_connections.discard(connection_id)

    def register_active_task(self, task_id):
        """注册活跃任务"""
        self.active_tasks.add(task_id)

    def unregister_active_task(self, task_id):
        """取消注册活跃任务"""
        self.active_tasks.discard(task_id)

    def is_shutdown_requested(self):
        """检查是否请求关闭"""
        return self.shutdown_requested.is_set()

    @contextmanager
    def with_shutdown_protection(self, operation_name=None):
        """关闭保护上下文管理器"""
        if self.is_shutdown_requested():
            raise RuntimeError(f"系统正在关闭，无法执行操作: {operation_name}")

        try:
            yield
        except Exception as e:
            logger.error(f"操作 {operation_name} 执行失败: {e}")
            raise

    def wait_for_tasks_completion(self, timeout=None):
        """等待活跃任务完成"""
        timeout = timeout or self.shutdown_timeout
        start_time = time.time()

        while self.active_tasks:
            if time.time() - start_time > timeout:
                logger.warning(f"等待任务完成超时，强制关闭。剩余任务: {len(self.active_tasks)}")
                break

            logger.info(f"等待 {len(self.active_tasks)} 个任务完成...")
            time.sleep(1)

    def perform_cleanup(self):
        """执行清理操作"""
        logger.info("开始执行系统清理...")

        for handler in self.cleanup_handlers:
            try:
                if callable(handler):
                    handler()
                logger.info("清理处理器执行成功")
            except Exception as e:
                logger.error(f"清理处理器执行失败: {e}")

        # 等待连接关闭
        if self.active_connections:
            logger.info(f"等待 {len(self.active_connections)} 个连接关闭...")
            # 这里可以添加连接关闭逻辑

        logger.info("系统清理完成")

    def setup_signal_handlers(self):
        """设置信号处理器"""
        import signal

        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，开始优雅关闭...")
            self.shutdown_requested.set()

        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

        try:
            signal.signal(signal.SIGBREAK, signal_handler)  # Windows下的中断信号
        except:
            pass  # 在非Windows系统上忽略

    def graceful_shutdown(self):
        """执行优雅关闭"""
        logger.info("开始优雅关闭...")

        # 设置关闭标志
        self.shutdown_requested.set()

        # 等待任务完成
        self.wait_for_tasks_completion()

        # 执行清理
        self.perform_cleanup()

        logger.info("优雅关闭完成")


# 全局管理器实例
thread_manager = ThreadSafeManager()
transaction_manager = TransactionManager()
graceful_shutdown_manager = GracefulShutdownManager()


# ==========================================
# 4. 辅助工具函数
# ==========================================

def smart_truncate(content, max_length=3000):
    if not content: return ""
    # 确保内容是字符串类型
    if not isinstance(content, str):
        content = str(content)
    
    # 处理编码问题，确保是有效的UTF-8
    try:
        # 如果是bytes，先解码
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        # 重新编码确保没有无效字符
        content = content.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.warning(f"内容编码处理警告: {e}")
        content = str(content)
    
    # 移除控制字符，防止数据库错误
    import re
    # 移除ASCII控制字符(0-31)和DEL(127)，但保留换行符(10)和制表符(9)
    content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
    
    if len(content) <= max_length: 
        return content
    
    half = max_length // 2
    truncated = content[:half] + f"\n\n...[中间省略 {len(content) - max_length} 字]\n\n" + content[-half:]
    
    # 再次确保截断后的内容编码正确
    try:
        truncated = truncated.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.warning(f"截断后内容编码处理警告: {e}")
        truncated = str(truncated)
    
    return truncated


def calculate_hash(content):
    if not content: return ""
    return hashlib.md5(str(content).encode('utf-8')).hexdigest()


def get_external_files_from_api(project_id, task_id=None):
    """从实际API获取指定项目的文档信息

    Args:
        project_id: 项目ID
        task_id: 任务ID（可选）
    """
    try:
        logger.info(f"   🔄 正在从API获取项目 {project_id} 的文档信息...")

        # 构建请求payload，根据新接口规范包含task_id
        payload = {"project_id": project_id}
        if task_id:
            payload["task_id"] = task_id

        response = requests.post(config.GET_FILES_API, json=payload, timeout=config.API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        if isinstance(data, dict) and data.get('code') == 0:
            files_data = data.get('data', [])
            logger.info(f"   ✅ 成功获取项目 {project_id} 的 {len(files_data)} 个文档项")
            return files_data
        else:
            logger.error(f"   ❌ API返回错误: {data}")
            return []
    except Exception as e:
        logger.error(f"   ❌ 获取文档信息异常: {e}")
        return []


def get_external_files_from_json(project_id):
    """Mock数据兜底"""
    json_filename = "mock_get_file_response.json"
    if not os.path.exists(json_filename): return []
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and str(data.get('code')) == '200':
                return data.get('data', [])
            return data if isinstance(data, list) else []
    except:
        pass
    return []


def get_external_files_from_all_sources(project_id, task_id=None):
    """从所有来源获取项目文件信息

    Args:
        project_id: 项目ID
        task_id: 任务ID（可选）
    """
    if config.USE_REAL_API:
        api_data = get_external_files_from_api(project_id, task_id)
        if api_data: return api_data
        logger.warning(f"   ⚠️ API失败，使用mock数据作为备用")
    return get_external_files_from_json(project_id)


def get_project_infos_from_api():
    try:
        logger.info("   🔄 正在从API获取项目信息...")
        response = requests.post(config.GET_PROJECTS_API, timeout=config.API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get('code') == 0:
            return data.get('data', [])
    except Exception as e:
        logger.error(f"   ❌ 获取项目信息异常: {e}")
    return []


def get_project_infos_from_json():
    json_filename = "mock_get_project_response.json"
    if not os.path.exists(json_filename): return []
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and str(data.get('code')) == '200': return data.get('data', [])
            return data if isinstance(data, list) else []
    except:
        pass
    return []


if config.USE_REAL_API:
    MOCK_EXTERNAL_PROJECTS = get_project_infos_from_api() or get_project_infos_from_json()
else:
    MOCK_EXTERNAL_PROJECTS = get_project_infos_from_json()


# ==========================================
# 5. 核心业务逻辑
# ==========================================

def async_parse_file(file_info):
    """ 单个文件解析任务 """
    file_path = file_info.get('file_path')
    file_name = file_info.get('file_name')
    # 不需要 thread_name 变量，logging 模块会自动获取

    logger.info(f"🔄 开始异步解析文件: {file_name}")

    try:
        content = doc_parser.extract_content(file_path, file_info.get('file_type'),
                                             file_name) if HAS_PARSER else f"[Mock Content for {file_name}]"

        if content:
            logger.info(f"✅ 文件解析成功: {file_name} (内容长度: {len(content)})")
        else:
            logger.warning(f"⚠️ 文件解析成功但内容为空: {file_name}")

        return (file_info, content, None)
    except Exception as e:
        logger.error(f"❌ 文件解析失败: {file_name} - {str(e)}", exc_info=True)
        return (file_info, None, str(e))


def core_sync_process(project_id, raw_files_data, task_id=None):
    """ 同步文件与规则 """
    task_info = f"[任务:{task_id}] " if task_id else ""
    logger.info(f"📥 [{project_id}] {task_info}开始同步数据与提取规则...")

    project = db.session.get(Project, project_id)
    if not project:
        raise Exception("Project not found")

    # 获取或创建 ProjectEvaluation 记录
    evaluation = ProjectEvaluation.query.filter_by(
        project_id=project_id,
        task_id=task_id or 'DEFAULT_TASK'
    ).first()

    if not evaluation:
        evaluation = ProjectEvaluation(
            project_id=project_id,
            task_id=task_id or 'DEFAULT_TASK',
            status='SYNCING'
        )
        db.session.add(evaluation)
    else:
        evaluation.status = 'SYNCING'
        # 更新重新运行任务的时间戳
        evaluation.updated_at = datetime.now()

    db.session.flush()

    extracted_rules = []
    files_to_process = []
    FILE_DOWNLOAD_BASE_URL = config.FILE_DOWNLOAD_BASE_URL
    FILE_DOWNLOAD_TOKEN = config.FILE_DOWNLOAD_TOKEN

    for idx, item in enumerate(raw_files_data):
        item_name = item.get('item_name', '未命名项')
        rule_info = {
            "检查细项": item_name,
            "检查子分类": item.get('file_type_name', item_name),
            "分值": item.get('scores', 0),
            "打分说明": item.get('score_remark', '无明确打分说明')
        }
        extracted_rules.append(rule_info)

        file_list = item.get('file_list') or item.get('item_files', [])

        for file_idx, f in enumerate(file_list):
            attach_id = f.get('attach_id')
            if attach_id:
                file_url = f"{FILE_DOWNLOAD_BASE_URL}/{attach_id}?token={FILE_DOWNLOAD_TOKEN}"
                file_name = f.get('attach_name', f'{attach_id}.{f.get("attach_suffix", "")}')
                file_type = f.get('attach_suffix', '')
            else:
                file_url = f.get('file_path', '')
                file_name = f.get('file_name', f.get('name', ''))
                file_type = f.get('file_type') or f.get('type', '')

            files_to_process.append({
                "cat_id": item.get('item_id', 'unknown'),
                "cat_name": item.get('file_type_name', item_name),  # 使用file_type_name作为分类名称
                "file_type_id": item.get('file_type_id', ''),
                "f": f,
                "path": file_url,
                "name": file_name,
                "attach_id": attach_id
            })

    # 保存规则配置到 ProjectEvaluation 表
    evaluation.rules_config = json.dumps(extracted_rules, ensure_ascii=False)
    evaluation.updated_at = datetime.now()
    logger.info(f"📋 [{project_id}] {task_info}规则配置已保存，共 {len(extracted_rules)} 项规则")

    parse_tasks = []
    new_files_count = 0
    updated_files_count = 0

    for item in files_to_process:
        f_path, f_name = item['path'], item['name']
        if not f_path: continue

        curr_hash = calculate_hash(f_path + f_name)

        # 查询文件，现在包含 task_id 条件
        db_file = ProjectFile.query.filter_by(
            project_id=project_id,
            task_id=task_id or 'DEFAULT_TASK',
            category_id=item['cat_id'],
            file_name=f_name
        ).first()

        file_type = item['f'].get('attach_suffix', '') if item.get('attach_id') else (
                    item['f'].get('file_type') or item['f'].get('type', ''))

        if not db_file:
            new_files_count += 1
            db_file = ProjectFile(
                project_id=project_id,
                task_id=task_id or 'DEFAULT_TASK',
                category_id=item['cat_id'],
                category_name=item['cat_name'],
                file_name=f_name,
                file_url=f_path,
                file_type=file_type,
                file_hash=curr_hash,
                parsed_content=None
            )
            db.session.add(db_file)
            db.session.flush()
            parse_tasks.append({'file_info': item, 'db_id': db_file.id})

        elif db_file.file_hash != curr_hash or not db_file.parsed_content:
            updated_files_count += 1
            parse_tasks.append({'file_info': item, 'db_id': db_file.id})

    db.session.commit()
    logger.info(f"📊 [{project_id}] {task_info}文件入库完成 - 新增: {new_files_count}, 更新: {updated_files_count}")

    if parse_tasks:
        logger.info(f"📋 [{project_id}] {task_info}开始异步解析，共 {len(parse_tasks)} 个任务")
        future_to_id = {}
        for task in parse_tasks:
            info = task['file_info']
            file_type = info['f'].get('attach_suffix', '') if info.get('attach_id') else (
                        info['f'].get('file_type') or info['f'].get('type', ''))

            p_arg = {
                'file_path': info['path'], 'file_type': file_type,
                'file_name': info['name'], 'db_id': task['db_id']
            }
            future = doc_parser_executor.submit(async_parse_file, p_arg)
            future_to_id[future] = task['db_id']

        completed_count = 0
        error_count = 0
        for future in as_completed(future_to_id):
            p_arg, content, error = future.result()
            target_file = ProjectFile.query.get(p_arg['db_id'])
            if target_file:
                if error:
                    error_count += 1
                    target_file.parsed_content = f"[ERROR] {error}"
                    logger.error(f"❌ 解析失败: {p_arg.get('file_name')}")
                else:
                    completed_count += 1
                    # 使用smart_truncate函数截断过长的内容，防止"Data too long for column 'parsed_content'"错误
                    # 使用默认截断长度3000，确保不会超过数据库字段限制
                    target_file.parsed_content = smart_truncate(content, max_length=3000)
                    target_file.update_time = datetime.now()

                if completed_count % 5 == 0: db.session.commit()

        db.session.commit()
        logger.info(f"📋 [{project_id}] {task_info}解析汇总 - 成功: {completed_count}, 失败: {error_count}")

    return True


def core_evaluate_process(project_id, task_id=None):
    """ AI评测逻辑 """
    task_info = f"[任务:{task_id}] " if task_id else ""
    logger.info(f"🧠 [{project_id}] {task_info}开始AI评测...")

    # 获取评测记录
    evaluation = ProjectEvaluation.query.filter_by(
        project_id=project_id,
        task_id=task_id or 'DEFAULT_TASK'
    ).first()

    if not evaluation:
        raise Exception(f"未找到项目 {project_id} 任务 {task_id or 'DEFAULT_TASK'} 的评测记录")

    evaluation.status = 'EVALUATING'
    db.session.flush()

    # 1. 规则准备 - 现在从 ProjectEvaluation 表获取
    api_rules = []
    if evaluation.rules_config:
        try:
            api_rules = json.loads(evaluation.rules_config)
        except Exception as e:
            logger.error(f"规则解析失败: {e}")

    # 这里简化了原有的混合规则逻辑，假设 api_rules 为主
    rules_data = api_rules
    if not rules_data:
        # 尝试加载Excel兜底
        excel_path = config.CHECK_RULES_FILE
        if HAS_PANDAS and os.path.exists(excel_path):
            try:
                df = pd.read_excel(excel_path)
                rules_data = df.to_dict(orient='records')
                logger.info(f"使用 Excel 兜底规则: {len(rules_data)} 条")
            except Exception as e:
                logger.error(f"Excel加载失败: {e}")

    if not rules_data:
        raise Exception("无有效规则，无法评测")

    # 2. 准备上下文 - 现在按 task_id 查询文件
    all_files = ProjectFile.query.filter_by(
        project_id=project_id,
        task_id=task_id or 'DEFAULT_TASK'
    ).all()
    files_content_by_cat = {}
    for f in all_files:
        if f.parsed_content:
            if f.category_name not in files_content_by_cat: files_content_by_cat[f.category_name] = ""
            # 使用默认截断长度3000，确保不会超过数据库字段限制
            content = smart_truncate(f.parsed_content, max_length=3000)
            files_content_by_cat[f.category_name] += f"\n=== 文件：{f.file_name} ===\n{content}\n"

    # 3. 分组评测
    rules_by_cat = {}
    for r in rules_data:
        cat = r.get('检查子分类', r.get('检查细项'))
        if cat not in rules_by_cat: rules_by_cat[cat] = []
        rules_by_cat[cat].append(r)

    # 获取文件信息以建立 item_id 映射关系
    item_id_mapping = {}
    try:
        logger.info(f"   📋 [{project_id}] {task_info}获取文件信息建立item_id映射...")
        files_data = get_external_files_from_all_sources(project_id, task_id)
        if files_data and len(files_data) > 0:
            for file_item in files_data:
                # 从接口返回的数据中建立检查细项到item_id的映射
                item_name = file_item.get("item_name", "")
                file_type_name = file_item.get("file_type_name", "")
                real_item_id = file_item.get("item_id", "")

                if real_item_id and (item_name or file_type_name):
                    # 优先使用item_name，如果不存在则使用file_type_name
                    mapping_key = item_name if item_name else file_type_name
                    item_id_mapping[mapping_key] = real_item_id
                    logger.info(f"   ✅ 建立映射: {mapping_key} -> {real_item_id}")
        else:
            logger.warning(f"   ⚠️ 未能获取文件信息，将生成默认item_id")
    except Exception as e:
        logger.warning(f"   ⚠️ 获取文件信息建立映射失败: {e}")

    final_results = []

    for category, category_rules in rules_by_cat.items():
        logger.info(f"   👉 评测分类: {category}")
        category_context = files_content_by_cat.get(category, "")

        if not category_context.strip():
            for r in category_rules:
                item_name = r['检查细项']
                real_item_id = item_id_mapping.get(item_name, f"item_{len(final_results)}")
                final_results.append({
                    "item_id": real_item_id,
                    "item": item_name, "category": category, "score": 0, "maxScore": int(r['分值']),
                    "isPass": False, "reason": "未检索到相关证明材料"
                })
            continue

        simple_rules = [{"item": r['检查细项'], "criteria": r['打分说明']} for r in category_rules]
        system_prompt = """你是一名建筑工程合规审核员。请根据提供的文件内容和规则进行评分 .
        返回格式必须为 JSON 数组：[{"item": "规则名", "is_compliant": true/false, "score_logic": "理由", "reason_detail":"理由细节"}]
        评分结果需要归属于下列几类，score_logic禁止自行增减文字，详细理由写在reason_detail中：
        ① is_compliant = false ; score_logic = "材料存在，按规则评估，不符合评分要求" 
        ② is_compliant = true ; score_logic = "材料存在，按规则评估，整体符合评分要求"
        ③ is_compliant = true ; score_logic = "材料存在，但规则标准较为模糊，不足以根据材料信息给出明确判断"  
        ④ is_compliant = false ; score_logic = "缺少相关证明材料"
        """
        user_prompt = f"文件内容：\n{category_context}\n\n规则：\n{json.dumps(simple_rules, ensure_ascii=False)}"

        try:
            batch_results = []
            if HAS_ANTHROPIC and config.ZHIPU_API_KEY:
                client = anthropic.Anthropic(api_key=config.ZHIPU_API_KEY, base_url=config.ZHIPU_BASE_URL)
                response = client.messages.create(
                    model=config.ZHIPU_MODEL, max_tokens=2000,
                    system=system_prompt, messages=[{"role": "user", "content": user_prompt}]
                )
                import re
                json_match = re.search(r'\[.*\]', response.content[0].text, re.DOTALL)
                if json_match:
                    batch_results = json.loads(json_match.group())
            else:
                time.sleep(0.5)  # Mock delay
                batch_results = [{"item": r['检查细项'], "is_compliant": True, "score_logic": "Mock Pass (No AI Key)"}
                                 for r in category_rules]

            # 结果映射
            rule_map = {r['检查细项']: r for r in category_rules}
            for res in batch_results:
                target = res.get('item')
                if target in rule_map:
                    orig = rule_map[target]
                    item_name = orig['检查细项']
                    real_item_id = item_id_mapping.get(item_name, f"item_{len(final_results)}")
                    is_pass = res.get('is_compliant', False)
                    score_logic = res.get('score_logic', '')
                    if (score_logic == "材料存在，但规则标准较为模糊，不足以根据材料信息给出明确判断"):
                        is_pass = True
                        score_logic = "材料存在，按规则评估，整体符合评分要求"
                    final_results.append({
                        "item_id": real_item_id,
                        "item": item_name, "category": category,
                        "score": int(orig['分值']) if is_pass else 0,
                        "maxScore": int(orig['分值']),
                        "isPass": is_pass,
                        "reason": score_logic
                    })
                    del rule_map[target]

            # 补漏
            for r in rule_map.values():
                item_name = r['检查细项']
                real_item_id = item_id_mapping.get(item_name, f"item_{len(final_results)}")
                final_results.append({
                    "item_id": real_item_id,
                    "item": item_name, "category": category,
                    "score": 0, "maxScore": int(r['分值']),
                    "isPass": False, "reason": "未检索到相关证明材料"
                })

        except Exception as e:
            logger.error(f"AI评测异常: {e}", exc_info=True)
            for r in category_rules:
                item_name = r['检查细项']
                real_item_id = item_id_mapping.get(item_name, f"item_{len(final_results)}")
                final_results.append({
                    "item_id": real_item_id,
                    "item": item_name, "score": 0, "maxScore": int(r['分值']), "isPass": False,
                    "reason": f"系统错误: {e}"
                })

    # 从已有的 item_id_mapping 中提取真实的 check_date 和 check_person_name
    # 如果我们在建立映射时有获取文件数据，使用这些数据
    if not files_data:
        # 如果前面建立映射时没有获取到文件数据，重新获取
        try:
            logger.info(f"   📋 [{project_id}] {task_info}获取文件信息中的真实数据...")
            files_data = get_external_files_from_all_sources(project_id, task_id)
        except Exception as e:
            logger.warning(f"   ⚠️ 获取文件信息失败，使用默认值: {e}")
            files_data = []

    if files_data and len(files_data) > 0:
        # 从接口返回的数据中获取真实的 check_date 和 check_person_name
        # 根据接口文档，每个文件项都包含这些字段
        first_item = files_data[0]
        real_check_date = first_item.get("check_date")
        real_check_person_name = first_item.get("check_person_name")

        if real_check_date:
            evaluation.check_date = real_check_date
            logger.info(f"   ✅ 保存真实检查日期: {real_check_date}")

        if real_check_person_name:
            evaluation.check_person_name = real_check_person_name
            logger.info(f"   ✅ 保存真实检查人员: {real_check_person_name}")
    else:
        logger.warning(f"   ⚠️ 未能获取文件信息，将使用默认值")

    # 保存评测结果到 ProjectEvaluation 表
    evaluation.evaluation_result = json.dumps(final_results, ensure_ascii=False)
    evaluation.status = 'COMPLETED'
    evaluation.updated_at = datetime.now()

    # 同时更新 Project 表的 last_update 时间戳
    project = db.session.get(Project, project_id)
    if project:
        project.last_update = datetime.now()

    db.session.commit()
    logger.info(f"🏁 [{project_id}] {task_info}评测完成")


def async_full_pipeline_task(app_context, project_id, task_id=None):
    """ 全链路自动化任务

    Args:
        app_context: Flask应用上下文
        project_id: 项目ID
        task_id: 任务ID（可选）
    """
    # 关键修改：移除 setup_thread_logging，直接使用全局 logger
    # logger 会自动记录 threadName
    task_info = f"任务ID: {task_id}, " if task_id else ""
    logger.info(f"🚀 [{project_id}] 全链路评测任务启动... {task_info}")

    with app_context:
        try:
            raw_data = get_external_files_from_all_sources(project_id, task_id)
            if not raw_data:
                raise Exception("无法获取项目文件信息 (Mock Data Empty)")

            core_sync_process(project_id, raw_data, task_id)
            core_evaluate_process(project_id, task_id)

            # 更新 ProjectEvaluation 状态为 COMPLETED
            evaluation = ProjectEvaluation.query.filter_by(
                project_id=project_id,
                task_id=task_id or 'DEFAULT_TASK'
            ).first()
            if evaluation:
                evaluation.status = 'COMPLETED'

            db.session.commit()
            logger.info(f"✅ [{project_id}] {task_info}任务成功完成")

        except Exception as e:
            logger.error(f"❌ [{project_id}] {task_info}任务中断: {str(e)}", exc_info=True)

            # 更新 ProjectEvaluation 状态为 ERROR
            evaluation = ProjectEvaluation.query.filter_by(
                project_id=project_id,
                task_id=task_id or 'DEFAULT_TASK'
            ).first()
            if evaluation:
                evaluation.status = 'ERROR'
                evaluation.evaluation_result = json.dumps(
                    [{"reason": f"流程失败: {str(e)}", "item": "系统错误", "isPass": False}])

            db.session.commit()


# ==========================================
# 5. 前端路由 (统一服务架构)
# ==========================================

@app.route('/')
def index():
    """前端首页 - 重定向到项目列表页"""
    return send_from_directory('static', 'project/frontend_improved.html')

@app.route('/project/<path:filename>')
def serve_project(filename):
    """项目页面路由"""
    return send_from_directory('static/project', filename)

@app.route('/<path:filename>')
def serve_static(filename):
    """静态资源路由（config.js, config-manager.html等）"""
    return send_from_directory('static', filename)


# ==========================================
# 6. API 接口
# ==========================================

@app.route('/api/task_statistics', methods=['GET'])
def api_task_statistics():
    """
    获取任务状态统计信息
    返回：项目总数、运行中任务、已完成任务、异常任务的数量
    """
    try:
        # 统计各种状态的任务数量
        task_stats = {}
        total_tasks = 0

        # 定义所有可能的状态
        all_statuses = ['IDLE', 'PENDING', 'SYNCING', 'EVALUATING', 'COMPLETED', 'ERROR', 'CANCELLED', 'PAUSED']

        for status in all_statuses:
            count = ProjectEvaluation.query.filter_by(status=status).count()
            task_stats[status.lower()] = count
            total_tasks += count

        # 根据用户要求分类统计
        running_tasks = task_stats['syncing'] + task_stats['evaluating'] + task_stats['pending']
        completed_tasks = task_stats['completed']
        error_tasks = task_stats['error']

        # 获取项目总数
        total_projects = Project.query.count()

        response_data = {
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "completed_tasks": completed_tasks,
            "error_tasks": error_tasks,
            "detailed_stats": task_stats
        }

        logger.info(f"任务统计: 项目总数={total_projects}, 任务总数={total_tasks}, 运行中={running_tasks}, 已完成={completed_tasks}, 异常={error_tasks}")

        return jsonify({"code": 0, "data": response_data})

    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        return jsonify({"code": 500, "message": f"获取任务统计失败: {str(e)}"})


@app.route('/api/projects', methods=['GET'])
def api_projects():
    # 增量同步逻辑
    try:
        logger.info("开始处理 /api/projects 请求")
        external_data = MOCK_EXTERNAL_PROJECTS
        logger.info(f"外部数据数量: {len(external_data)}")

        existing_projects = {p.id: p for p in Project.query.all()}
        logger.info(f"现有项目数量: {len(existing_projects)}")

        for ext_p in external_data:
            pid = ext_p['project_id']
            if pid in existing_projects:
                db_p = existing_projects[pid]
                db_p.project_name = ext_p['project_name']
                db_p.project_code = ext_p['project_code']
                # 更新新增字段
                db_p.epc_manager = ext_p.get('epc_manager')
                db_p.entrust_manager = ext_p.get('entrust_manager')
            else:
                new_p = Project(
                    id=pid,
                    project_code=ext_p['project_code'],
                    project_name=ext_p['project_name'],
                    epc_manager=ext_p.get('epc_manager'),
                    entrust_manager=ext_p.get('entrust_manager')
                )
                db.session.add(new_p)
        db.session.commit()

        logger.info("开始查询项目列表")
        # 简化查询：获取项目列表（暂时去掉last_update排序以避免datetime2问题）
        try:
            projects = Project.query.order_by(Project.last_update.desc()).all()
        except Exception as order_error:
            logger.warning(f"按last_update排序失败: {order_error}，改为按id排序")
            projects = Project.query.order_by(Project.id.desc()).all()
        logger.info(f"查询到项目数量: {len(projects)}")

        res = []
        for i, project in enumerate(projects):
            logger.info(f"处理第{i+1}个项目: {project.id}")
            # 统计每个项目的任务数量
            task_count = db.session.query(ProjectEvaluation).filter_by(project_id=project.id).count()

            res.append({
                "project_id": project.id,
                "project_name": project.project_name or "",
                "project_code": project.project_code or "",
                "epc_manager": project.epc_manager or "",  # 项目经理
                "entrust_manager": project.entrust_manager or "",  # 项目执行经理
                "status": "IDLE",  # 简化状态显示
                "task_count": task_count,
                "last_update": safe_datetime_format(project.last_update)
            })

        logger.info("成功构建响应数据")
        return jsonify({"code": 0, "data": res})
    except Exception as e:
        import traceback
        logger.error(f"API Error: {e}")
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({"code": 500, "message": str(e)})


@app.route('/api/task/concurrency/status', methods=['GET'])
def get_task_concurrency_status():
    """
    获取当前任务并发状态
    用于前端显示并发限制和当前运行任务数量
    """
    logger.info("🔍 收到并发状态查询请求")

    try:
        with task_management_lock:
            status_info = check_task_concurrency_limit()

        # 增加配置信息
        status_info['config'] = {
            'max_concurrent_tasks': GLOBAL_CONFIG['MAX_CONCURRENT_TASKS'],
            'running_states': GLOBAL_CONFIG['RUNNING_STATES'],
            'rerunnable_states': GLOBAL_CONFIG['RERUNNABLE_STATES']
        }

        logger.info(f"✅ 并发状态查询成功: {status_info}")

        return jsonify({
            "code": 0,
            "message": "获取并发状态成功",
            "data": status_info
        })

    except Exception as e:
        logger.error(f"❌ 获取并发状态失败: {e}")
        return jsonify({
            "code": 500,
            "message": f"获取并发状态失败: {str(e)}",
            "data": None
        })

@app.route('/api/start_evaluation', methods=['POST'])
def api_start_evaluation():
    try:
        # 参数验证
        if not request.is_json:
            return jsonify({"code": 400, "message": "请求必须为JSON格式"})

        data = request.get_json()
        project_id = data.get('project_id')
        task_id = data.get('task_id')  # 新增task_id参数（可选）

        # 必填参数检查
        if not project_id:
            return jsonify({"code": 400, "message": "项目ID缺失"})

        # 并发控制检查
        with task_management_lock:
            concurrency_status = check_task_concurrency_limit()

        if not concurrency_status['is_allowed']:
            running_task_ids = [task['task_id'] for task in concurrency_status['running_tasks']]
            return jsonify({
                "code": 409,  # 409 Conflict 表示资源冲突
                "message": f"已达到最大并发任务数限制（{concurrency_status['max_count']}个）。当前运行任务：{', '.join(running_task_ids)}",
                "data": {
                    "current_count": concurrency_status['current_count'],
                    "max_count": concurrency_status['max_count'],
                    "running_tasks": concurrency_status['running_tasks']
                }
            })

        # 可选参数task_id的提示（如果将来需要）
        if task_id:
            logger.info(f"🚀 启动评测 - 项目ID: {project_id}, 任务ID: {task_id}")
        else:
            logger.info(f"🚀 启动评测 - 项目ID: {project_id}")

        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({"code": 500, "message": "项目不存在或系统错误"})

        # 检查是否有正在运行的任务（支持task_id隔离）
        evaluation = ProjectEvaluation.query.filter_by(
            project_id=project_id,
            task_id=task_id or 'DEFAULT_TASK'
        ).first()

        if evaluation and evaluation.status in ['SYNCING', 'EVALUATING']:
            task_desc = f"任务 {task_id}" if task_id else "默认任务"
            return jsonify({"code": 409, "message": "该项目正在进行评测中，请勿重复提交"})

        # 创建或更新 ProjectEvaluation 记录
        if not evaluation:
            evaluation = ProjectEvaluation(
                project_id=project_id,
                task_id=task_id or 'DEFAULT_TASK',
                status='EVALUATING'
            )
            db.session.add(evaluation)
        else:
            evaluation.status = 'EVALUATING'

        db.session.commit()

        # 启动线程，传递task_id（如果提供）
        thread = threading.Thread(target=async_full_pipeline_task, args=(app.app_context(), project_id, task_id))
        thread.start()

        return jsonify({"code": 200, "message": "评测已启动"})
    except Exception as e:
        logger.error(f"Start Error: {e}")
        return jsonify({"code": 500, "message": str(e)})


@app.route('/api/get_result', methods=['GET'])
def api_get_result():
    try:
        # 参数验证
        project_id = request.args.get('project_id')
        task_id = request.args.get('task_id')  # task_id参数（必选）

        # 必填参数检查
        if not project_id:
            return jsonify({"code": 400, "message": "项目ID缺失"})

        if not task_id:
            return jsonify({"code": 400, "message": "任务ID缺失"})

        # 记录请求信息（project_id和task_id都是必选参数）
        logger.info(f"📊 查询评测结果 - 项目ID: {project_id}, 任务ID: {task_id}")

        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({"code": 500, "message": "项目不存在或系统错误"})

        # 获取评测记录（task_id是必选参数）
        evaluation = ProjectEvaluation.query.filter_by(
            project_id=project_id,
            task_id=task_id
        ).first()

        if not evaluation:
            return jsonify({"code": 500, "message": f"未找到项目 {project_id} 的任务 {task_id} 评测记录"})

        # 从数据库读取真实的check_date和check_person_name
        check_date = evaluation.check_date if evaluation.check_date else (evaluation.created_at.strftime("%Y-%m-%d") if evaluation.created_at else "")
        check_person_name = evaluation.check_person_name if evaluation.check_person_name else "AI质检员"

        logger.info(f"   ✅ 从数据库获取真实数据: 检查日期={check_date}, 检查人员={check_person_name}")

        # 构建响应数据，严格按照文档规范
        data = {
            "project_id": project.id,
            "project_code": project.project_code if project.project_code else "",
            "project_name": project.project_name if project.project_name else "",
            "epc_manager": project.epc_manager if project.epc_manager else "",  # 项目经理
            "entrust_manager": project.entrust_manager if project.entrust_manager else "",  # 项目执行经理
            "check_date": check_date,
            "check_person_name": check_person_name,
            "status": evaluation.status,
            "last_update": evaluation.updated_at.strftime("%Y-%m-%d %H:%M:%S") if evaluation.updated_at else "",
            "evaluation_details": []
        }

        # 解析评测详情（从 ProjectEvaluation 表获取）
        if evaluation.evaluation_result:
            try:
                evaluation_data = json.loads(evaluation.evaluation_result)
                # 确保返回的是数组格式，并按照文档要求格式化每个条目
                if isinstance(evaluation_data, list):
                    formatted_details = []
                    for item in evaluation_data:
                        # 查询该检查细项相关的文件
                        item_name = item.get("item", item.get("检查细项", ""))
                        files_for_item = []

                        if item_name:
                            # 查询与该检查细项名称相关的文件
                            files = ProjectFile.query.filter_by(
                                project_id=project_id,
                                task_id=task_id
                            ).all()

                            files_for_item = [{"file_name": f.file_name, "file_type": f.file_type} for f in files if item_name in f.file_name]

                        # 按照文档格式要求标准化每个评测项
                        formatted_item = {
                            "item_id": item.get("item_id", item.get("id", f"item_{len(formatted_details)}")),  # 新增item_id字段
                            "item": item.get("item", item.get("检查细项", "未知项目")),
                            "category": item.get("category", item.get("检查子分类", "未分类")),
                            "score": item.get("score", 0),
                            "maxScore": item.get("maxScore", item.get("分值", 0)),
                            "isPass": item.get("isPass", item.get("is_compliant", False)),
                            "reason": item.get("reason", item.get("score_logic", item.get("打分说明", ""))),
                            "file_list": files_for_item
                        }
                        formatted_details.append(formatted_item)
                    data["evaluation_details"] = formatted_details
                elif isinstance(evaluation_data, dict):
                    # 如果是字典格式，尝试提取相关字段
                    if "evaluation_details" in evaluation_data:
                        details_list = evaluation_data["evaluation_details"]
                        if isinstance(details_list, list):
                            formatted_details = []
                            for item in details_list:
                                formatted_item = {
                                    "item": item.get("item", item.get("检查细项", "未知项目")),
                                    "category": item.get("category", item.get("检查子分类", "未分类")),
                                    "score": item.get("score", 0),
                                    "maxScore": item.get("maxScore", item.get("分值", 0)),
                                    "isPass": item.get("isPass", item.get("is_compliant", False)),
                                    "reason": item.get("reason", item.get("score_logic", item.get("打分说明", "")))
                                }
                                formatted_details.append(formatted_item)
                            data["evaluation_details"] = formatted_details
                        else:
                            # 单个项目
                            item = details_list
                            formatted_item = {
                                "item_id": item.get("item_id", item.get("id", f"item_{len(formatted_details)}")),  # 新增item_id字段
                                "item": item.get("item", item.get("检查细项", "未知项目")),
                                "category": item.get("category", item.get("检查子分类", "未分类")),
                                "score": item.get("score", 0),
                                "maxScore": item.get("maxScore", item.get("分值", 0)),
                                "isPass": item.get("isPass", item.get("is_compliant", False)),
                                "reason": item.get("reason", item.get("score_logic", item.get("打分说明", "")))
                            }
                            data["evaluation_details"] = [formatted_item]
                    else:
                        # 将字典转换为单条记录
                        formatted_item = {
                            "item_id": evaluation_data.get("item_id", evaluation_data.get("id", "item_0")),  # 新增item_id字段
                            "item": evaluation_data.get("item", evaluation_data.get("检查细项", "未知项目")),
                            "category": evaluation_data.get("category", evaluation_data.get("检查子分类", "未分类")),
                            "score": evaluation_data.get("score", 0),
                            "maxScore": evaluation_data.get("maxScore", evaluation_data.get("分值", 0)),
                            "isPass": evaluation_data.get("isPass", evaluation_data.get("is_compliant", False)),
                            "reason": evaluation_data.get("reason", evaluation_data.get("score_logic", evaluation_data.get("打分说明", "")))
                        }
                        data["evaluation_details"] = [formatted_item]
            except json.JSONDecodeError as e:
                logger.warning(f"评测结果JSON解析失败: {e}")
                data["evaluation_details"] = []

        return jsonify({"code": 200, "data": data})
    except Exception as e:
        logger.error(f"Get Result Error: {e}")
        return jsonify({"code": 500, "message": str(e)})


def reset_stuck_tasks():
    """使用智能任务恢复管理器替换简单粗暴的重置逻辑"""
    with app.app_context():
        try:
            # 创建智能任务恢复管理器实例
            recovery_manager = TaskRecoveryManager()

            # 执行智能任务恢复
            recovery_stats = recovery_manager.recover_stuck_tasks()

            # 记录恢复统计信息
            total_tasks = recovery_stats['total_checked']
            if total_tasks > 0:
                logger.info(f"🎯 智能任务恢复完成:")
                logger.info(f"   • 总检查任务数: {total_tasks}")
                logger.info(f"   • 可恢复任务数: {recovery_stats['recoverable_tasks']}")
                logger.info(f"   • 成功恢复任务数: {recovery_stats['recovered_tasks']}")
                logger.info(f"   • 失败任务数: {recovery_stats['failed_tasks']}")
                logger.info(f"   • 忽略任务数: {recovery_stats['ignored_tasks']}")
            else:
                logger.info("✅ 系统启动检查：无卡住任务")

        except Exception as e:
            logger.error(f"❌ 智能任务恢复失败，回退到基础重置: {e}")

            # 回退到基础重置逻辑
            try:
                stuck_evaluations = ProjectEvaluation.query.filter(
                    ProjectEvaluation.status.in_(['SYNCING', 'EVALUATING'])
                ).all()

                for evaluation in stuck_evaluations:
                    evaluation.status = 'ERROR'
                    evaluation.evaluation_result = json.dumps([{
                        "reason": "服务重启，任务被重置（回退模式）",
                        "item": "系统错误",
                        "isPass": False
                    }])

                if stuck_evaluations:
                    db.session.commit()
                    logger.info(f"🔄 回退模式：重置了 {len(stuck_evaluations)} 个卡住的任务")

            except Exception as fallback_error:
                logger.error(f"❌ 回退重置也失败: {fallback_error}")


@app.route('/api/projects/<project_id>/tasks', methods=['GET'])
def get_project_tasks(project_id):
    """获取指定项目的所有任务历史记录"""
    try:
        # 参数验证
        if not project_id:
            return jsonify({
                "code": 400,
                "message": "项目ID不能为空",
                "data": None
            }), 400

        # 分页参数
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # 限制最大100条
        status_filter = request.args.get('status', '')

        logger.info(f"获取项目任务历史: project_id={project_id}, page={page}, per_page={per_page}")

        # 构建查询
        query = ProjectEvaluation.query.filter_by(project_id=project_id)

        # 状态筛选
        if status_filter and status_filter != 'all':
            query = query.filter_by(status=status_filter.upper())

        # 按创建时间倒序排列
        query = query.order_by(ProjectEvaluation.created_at.desc())

        # 分页查询
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 格式化任务数据
        tasks = []
        for task in pagination.items:
            # 解析评测结果
            evaluation_result = []
            if task.evaluation_result:
                try:
                    evaluation_result = json.loads(task.evaluation_result) if isinstance(task.evaluation_result, str) else task.evaluation_result
                except json.JSONDecodeError:
                    evaluation_result = [{"item": "解析错误", "reason": "评测结果格式错误", "isPass": False}]

            # 计算通过率
            total_items = len(evaluation_result)
            passed_items = sum(1 for item in evaluation_result if item.get('isPass', False))
            pass_rate = (passed_items / total_items * 100) if total_items > 0 else 0

            # 获取文件数量（按任务统计）
            file_count = ProjectFile.query.filter_by(project_id=project_id, task_id=task.task_id or 'DEFAULT_TASK').count()

            tasks.append({
                "id": task.id,
                "task_id": task.task_id or "默认任务",
                "status": task.status,
                "file_count": file_count,
                "pass_rate": round(pass_rate, 1),
                "total_items": total_items,
                "passed_items": passed_items,
                "check_person_name": task.check_person_name,  # 新增：任务发起人
                "created_at": task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "updated_at": task.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                "has_result": bool(evaluation_result),
                "result_preview": evaluation_result[:3] if evaluation_result else []  # 前3个结果作为预览
            })

        # 获取项目基本信息
        project = db.session.get(Project, project_id)
        project_info = None
        if project:
            # 安全的datetime格式化处理
            last_update_str = None
            if project.last_update:
                try:
                    if isinstance(project.last_update, str):
                        last_update_str = project.last_update
                    elif hasattr(project.last_update, 'strftime'):
                        last_update_str = project.last_update.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        last_update_str = str(project.last_update)
                except Exception as date_error:
                    logger.warning(f"日期格式化失败 project_id={project.id}: {date_error}")
                    last_update_str = None

            project_info = {
                "project_id": project.id,
                "project_name": project.project_name,
                "project_code": project.project_code,
                "epc_manager": project.epc_manager,  # 项目经理
                "entrust_manager": project.entrust_manager,  # 项目执行经理
                "last_update": last_update_str
            }

        # 构建响应
        response_data = {
            "project": project_info,
            "tasks": tasks,
            "pagination": {
                "current_page": page,
                "total_pages": pagination.pages,
                "total_items": pagination.total,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        }

        logger.info(f"成功获取项目任务历史: {len(tasks)} 条记录")

        return jsonify({
            "code": 0,
            "message": "获取项目任务历史成功",
            "data": response_data
        })

    except Exception as e:
        logger.error(f"获取项目任务历史失败: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取项目任务历史失败: {str(e)}",
            "data": None
        }), 500


@app.route('/api/projects/<project_id>/stats', methods=['GET'])
def get_project_stats(project_id):
    """获取指定项目的统计信息"""
    try:
        # 参数验证
        if not project_id:
            return jsonify({
                "code": 400,
                "message": "项目ID不能为空",
                "data": None
            }), 400

        logger.info(f"获取项目统计信息: project_id={project_id}")

        # 获取项目基本信息
        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({
                "code": 404,
                "message": "项目不存在",
                "data": None
            }), 404

        # 获取任务统计
        total_tasks = ProjectEvaluation.query.filter_by(project_id=project_id).count()

        # 状态统计
        status_counts = {}
        for status in ['IDLE', 'PENDING', 'SYNCING', 'EVALUATING', 'COMPLETED', 'ERROR', 'CANCELLED', 'PAUSED']:
            count = ProjectEvaluation.query.filter_by(project_id=project_id, status=status).count()
            status_counts[status.lower()] = count

        # 计算成功率（基于已完成的任务）
        completed_tasks = status_counts['completed']
        successful_tasks = 0

        if completed_tasks > 0:
            # 统计通过率>80%的任务数量
            completed_evaluations = ProjectEvaluation.query.filter_by(
                project_id=project_id,
                status='COMPLETED'
            ).all()

            for eval_record in completed_evaluations:
                try:
                    if eval_record.evaluation_result:
                        result_data = json.loads(eval_record.evaluation_result) if isinstance(eval_record.evaluation_result, str) else eval_record.evaluation_result
                        if isinstance(result_data, list) and len(result_data) > 0:
                            passed_items = sum(1 for item in result_data if item.get('isPass', False))
                            pass_rate = (passed_items / len(result_data)) * 100
                            if pass_rate >= 80:
                                successful_tasks += 1
                except (json.JSONDecodeError, TypeError):
                    pass

        success_rate = (successful_tasks / completed_tasks * 100) if completed_tasks > 0 else 0

        # 最近任务信息
        recent_task = ProjectEvaluation.query.filter_by(project_id=project_id).order_by(
            ProjectEvaluation.updated_at.desc()
        ).first()

        # 文件统计
        file_count = ProjectFile.query.filter_by(project_id=project_id).count()

        # 时间统计
        first_task = ProjectEvaluation.query.filter_by(project_id=project_id).order_by(
            ProjectEvaluation.created_at.asc()
        ).first()

        stats_data = {
            "project_info": {
                "project_id": project.id,
                "project_name": project.project_name,
                "project_code": project.project_code,
                "epc_manager": project.epc_manager,  # 项目经理
                "entrust_manager": project.entrust_manager  # 项目执行经理
            },
            "task_statistics": {
                "total_tasks": total_tasks,
                "running_tasks": status_counts['evaluating'] + status_counts['syncing'],
                "completed_tasks": completed_tasks,
                "error_tasks": status_counts['error'],
                "success_rate": round(success_rate, 1),
                "status_distribution": status_counts
            },
            "file_statistics": {
                "total_files": file_count
            },
            "recent_activity": {
                "last_task_id": recent_task.task_id if recent_task and recent_task.task_id else "默认任务",
                "last_task_status": recent_task.status if recent_task else 'IDLE',
                "last_update": recent_task.updated_at.strftime('%Y-%m-%d %H:%M:%S') if recent_task else None
            },
            "time_range": {
                "first_task_created": first_task.created_at.strftime('%Y-%m-%d %H:%M:%S') if first_task else None,
                "project_duration_days": (datetime.now() - first_task.created_at).days if first_task and first_task.created_at else 0
            }
        }

        logger.info(f"成功获取项目统计信息: project_id={project_id}, total_tasks={total_tasks}")

        return jsonify({
            "code": 0,
            "message": "获取项目统计信息成功",
            "data": stats_data
        })

    except Exception as e:
        logger.error(f"获取项目统计信息失败: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取项目统计信息失败: {str(e)}",
            "data": None
        }), 500


if __name__ == '__main__':
    # 1. 设置优雅关闭处理器
    graceful_shutdown_manager.setup_signal_handlers()

    # 2. 注册清理处理器
    def cleanup_resources():
        """资源清理处理器"""
        logger.info("执行资源清理...")
        # 清理线程资源
        thread_manager.cleanup_thread_resources()

    graceful_shutdown_manager.register_cleanup_handler(cleanup_resources)

    # 3. 执行智能任务恢复
    reset_stuck_tasks()

    # 4. 初始化并启动任务监控器
    task_monitor = TaskMonitor()
    task_monitor.start_monitoring()

    print("\n🚀 后端服务 V6.1 (企业级稳定性版) 启动")
    print("📊 任务监控器已启动 - 自动检测和恢复卡住任务")
    print("🔧 智能任务恢复已启用 - 基于时间策略的任务恢复")
    print("⚙️ 任务状态机已激活 - 严格的状态转换管理")
    print("⏰ 超时控制已开启 - 自动处理长时间运行的任务")
    print("🔒 线程安全管理已启用 - 多线程环境数据一致性保障")
    print("💾 事务管理优化已启用 - 自动重试和原子性操作")
    print("🛡️ 优雅关闭机制已激活 - 信号处理和资源清理")

    # 5. 启动 Flask 服务
    CORS(app,
     resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": "*"}},
     supports_credentials=True)

    try:
        app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 收到中断信号，开始优雅关闭...")
        graceful_shutdown_manager.graceful_shutdown()
        print("✅ 服务已安全停止")
    except Exception as e:
        print(f"\n❌ 服务启动失败: {e}")
        graceful_shutdown_manager.graceful_shutdown()
        raise