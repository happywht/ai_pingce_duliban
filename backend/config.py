"""
配置管理模块 - 使用环境变量管理敏感配置
"""
import os
import urllib.parse
from typing import List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """配置类"""

    # ==============================
    # 1. 数据库配置 (新增)
    # ==============================
    # 类型: sqlite, mysql, postgresql, mssql
    DB_TYPE = os.getenv('DB_TYPE', 'sqlite').lower()

    # 数据库连接详情
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'project_eval')

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """根据 DB_TYPE 动态生成连接字符串"""
        if self.DB_TYPE == 'mysql':
            # 需安装: pip install pymysql
            # 对密码进行URL编码，处理特殊字符如 @
            encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
            return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

        elif self.DB_TYPE == 'postgresql':
            # 需安装: pip install psycopg2-binary
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

        elif self.DB_TYPE == 'mssql':
            # 需安装: pip install pyodbc
            # 使用 ODBC Driver 13 for SQL Server，兼容 Windows Server 2008
            encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
            return f"mssql+pyodbc://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?driver=ODBC+Driver+13+for+SQL+Server&TrustServerCertificate=yes"

        else:
            # 默认 SQLite
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, 'project_eval.db')
            return 'sqlite:///' + db_path

    # ==============================
    # 2. AI配置
    # ==============================
    ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
    ZHIPU_BASE_URL = os.getenv('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/anthropic')
    ZHIPU_MODEL = os.getenv('ZHIPU_MODEL', 'glm-4.5')

    # ==============================
    # 3. 系统配置
    # ==============================
    MAX_CONCURRENT_PROJECTS = int(os.getenv('MAX_CONCURRENT_PROJECTS', '3'))

    @property
    def SUPPORTED_FILE_TYPES(self) -> List[str]:
        """支持的文件类型"""
        file_types = os.getenv('SUPPORTED_FILE_TYPES', '.pdf,.doc,.docx')
        return [ext.strip() for ext in file_types.split(',')]

    OCR_ENABLED = os.getenv('OCR_ENABLED', 'true').lower() == 'true'
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))

    # 缓存配置
    ENABLE_CACHE = os.getenv('ENABLE_CACHE', 'true').lower() == 'true'
    CACHE_EXPIRE_HOURS = int(os.getenv('CACHE_EXPIRE_HOURS', '24'))

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    # 优化日志格式，增加线程ID，方便调试多线程问题
    LOG_FORMAT = os.getenv('LOG_FORMAT',
                           '%(asctime)s - %(levelname)s - [%(threadName)s] - %(module)s.%(funcName)s:%(lineno)d - %(message)s')

    # 模糊匹配阈值
    FUZZY_MATCH_THRESHOLD = float(os.getenv('FUZZY_MATCH_THRESHOLD', '0.8'))

    # Flask配置
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

    # 文件路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    CACHE_DIR = os.path.join(BASE_DIR, "cache")
    MOCK_DATA_DIR = os.path.join(BASE_DIR, "mock_data")

    # 检查规则Excel文件路径
    @property
    def CHECK_RULES_FILE(self):
        return os.path.join(self.MOCK_DATA_DIR, "check_rules", "检查规则表.xlsx")

    # API配置
    USE_REAL_API = os.getenv('USE_REAL_API', 'true').lower() == 'true'
    API_BASE_URL = os.getenv('API_BASE_URL', 'http://10.1.24.200:8080/restcloud/internalapi')
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))

    @property
    def GET_PROJECTS_API(self):
        return f"{self.API_BASE_URL}/etl_flow_197088172500"

    @property
    def GET_FILES_API(self):
        return f"{self.API_BASE_URL}/etl_flow_197088172501"

    # 文件下载配置
    FILE_DOWNLOAD_BASE_URL = os.getenv('FILE_DOWNLOAD_BASE_URL',
                                       'http://epcm.sucdri.com:8090/com.cunion.oa.file/file/DownloadFile')
    FILE_DOWNLOAD_TOKEN = os.getenv('FILE_DOWNLOAD_TOKEN', '747dfd68f9214c9786300bc6651b6ac2')

    def validate_config(self):
        """验证必要的配置项"""
        errors = []
        if not self.ZHIPU_API_KEY:
            errors.append("ZHIPU_API_KEY 未配置")
        if self.MAX_CONCURRENT_PROJECTS < 1:
            errors.append("MAX_CONCURRENT_PROJECTS 必须大于0")

        # 验证数据库配置
        if self.DB_TYPE in ['mysql', 'postgresql', 'mssql'] and not self.DB_HOST:
            errors.append(f"使用 {self.DB_TYPE} 时必须配置 DB_HOST")

        if errors:
            raise ValueError("配置验证失败：" + "; ".join(errors))
        return True

  
    def get_ai_config(self):
        return {
            'apiKey': self.ZHIPU_API_KEY,
            'baseUrl': self.ZHIPU_BASE_URL,
            'model': self.ZHIPU_MODEL
        }

config = Config()
# 验证配置
try:
    config.validate_config()
    print("[OK] 配置验证通过")
except ValueError as e:
    print(f"[ERROR] 配置验证失败: {e}")
    print("请检查 .env 文件中的配置项")