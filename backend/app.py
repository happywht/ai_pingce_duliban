#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
后端服务启动入口
使用说明：
1. 复制 .env.sqlserver.example 为 .env 并配置数据库连接
2. 直接运行此脚本或打包后的 exe 文件启动服务
"""

import os
import sys

# 获取项目根目录（backend的父目录）
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 确保backend目录和项目根目录都在Python路径中
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 检查配置文件（在项目根目录）
env_file = os.path.join(current_dir, '.env')
env_example = os.path.join(current_dir, '.env.sqlserver.example')

if not os.path.exists(env_file):
    if os.path.exists(env_example):
        print("⚠️  未找到 .env 配置文件")
        print(f"✅ 发现示例配置文件: {env_example}")
        print("请复制示例文件为 .env 并配置数据库连接信息")
        print(f"cp {env_example} {env_file}")
        input("按回车键退出...")
        sys.exit(1)
    else:
        print("❌ 未找到配置文件 .env 或 .env.sqlserver.example")
        input("按回车键退出...")
        sys.exit(1)

try:
    # 导入并启动主应用
    from backend_service1126 import app

    if __name__ == '__main__':
        print("🚀 启动后端服务...")
        print("📍 工作目录:", current_dir)
        print("🔧 配置文件:", env_file)
        print("-" * 50)

        # 启动服务
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True
        )

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保所有依赖已安装:")
    print("pip install flask flask-cors flask-sqlalchemy requests pyodbc")
    input("按回车键退出...")
    sys.exit(1)
except Exception as e:
    print(f"❌ 启动失败: {e}")
    input("按回车键退出...")
    sys.exit(1)