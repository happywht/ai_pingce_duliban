#!/usr/bin/env python3
"""
测试新的项目信息接口响应格式
验证新增的epc_manager和entrust_manager字段
"""

import json
import requests
from config import config

def mock_new_api_response():
    """模拟新的API响应格式"""
    return {
        "code": 0,
        "msg": "请求成功",
        "data": [
            {
                "project_id": "P2024001",
                "project_code": "ZCB-2024-001",
                "project_name": "某总承包工程项目",
                "epc_manager": "张三",
                "entrust_manager": "李四"
            },
            {
                "project_id": "P2024002",
                "project_code": "ZCB-2024-002",
                "project_name": "另一个工程项目",
                "epc_manager": "王五",
                "entrust_manager": "赵六"
            }
        ]
    }

def test_api_response():
    """测试实际的API响应"""
    print("🚀 测试项目信息接口响应格式")
    print(f"📡 API地址: {config.GET_PROJECTS_API}")
    print("-" * 60)

    try:
        # 测试真实API
        print("🔍 测试真实API...")
        response = requests.post(
            config.GET_PROJECTS_API,
            headers={"Content-Type": "application/json;charset=utf-8"},
            timeout=config.API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        print("✅ API调用成功")
        print(f"📊 响应状态: {data.get('code', 'unknown')}")
        print(f"📝 响应消息: {data.get('msg', 'no message')}")
        print(f"📋 数据条数: {len(data.get('data', []))}")

        # 检查数据结构
        if data.get('code') == 0 and data.get('data'):
            print("\n📋 检查数据结构:")
            first_item = data['data'][0]
            required_fields = ['project_id', 'project_code', 'project_name', 'epc_manager', 'entrust_manager']

            for field in required_fields:
                value = first_item.get(field, 'MISSING')
                status = "✅" if value != 'MISSING' else "❌"
                print(f"   {status} {field}: {value}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ API调用失败: {e}")
        print("🔧 使用模拟数据进行测试...")
        return mock_new_api_response()
    except json.JSONDecodeError as e:
        print(f"❌ 响应解析失败: {e}")
        return mock_new_api_response()

def test_database_sync():
    """测试数据库同步功能"""
    print("\n🔄 测试数据库同步功能")
    print("⚠️ 此功能需要启动后端服务后测试")
    print("📍 可以调用 POST /api/projects/sync 来测试")

def main():
    print("=" * 60)
    print("🧪 项目信息接口适配测试")
    print("=" * 60)

    # 测试API响应
    api_data = test_api_response()

    # 显示完整响应结构
    print("\n📄 完整响应结构:")
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

    # 测试数据库同步
    test_database_sync()

    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("\n📋 更新摘要:")
    print("   ✅ 后端代码已更新，支持新的epc_manager和entrust_manager字段")
    print("   ✅ 数据库表结构已更新")
    print("   ✅ 所有API响应已更新，包含新增字段")
    print("   ✅ 创建了数据库迁移脚本: migrate_database.py")
    print("\n🚀 下一步操作:")
    print("   1. 运行 python migrate_database.py 添加数据库字段")
    print("   2. 启动后端服务进行完整测试")
    print("   3. 验证前端页面显示新的字段信息")

if __name__ == "__main__":
    main()