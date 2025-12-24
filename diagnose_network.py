#!/usr/bin/env python3
"""
网络连接诊断工具
专门用于测试到10.1.24.73的连接性
"""

import socket
import subprocess
import platform

def ping_server(server_ip, port=1433, timeout=5):
    """测试服务器连接"""
    print(f"🔍 测试连接到 {server_ip}:{port}")

    # 1. 基础ping测试
    print(f"   📡 执行ping测试...")
    try:
        if platform.system().lower() == 'windows':
            # Windows使用系统ping命令
            result = subprocess.run(
                ['ping', '-n', '4', server_ip],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                print(f"   ✅ Ping测试成功")
                # 检查响应时间
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Average' in line or '平均' in line:
                        print(f"   📊 {line.strip()}")
                        break
            else:
                print(f"   ❌ Ping测试失败: {result.stderr}")
                return False
        else:
            print(f"   📡 执行ping测试...")
            result = subprocess.run(
                ['ping', '-c', '4', server_ip],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                print(f"   ✅ Ping测试成功")
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Average' in line or '平均' in line or 'rtt' in line.lower():
                        print(f"   📊 {line.strip()}")
                        break
            else:
                print(f"   ❌ Ping测试失败: {result.stderr}")
                return False
    except Exception as e:
        print(f"   ❌ Ping测试异常: {e}")
        return False

    # 2. TCP端口测试
    print(f"   🔌 测试TCP端口{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        result = sock.connect_ex((server_ip, port))
        sock.close()

        if result == 0:
            print(f"   ✅ TCP端口{port}连接成功")
            return True
        else:
            print(f"   ❌ TCP端口{port}连接失败，错误码: {result}")
            return False
    except Exception as e:
        print(f"   ❌ TCP端口测试异常: {e}")
        return False

def check_sql_server_status():
    """检查SQL Server服务状态"""
    print(f"🔍 检查SQL Server相关服务...")

    try:
        # 检查SQL Server Windows服务
        if platform.system().lower() == 'windows':
            print(f"   📋 检查Windows服务...")
            result = subprocess.run(
                ['sc', 'query', 'state=', 'type=', 'service', 'name=*SQL*'],
                capture_output=True,
                text=True,
                timeout=10
            )

            services = result.stdout.strip().split('\n')
            sql_services = [s.strip() for s in services if 'SQL' in s and 'RUNNING' in s]

            if sql_services:
                print(f"   ✅ 找到运行的SQL Server服务:")
                for service in sql_services:
                    if service:
                        print(f"      🚀 {service}")
                return True
            else:
                print(f"   ❌ 未找到运行的SQL Server服务")
                return False
        else:
            print(f"   📋 非Windows系统，跳过服务检查")

    except Exception as e:
        print(f"   ❌ 检查服务状态异常: {e}")
        return False

def check_firewall():
    """检查防火墙状态"""
    print(f"🔍 检查防火墙配置...")

    try:
        if platform.system().lower() == 'windows':
            print(f"   📋 检查Windows防火墙...")

            # 检查防火墙是否启用
            result = subprocess.run(
                ['netsh', 'advfirewall', 'show', 'currentprofile'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if 'Domain Profile' in result.stdout:
                print(f"   ✅ 防火墙已启用")

                # 检查1433端口规则
                port_result = subprocess.run(
                    ['netsh', 'advfirewall', 'firewall', 'rule', 'name', 'Port 1433'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if 'Enabled' in port_result.stdout:
                    print(f"   ✅ 发现1433端口规则")
                else:
                    print(f"   ⚠️ 未发现1433端口规则，可能需要添加")
            else:
                print(f"   ⚠️ 防火墙可能未启用")

        else:
            print(f"   📋 非Windows系统，跳过防火墙检查")

    except Exception as e:
        print(f"   ❌ 检查防火墙异常: {e}")

def main():
    """主诊断函数"""
    print("🔍 网络连接诊断工具")
    print("目标: 10.1.24.73:1433 (SQL Server)")
    print("=" * 60)

    server_ip = "10.1.24.73"  # 修正IP地址
    port = 1433

    # 1. 基础连通性测试
    print(f"📡 第一步: 基础网络连通性测试")
    ping_ok = ping_server(server_ip, port)

    if not ping_ok:
        print(f"\n❌ 基础连通性测试失败")
        print(f"💡 建议:")
        print(f"   1. 检查IP地址是否正确")
        print(f"   2. 确认服务器可达")
        print(f"   3. 检查网络设备配置")
        return

    print(f"\n✅ 基础连通性测试通过！")

    # 2. SQL Server服务检查
    sql_server_ok = check_sql_server_status()

    # 3. 防火墙检查
    check_firewall()

    # 4. 总结
    print(f"\n" + "=" * 60)
    print(f"📊 诊断结果总结:")
    print(f"   📡 Ping连接: {'✅ 成功' if ping_ok else '❌ 失败'}")
    print(f"   🔌 TCP端口: {'✅ 成功' if ping_ok else '❌ 失败'}")
    print(f"   🗄️ 服务状态: {'✅ 正常' if sql_server_ok else '❌ 需要检查'}")

    if ping_ok:
        print(f"\n✅ 网络连接正常！")
        print(f"💡 如果仍有SQL Server连接问题，请检查:")
        print(f"   1. SQL Server实例是否运行在指定端口")
        print(f"   2. 用户名和密码是否正确")
        print(f"   3. 数据库是否存在")
        print(f"   4. 用户是否有足够权限")
        print(f"   5. 可以尝试使用SQL Server Management Studio直接连接测试")
    else:
        print(f"\n❌ 网络连接存在问题，请先解决连接问题")

if __name__ == "__main__":
    main()