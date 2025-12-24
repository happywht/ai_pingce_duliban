#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
后端服务启动脚本
专门解决打包后的编码问题
"""

import sys
import os

# 设置控制台编码为UTF-8 (仅Windows)
if sys.platform == 'win32':
    import subprocess
    try:
        # 尝试设置控制台编码为UTF-8
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
    except:
        pass

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    # 导入并启动主应用
    from backend_service1126 import app

    if __name__ == '__main__':
        print("=" * 50)
        print("后端服务启动器 V6.1 (完整版)")
        print("=" * 50)
        print("工作目录:", current_dir)
        print("数据库类型: SQL Server")
        print("文档解析: 支持 PDF, DOCX, Excel, 图片OCR")
        print("=" * 50)

        # 启动服务
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True
        )

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保所有依赖已正确打包")
    input("按回车键退出...")
    sys.exit(1)
except Exception as e:
    print(f"启动失败: {e}")
    input("按回车键退出...")
    sys.exit(1)