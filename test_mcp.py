#!/usr/bin/env python3
"""
MCP服务器全面测试脚本
老王专用，测试所有MCP功能和工具
"""

import json
import asyncio
import subprocess
import sys
from typing import Dict, Any, List
import time

class MCPTester:
    def __init__(self):
        self.process = None
        self.test_results = []
        self.request_id = 1
    
    def send_mcp_request(self, method: str, params: Dict = None) -> Dict[str, Any]:
        """发送MCP请求并获取响应"""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        
        # 启动MCP服务器进程
        cmd = ["uv", "run", "python", "main.py"]
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 发送请求
        request_json = json.dumps(request) + "\n"
        stdout, stderr = process.communicate(input=request_json, timeout=10)
        
        try:
            # 解析响应 - 查找JSON响应行
            for line in stdout.split('\n'):
                line = line.strip()
                if line and (line.startswith('{"jsonrpc"') or line.startswith('{"jsonrpc')):
                    try:
                        response = json.loads(line)
                        if 'jsonrpc' in response:
                            return response
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"解析响应失败: {e}")
            print(f"stdout前500字符: {stdout[:500]}")
            print(f"stderr: {stderr}")
            return {"error": str(e)}
        
        return {"error": "No valid response"}
    
    def test_initialize(self):
        """测试初始化"""
        print("🔄 测试MCP初始化...")
        params = {
            "protocol_version": "2024-11-05",
            "capabilities": {},
            "client_info": {
                "name": "warp-tester",
                "version": "1.0.0"
            }
        }
        
        response = self.send_mcp_request("initialize", params)
        print(f"调试: 收到响应: {response}")
        
        if not response.get("error") and response.get("result"):
            print("✅ 初始化成功")
            print(f"   服务器: {response.get('result', {}).get('server_info', {}).get('name')}")
            print(f"   版本: {response.get('result', {}).get('server_info', {}).get('version')}")
            self.test_results.append(("initialize", "✅", "成功"))
            return True
        else:
            print(f"❌ 初始化失败: {response.get('error')}")
            self.test_results.append(("initialize", "❌", response.get('error')))
            return False
    
    def test_tools_list(self):
        """测试工具列表"""
        print("🔄 测试工具列表...")
        response = self.send_mcp_request("tools/list")
        
        if not response.get("error"):
            tools = response.get('result', {}).get('tools', [])
            print(f"✅ 获取到 {len(tools)} 个工具")
            
            # 按类别统计
            categories = {}
            for tool in tools:
                cat = tool.get('description', '').split()[0] if tool.get('description') else 'unknown'
                categories[cat] = categories.get(cat, 0) + 1
            
            print("   工具分类统计:")
            for cat, count in categories.items():
                print(f"     - {cat}: {count}个")
                
            self.test_results.append(("tools/list", "✅", f"{len(tools)}个工具"))
            return tools
        else:
            print(f"❌ 获取工具列表失败: {response.get('error')}")
            self.test_results.append(("tools/list", "❌", response.get('error')))
            return []
    
    def test_tool_call(self, tool_name: str, arguments: Dict = None):
        """测试单个工具调用"""
        print(f"🔄 测试工具调用: {tool_name}")
        params = {
            "name": tool_name,
            "arguments": arguments or {}
        }
        
        response = self.send_mcp_request("tools/call", params)
        
        if not response.get("error"):
            result = response.get('result', {})
            print(f"✅ 工具 {tool_name} 调用成功")
            if 'content' in result:
                print(f"   返回: {str(result['content'])[:100]}...")
            self.test_results.append((f"tools/call:{tool_name}", "✅", "成功"))
            return True
        else:
            print(f"❌ 工具 {tool_name} 调用失败: {response.get('error')}")
            self.test_results.append((f"tools/call:{tool_name}", "❌", response.get('error')))
            return False
    
    def test_resources(self):
        """测试资源访问"""
        print("🔄 测试资源列表...")
        response = self.send_mcp_request("resources/list")
        
        if not response.get("error"):
            resources = response.get('result', {}).get('resources', [])
            print(f"✅ 获取到 {len(resources)} 个资源")
            
            for resource in resources:
                print(f"   - {resource.get('name')}: {resource.get('uri')}")
            
            # 测试读取配置资源
            if resources:
                print("🔄 测试配置资源读取...")
                config_uri = next((r['uri'] for r in resources if 'config' in r['uri']), None)
                if config_uri:
                    read_response = self.send_mcp_request("resources/read", {"uri": config_uri})
                    if "error" not in read_response:
                        print("✅ 配置资源读取成功")
                        self.test_results.append(("resources/read", "✅", "成功"))
                    else:
                        print(f"❌ 配置资源读取失败: {read_response.get('error')}")
            
            self.test_results.append(("resources/list", "✅", f"{len(resources)}个资源"))
            return True
        else:
            print(f"❌ 获取资源列表失败: {response.get('error')}")
            self.test_results.append(("resources/list", "❌", response.get('error')))
            return False
    
    def test_prompts(self):
        """测试提示列表"""
        print("🔄 测试提示列表...")
        response = self.send_mcp_request("prompts/list")
        
        if not response.get("error"):
            prompts = response.get('result', {}).get('prompts', [])
            print(f"✅ 获取到 {len(prompts)} 个提示")
            
            for prompt in prompts:
                print(f"   - {prompt.get('name')}: {prompt.get('description')}")
            
            self.test_results.append(("prompts/list", "✅", f"{len(prompts)}个提示"))
            return True
        else:
            print(f"❌ 获取提示列表失败: {response.get('error')}")
            self.test_results.append(("prompts/list", "❌", response.get('error')))
            return False
    
    def run_comprehensive_test(self):
        """运行全面测试"""
        print("=" * 60)
        print("🚀 开始MCP服务器全面测试")
        print("=" * 60)
        
        # 1. 测试初始化
        if not self.test_initialize():
            print("❌ 初始化失败，停止测试")
            return
        
        # 2. 测试工具列表
        tools = self.test_tools_list()
        
        # 3. 测试资源
        self.test_resources()
        
        # 4. 测试提示
        self.test_prompts()
        
        # 5. 测试关键工具调用（不需要认证的）
        safe_tools = ['status', 'health_check']  # 诊断工具通常不需要认证
        for tool_name in safe_tools:
            if any(t.get('name') == tool_name for t in tools):
                self.test_tool_call(tool_name)
        
        # 6. 测试需要参数的工具（模拟调用）
        print("🔄 测试需要参数的工具...")
        parameter_tools = [
            ('add_text', {'text': '测试文本', 'dataset_name': 'test_dataset'}),
            ('search', {'query': '测试查询', 'limit': 5})
        ]
        
        for tool_name, args in parameter_tools:
            if any(t.get('name') == tool_name for t in tools):
                print(f"   模拟测试 {tool_name} (需要认证，跳过实际调用)")
        
        # 7. 输出测试报告
        self.print_test_report()
    
    def print_test_report(self):
        """打印测试报告"""
        print("\n" + "=" * 60)
        print("📊 测试报告")
        print("=" * 60)
        
        success_count = sum(1 for _, status, _ in self.test_results if status == "✅")
        total_count = len(self.test_results)
        
        print(f"总测试项: {total_count}")
        print(f"成功: {success_count}")
        print(f"失败: {total_count - success_count}")
        print(f"成功率: {success_count/total_count*100:.1f}%")
        
        print("\n详细结果:")
        for test_name, status, details in self.test_results:
            print(f"{status} {test_name}: {details}")
        
        print("\n" + "=" * 60)


if __name__ == "__main__":
    tester = MCPTester()
    try:
        tester.run_comprehensive_test()
    except KeyboardInterrupt:
        print("\n❌ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
