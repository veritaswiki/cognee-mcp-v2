#!/usr/bin/env python3
"""
改进的MCP服务器全面测试脚本
使用持久连接，模拟真实MCP客户端行为
"""

import json
import subprocess
import time
from typing import Dict, Any, List
import signal
import os

class PersistentMCPTester:
    def __init__(self):
        self.process = None
        self.test_results = []
        self.request_id = 1
        self.initialized = False
    
    def start_server(self):
        """启动MCP服务器进程"""
        cmd = ["uv", "run", "python", "main.py"]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并stderr到stdout
            text=True,
            bufsize=1  # 行缓冲
        )
        
        print("🚀 MCP服务器已启动")
        time.sleep(1)  # 等待服务器启动
    
    def stop_server(self):
        """停止MCP服务器"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            print("🛑 MCP服务器已停止")
    
    def send_request(self, method: str, params: Dict = None) -> Dict[str, Any]:
        """发送MCP请求"""
        if not self.process or self.process.poll() is not None:
            return {"error": "服务器未运行"}
        
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        
        try:
            # 发送请求
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # 读取响应
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                if line and (line.startswith('{"jsonrpc"') or line.startswith('{"id"') or '{"jsonrpc"' in line):
                    try:
                        # 尝试解析JSON
                        if line.startswith('{') and '"jsonrpc"' in line:
                            response = json.loads(line)
                            if 'jsonrpc' in response and response.get('id') == request['id']:
                                return response
                    except json.JSONDecodeError:
                        continue
                        
                # 如果是日志行，跳过
                if any(level in line for level in ['[info]', '[warning]', '[error]', '[debug]']):
                    continue
                    
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}
        
        return {"error": "未收到响应"}
    
    def test_initialize(self):
        """测试初始化"""
        print("🔄 测试MCP初始化...")
        params = {
            "protocol_version": "2024-11-05",
            "capabilities": {},
            "client_info": {
                "name": "persistent-warp-tester",
                "version": "1.0.0"
            }
        }
        
        response = self.send_request("initialize", params)
        
        if not response.get("error") and response.get("result"):
            server_info = response["result"].get("server_info", {})
            print("✅ 初始化成功")
            print(f"   服务器: {server_info.get('name')}")
            print(f"   版本: {server_info.get('version')}")
            print(f"   协议版本: {response['result'].get('protocol_version')}")
            
            self.initialized = True
            self.test_results.append(("initialize", "✅", "成功"))
            return True
        else:
            print(f"❌ 初始化失败: {response.get('error')}")
            self.test_results.append(("initialize", "❌", str(response.get('error'))))
            return False
    
    def test_tools_list(self):
        """测试工具列表"""
        if not self.initialized:
            print("⚠️ 跳过工具列表测试 - 未初始化")
            return []
            
        print("🔄 测试工具列表...")
        response = self.send_request("tools/list")
        
        if not response.get("error") and response.get("result"):
            tools = response["result"].get("tools", [])
            print(f"✅ 获取到 {len(tools)} 个工具")
            
            # 按类别统计
            categories = {}
            auth_required = 0
            for tool in tools:
                # 从工具名推断类别
                name = tool.get('name', '')
                if name.startswith('add_') or name in ['cognify', 'search']:
                    cat = 'basic'
                elif name.startswith('graph_'):
                    cat = 'graph'
                elif name.startswith('dataset'):
                    cat = 'dataset'
                elif name.startswith('time_') or 'temporal' in name:
                    cat = 'temporal'
                elif 'ontology' in name or 'concept' in name or 'semantic' in name:
                    cat = 'ontology'
                elif 'memory' in name or 'context' in name:
                    cat = 'memory'
                elif 'performance' in name or 'optimization' in name or 'learning' in name:
                    cat = 'self_improving'
                elif name in ['status', 'health_check', 'error_analysis', 'log_analysis', 'connectivity_test']:
                    cat = 'diagnostic'
                else:
                    cat = 'other'
                
                categories[cat] = categories.get(cat, 0) + 1
            
            print("   工具分类统计:")
            for cat, count in sorted(categories.items()):
                print(f"     - {cat}: {count}个")
            
            self.test_results.append(("tools/list", "✅", f"{len(tools)}个工具"))
            return tools
        else:
            print(f"❌ 获取工具列表失败: {response.get('error')}")
            self.test_results.append(("tools/list", "❌", str(response.get('error'))))
            return []
    
    def test_tool_call(self, tool_name: str, arguments: Dict = None):
        """测试工具调用"""
        if not self.initialized:
            print(f"⚠️ 跳过工具调用测试 {tool_name} - 未初始化")
            return False
            
        print(f"🔄 测试工具调用: {tool_name}")
        params = {
            "name": tool_name,
            "arguments": arguments or {}
        }
        
        response = self.send_request("tools/call", params)
        
        if not response.get("error") and response.get("result"):
            result = response["result"]
            print(f"✅ 工具 {tool_name} 调用成功")
            if 'content' in result:
                content = str(result['content'])
                print(f"   返回内容: {content[:100]}{'...' if len(content) > 100 else ''}\"")
            
            self.test_results.append((f"tools/call:{tool_name}", "✅", "成功"))
            return True
        else:
            error_info = response.get('error', 'Unknown error')
            print(f"❌ 工具 {tool_name} 调用失败: {error_info}")
            self.test_results.append((f"tools/call:{tool_name}", "❌", str(error_info)))
            return False
    
    def test_resources(self):
        """测试资源访问"""
        if not self.initialized:
            print("⚠️ 跳过资源测试 - 未初始化")
            return False
            
        print("🔄 测试资源列表...")
        response = self.send_request("resources/list")
        
        if not response.get("error") and response.get("result"):
            resources = response["result"].get("resources", [])
            print(f"✅ 获取到 {len(resources)} 个资源")
            
            for resource in resources:
                print(f"   - {resource.get('name')}: {resource.get('uri')}")
            
            # 测试读取配置资源
            if resources:
                print("🔄 测试资源读取...")
                config_uri = next((r['uri'] for r in resources if 'config' in r['uri']), None)
                if config_uri:
                    read_response = self.send_request("resources/read", {"uri": config_uri})
                    if not read_response.get("error") and read_response.get("result"):
                        print("✅ 配置资源读取成功")
                        self.test_results.append(("resources/read", "✅", "成功"))
                    else:
                        print(f"❌ 配置资源读取失败: {read_response.get('error')}")
                        self.test_results.append(("resources/read", "❌", str(read_response.get('error'))))
            
            self.test_results.append(("resources/list", "✅", f"{len(resources)}个资源"))
            return True
        else:
            print(f"❌ 获取资源列表失败: {response.get('error')}")
            self.test_results.append(("resources/list", "❌", str(response.get('error'))))
            return False
    
    def test_prompts(self):
        """测试提示功能"""
        if not self.initialized:
            print("⚠️ 跳过提示测试 - 未初始化")
            return False
            
        print("🔄 测试提示列表...")
        response = self.send_request("prompts/list")
        
        if not response.get("error") and response.get("result"):
            prompts = response["result"].get("prompts", [])
            print(f"✅ 获取到 {len(prompts)} 个提示")
            
            for prompt in prompts:
                print(f"   - {prompt.get('name')}: {prompt.get('description')}")
            
            # 测试获取具体提示
            if prompts:
                prompt_name = prompts[0].get('name')
                print(f"🔄 测试提示获取: {prompt_name}")
                get_response = self.send_request("prompts/get", {
                    "name": prompt_name,
                    "arguments": {"dataset_id": "test_dataset"}
                })
                if not get_response.get("error") and get_response.get("result"):
                    print(f"✅ 提示 {prompt_name} 获取成功")
                    self.test_results.append((f"prompts/get:{prompt_name}", "✅", "成功"))
                else:
                    print(f"❌ 提示 {prompt_name} 获取失败: {get_response.get('error')}")
            
            self.test_results.append(("prompts/list", "✅", f"{len(prompts)}个提示"))
            return True
        else:
            print(f"❌ 获取提示列表失败: {response.get('error')}")
            self.test_results.append(("prompts/list", "❌", str(response.get('error'))))
            return False
    
    def run_comprehensive_test(self):
        """运行全面测试"""
        print("=" * 60)
        print("🚀 开始MCP服务器全面测试 (持久连接)")
        print("=" * 60)
        
        try:
            # 启动服务器
            self.start_server()
            
            # 1. 测试初始化
            if not self.test_initialize():
                print("❌ 初始化失败，停止测试")
                return
            
            print()
            
            # 2. 测试工具列表
            tools = self.test_tools_list()
            
            print()
            
            # 3. 测试资源
            self.test_resources()
            
            print()
            
            # 4. 测试提示
            self.test_prompts()
            
            print()
            
            # 5. 测试诊断工具（不需要认证）
            diagnostic_tools = ['status']
            for tool_name in diagnostic_tools:
                if any(t.get('name') == tool_name for t in tools):
                    self.test_tool_call(tool_name)
                    print()
            
            # 6. 测试需要参数但会失败的工具（演示）
            print("🔄 演示需要认证的工具调用（预期失败）...")
            auth_tools = [
                ('add_text', {'text': '测试文本', 'dataset_name': 'test'}),
                ('search', {'query': '测试查询'})
            ]
            
            for tool_name, args in auth_tools:
                if any(t.get('name') == tool_name for t in tools):
                    print(f"   演示调用 {tool_name} (预期认证失败)")
                    self.test_tool_call(tool_name, args)
            
        finally:
            self.stop_server()
        
        # 输出测试报告
        self.print_test_report()
    
    def print_test_report(self):
        """打印测试报告"""
        print("\n" + "=" * 60)
        print("📊 MCP服务器测试报告")
        print("=" * 60)
        
        success_count = sum(1 for _, status, _ in self.test_results if status == "✅")
        total_count = len(self.test_results)
        
        print(f"总测试项: {total_count}")
        print(f"成功: {success_count}")
        print(f"失败: {total_count - success_count}")
        print(f"成功率: {success_count/total_count*100:.1f}%" if total_count > 0 else "0.0%")
        
        print("\n详细结果:")
        for test_name, status, details in self.test_results:
            print(f"{status} {test_name}: {details}")
        
        # 总结
        print("\n" + "=" * 60)
        print("📋 测试总结:")
        
        if success_count == total_count:
            print("🎉 所有测试通过！MCP服务器运行正常")
        elif success_count >= total_count * 0.8:
            print("✨ 大部分测试通过，MCP服务器基本功能正常")
        else:
            print("⚠️ 部分测试失败，需要检查MCP服务器配置")
            
        print("=" * 60)


if __name__ == "__main__":
    tester = PersistentMCPTester()
    try:
        tester.run_comprehensive_test()
    except KeyboardInterrupt:
        print("\n❌ 用户中断测试")
        tester.stop_server()
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        tester.stop_server()
