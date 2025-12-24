import http.server
import socketserver
import webbrowser
import os

# 获取当前脚本所在目录（frontend目录）
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

PORT = 8100
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"🚀 前端服务器启动成功!")
    print(f"📍 访问地址: http://localhost:{PORT}")
    print(f"📄 项目列表: http://localhost:{PORT}/project/frontend_improved.html")
    print(f"🔍 项目详情: http://localhost:{PORT}/project/project-detail.html?project_id=YOUR_PROJECT_ID")
    print(f"📊 评测结果: http://localhost:{PORT}/project/ai_pingce_result.html?project_id=YOUR_PROJECT_ID&task_id=YOUR_TASK_ID")
    print("按 Ctrl+C 停止服务器")

    # 自动打开浏览器
    webbrowser.open(f'http://localhost:{PORT}/project/frontend_improved.html')

    httpd.serve_forever()