#!/usr/bin/env python3
"""
逐个测试所有35个MCP工具
老王专用 - 详细测试每个工具的功能、参数、错误处理
"""

import json
import subprocess
import time
import sys
from typing import Dict, Any, List, Tuple
from datetime import datetime
import signal

class IndividualToolTester:
    def __init__(self):
        self.process = None
        self.request_id = 1
        self.initialized = False
        self.tools_info = []
        self.test_results = []
        self.tool_schemas = {}
        
    def start_server(self) -> bool:
        """启动MCP服务器"""
        print("🚀 启动MCP服务器进程...")
        
        cmd = ["uv", "run", "python", "main.py"]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0
        )
        
        time.sleep(2)
        
        if self.process.poll() is None:
            print("✅ MCP服务器启动成功")
            return True
        else:
            print("❌ MCP服务器启动失败")
            return False
    
    def stop_server(self):
        """停止MCP服务器"""
        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except:
                    pass
            print("🛑 MCP服务器已停止")
    
    def send_request(self, method: str, params: Dict = None, timeout: float = 15.0) -> Tuple[Dict, float]:
        """发送MCP请求"""
        if not self.process or self.process.poll() is not None:
            return {"error": "服务器未运行"}, 0.0
        
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        self.request_id += 1
        
        start_time = time.time()
        
        try:
            # 发送请求
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # 读取响应
            response = None
            end_time = start_time + timeout
            
            while time.time() < end_time:
                line = self.process.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                    
                line = line.strip()
                if line and '{"jsonrpc"' in line:
                    try:
                        parsed = json.loads(line)
                        if 'jsonrpc' in parsed and parsed.get('id') == request['id']:
                            response = parsed
                            break
                    except json.JSONDecodeError:
                        continue
                        
                # 跳过日志行
                if any(log_level in line for log_level in ['[info]', '[warning]', '[error]', '[debug]']):
                    continue
            
            elapsed = time.time() - start_time
            
            if response is None:
                return {"error": "请求超时"}, elapsed
                
            return response, elapsed
            
        except Exception as e:
            elapsed = time.time() - start_time
            return {"error": f"请求异常: {str(e)}"}, elapsed
    
    def initialize_server(self) -> bool:
        """初始化MCP服务器"""
        print("\n🔧 初始化MCP服务器...")
        
        params = {
            "protocol_version": "2024-11-05",
            "capabilities": {},
            "client_info": {
                "name": "individual-tool-tester",
                "version": "1.0.0"
            }
        }
        
        response, elapsed = self.send_request("initialize", params)
        
        if not response.get("error") and response.get("result"):
            server_info = response["result"].get("server_info", {})
            print(f"✅ 初始化成功 ({elapsed:.3f}s)")
            print(f"   服务器: {server_info.get('name')}")
            print(f"   版本: {server_info.get('version')}")
            
            self.initialized = True
            return True
        else:
            error = response.get("error", "未知错误")
            print(f"❌ 初始化失败 ({elapsed:.3f}s): {error}")
            return False
    
    def get_all_tools(self) -> List[Dict]:
        """获取所有工具信息"""
        print("\n📋 获取工具列表...")
        
        response, elapsed = self.send_request("tools/list")
        
        if not response.get("error") and response.get("result"):
            tools = response["result"].get("tools", [])
            print(f"✅ 获取到 {len(tools)} 个工具 ({elapsed:.3f}s)")
            
            # 保存工具schema信息
            for tool in tools:
                name = tool.get("name")
                if name:
                    self.tool_schemas[name] = tool.get("inputSchema", {})
            
            self.tools_info = tools
            return tools
        else:
            error = response.get("error", "获取失败")
            print(f"❌ 获取工具列表失败 ({elapsed:.3f}s): {error}")
            return []
    
    def analyze_tool_schema(self, tool_name: str, schema: Dict) -> Dict[str, Any]:
        """分析工具参数schema"""
        analysis = {
            "has_required": False,
            "required_params": [],
            "optional_params": [],
            "param_types": {},
            "has_defaults": False,
            "complexity": "simple"
        }
        
        if not isinstance(schema, dict):
            return analysis
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        analysis["required_params"] = required
        analysis["has_required"] = len(required) > 0
        
        for param, spec in properties.items():
            if param in required:
                continue
            analysis["optional_params"].append(param)
            
            param_type = spec.get("type", "unknown")
            analysis["param_types"][param] = param_type
            
            if "default" in spec:
                analysis["has_defaults"] = True
        
        # 判断复杂度
        total_params = len(properties)
        if total_params == 0:
            analysis["complexity"] = "simple"
        elif total_params <= 2:
            analysis["complexity"] = "simple"
        elif total_params <= 5:
            analysis["complexity"] = "moderate"
        else:
            analysis["complexity"] = "complex"
        
        return analysis
    
    def generate_test_params(self, tool_name: str, schema: Dict) -> List[Dict]:
        """为工具生成测试参数"""
        if not isinstance(schema, dict):
            return [{}]
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        test_cases = []
        
        # 测试用例1: 空参数 (适用于无参数工具)
        if not required:
            test_cases.append({})
        
        # 测试用例2: 最小必要参数
        if required:
            min_params = {}
            for param in required:
                spec = properties.get(param, {})
                param_type = spec.get("type", "string")
                
                # 根据工具名和参数名生成合理的测试值
                if param == "text":
                    min_params[param] = "这是一个测试文本内容"
                elif param == "query":
                    min_params[param] = "测试查询"
                elif param == "dataset_name":
                    min_params[param] = "test_dataset"
                elif param == "dataset_id":
                    min_params[param] = "test_dataset_001"
                elif param == "files":
                    min_params[param] = ["test_file.txt"]
                elif param == "limit":
                    min_params[param] = 5
                elif param == "cypher_query":
                    min_params[param] = "MATCH (n) RETURN n LIMIT 5"
                elif param == "start_time":
                    min_params[param] = "2024-01-01T00:00:00Z"
                elif param == "end_time":
                    min_params[param] = "2024-12-31T23:59:59Z"
                elif param == "ontology_data":
                    min_params[param] = "<?xml version='1.0'?><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'></rdf:RDF>"
                elif param == "memory_key":
                    min_params[param] = "test_memory_key"
                elif param == "feedback_data":
                    min_params[param] = {"rating": 5, "comment": "测试反馈"}
                elif param_type == "string":
                    min_params[param] = f"test_{param}"
                elif param_type == "integer" or param_type == "number":
                    min_params[param] = 10
                elif param_type == "boolean":
                    min_params[param] = True
                elif param_type == "array":
                    min_params[param] = ["test_item"]
                elif param_type == "object":
                    min_params[param] = {"test_key": "test_value"}
                else:
                    min_params[param] = f"test_{param}"
            
            test_cases.append(min_params)
        
        # 测试用例3: 包含可选参数
        if properties and len(properties) > len(required):
            full_params = test_cases[-1].copy() if test_cases else {}
            
            for param, spec in properties.items():
                if param in required:
                    continue
                    
                param_type = spec.get("type", "string")
                default_value = spec.get("default")
                
                if default_value is not None:
                    full_params[param] = default_value
                elif param == "run_in_background":
                    full_params[param] = False
                elif param == "include_metadata":
                    full_params[param] = True
                elif param_type == "boolean":
                    full_params[param] = False
                elif param_type == "integer" or param_type == "number":
                    full_params[param] = 5
                elif param_type == "string":
                    full_params[param] = f"optional_{param}"
            
            if full_params and full_params != (test_cases[-1] if test_cases else {}):
                test_cases.append(full_params)
        
        return test_cases if test_cases else [{}]
    
    def test_single_tool(self, tool_name: str, tool_info: Dict) -> Dict:
        """测试单个工具"""
        print(f"\n{'='*60}")
        print(f"🔧 测试工具: {tool_name}")
        print(f"{'='*60}")
        
        description = tool_info.get("description", "无描述")
        schema = tool_info.get("inputSchema", {})
        
        print(f"📝 描述: {description}")
        
        # 分析schema
        analysis = self.analyze_tool_schema(tool_name, schema)
        print(f"🔍 参数分析:")
        print(f"   必需参数: {analysis['required_params'] if analysis['required_params'] else '无'}")
        print(f"   可选参数: {analysis['optional_params'] if analysis['optional_params'] else '无'}")
        print(f"   复杂度: {analysis['complexity']}")
        
        # 生成测试用例
        test_cases = self.generate_test_params(tool_name, schema)
        print(f"📋 生成 {len(test_cases)} 个测试用例")
        
        results = {
            "tool_name": tool_name,
            "description": description,
            "schema_analysis": analysis,
            "test_cases": [],
            "summary": {
                "total": len(test_cases),
                "success": 0,
                "auth_required": 0,
                "errors": 0
            }
        }
        
        # 执行测试用例
        for i, params in enumerate(test_cases):
            print(f"\n🧪 测试用例 {i+1}/{len(test_cases)}")
            print(f"   参数: {params if params else '无参数'}")
            
            # 发送工具调用请求
            call_params = {
                "name": tool_name,
                "arguments": params
            }
            
            response, elapsed = self.send_request("tools/call", call_params)
            
            test_result = {
                "case_id": i + 1,
                "params": params,
                "elapsed": elapsed,
                "success": False,
                "auth_required": False,
                "error": None,
                "response": None
            }
            
            if not response.get("error") and response.get("result"):
                # 成功
                result = response["result"]
                test_result["success"] = True
                test_result["response"] = result
                results["summary"]["success"] += 1
                
                print(f"   ✅ 成功 ({elapsed:.3f}s)")
                
                # 显示返回内容
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and content:
                        first_content = content[0]
                        if isinstance(first_content, dict) and "text" in first_content:
                            text = first_content["text"][:200]
                            print(f"   📄 返回: {text}{'...' if len(first_content['text']) > 200 else ''}")
                    elif isinstance(content, str):
                        print(f"   📄 返回: {content[:200]}{'...' if len(content) > 200 else ''}")
                    else:
                        print(f"   📄 返回: {str(content)[:200]}")
                        
            else:
                # 失败
                error = response.get("error", {})
                if isinstance(error, dict):
                    error_msg = error.get("message", "未知错误")
                    error_code = error.get("code")
                else:
                    error_msg = str(error)
                    error_code = None
                
                test_result["error"] = {"message": error_msg, "code": error_code}
                
                # 判断是否为认证错误
                if any(auth_keyword in error_msg.lower() for auth_keyword in ["auth", "unauthorized", "credential", "token", "认证", "登录"]):
                    test_result["auth_required"] = True
                    results["summary"]["auth_required"] += 1
                    print(f"   🔐 需要认证 ({elapsed:.3f}s): {error_msg}")
                else:
                    results["summary"]["errors"] += 1
                    print(f"   ❌ 失败 ({elapsed:.3f}s): {error_msg}")
            
            results["test_cases"].append(test_result)
            
            # 短暂延迟避免过于频繁
            time.sleep(0.1)
        
        # 打印工具测试总结
        summary = results["summary"]
        print(f"\n📊 工具 {tool_name} 测试总结:")
        print(f"   总测试: {summary['total']}")
        print(f"   成功: {summary['success']}")
        print(f"   需认证: {summary['auth_required']}")
        print(f"   错误: {summary['errors']}")
        
        self.test_results.append(results)
        return results
    
    def classify_tools_by_category(self, tools: List[Dict]) -> Dict[str, List[str]]:
        """按类别分类工具"""
        categories = {
            "basic": [],
            "graph": [],
            "dataset": [],
            "temporal": [],
            "ontology": [],
            "memory": [],
            "self_improving": [],
            "diagnostic": []
        }
        
        for tool in tools:
            name = tool.get("name", "")
            
            if name.startswith("add_") or name in ["cognify", "search"]:
                categories["basic"].append(name)
            elif name.startswith("graph_"):
                categories["graph"].append(name)
            elif name.startswith("dataset"):
                categories["dataset"].append(name)
            elif any(keyword in name for keyword in ["time_", "temporal", "timeline", "event_"]):
                categories["temporal"].append(name)
            elif any(keyword in name for keyword in ["ontology", "concept", "semantic", "relation_"]):
                categories["ontology"].append(name)
            elif any(keyword in name for keyword in ["memory", "context"]):
                categories["memory"].append(name)
            elif any(keyword in name for keyword in ["performance", "optimization", "learning", "system_"]):
                categories["self_improving"].append(name)
            elif name in ["status", "health_check", "error_analysis", "log_analysis", "connectivity_test"]:
                categories["diagnostic"].append(name)
            else:
                # 其他工具暂时归类到diagnostic
                categories["diagnostic"].append(name)
        
        return categories
    
    def generate_final_report(self):
        """生成最终测试报告"""
        print(f"\n{'='*80}")
        print("📊 所有工具测试完成 - 最终报告")
        print(f"{'='*80}")
        
        total_tools = len(self.test_results)
        total_tests = sum(r["summary"]["total"] for r in self.test_results)
        total_success = sum(r["summary"]["success"] for r in self.test_results)
        total_auth = sum(r["summary"]["auth_required"] for r in self.test_results)
        total_errors = sum(r["summary"]["errors"] for r in self.test_results)
        
        print(f"\n📈 总体统计:")
        print(f"   测试工具数: {total_tools}")
        print(f"   总测试用例: {total_tests}")
        print(f"   成功用例: {total_success} ({total_success/total_tests*100:.1f}%)")
        print(f"   需认证用例: {total_auth} ({total_auth/total_tests*100:.1f}%)")
        print(f"   错误用例: {total_errors} ({total_errors/total_tests*100:.1f}%)")
        
        # 按类别统计
        categories = self.classify_tools_by_category([{"name": r["tool_name"]} for r in self.test_results])
        
        print(f"\n🏷️ 按类别统计:")
        for category, tool_names in categories.items():
            if tool_names:
                category_results = [r for r in self.test_results if r["tool_name"] in tool_names]
                success_count = sum(1 for r in category_results if r["summary"]["success"] > 0)
                auth_count = sum(1 for r in category_results if r["summary"]["auth_required"] > 0)
                
                print(f"   {category:15s}: {len(tool_names):2d}个工具 - {success_count}个可用, {auth_count}个需认证")
        
        # 问题工具
        problem_tools = []
        working_tools = []
        auth_tools = []
        
        for result in self.test_results:
            summary = result["summary"]
            name = result["tool_name"]
            
            if summary["success"] > 0:
                working_tools.append(name)
            elif summary["auth_required"] > 0:
                auth_tools.append(name)
            elif summary["errors"] > 0:
                problem_tools.append(name)
        
        print(f"\n✅ 正常工作的工具 ({len(working_tools)}个):")
        for tool in working_tools:
            print(f"   - {tool}")
        
        print(f"\n🔐 需要认证的工具 ({len(auth_tools)}个):")
        for tool in auth_tools:
            print(f"   - {tool}")
        
        if problem_tools:
            print(f"\n❌ 存在问题的工具 ({len(problem_tools)}个):")
            for tool in problem_tools:
                print(f"   - {tool}")
        
        # 保存详细报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"all_tools_test_report_{timestamp}.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tools": total_tools,
                "total_tests": total_tests,
                "total_success": total_success,
                "total_auth": total_auth,
                "total_errors": total_errors
            },
            "categories": categories,
            "tool_results": self.test_results
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细报告已保存到: {report_file}")
        
        # 最终结论
        print(f"\n🎯 最终结论:")
        if total_success >= total_tests * 0.3:  # 至少30%成功(考虑到大部分需要认证)
            print("✨ MCP服务器工具系统基本正常，大部分工具可以正确响应")
            if total_auth > 0:
                print("💡 建议: 配置认证信息以测试完整功能")
        else:
            print("⚠️ 工具系统存在较多问题，需要进一步调试")
        
        print("="*80)
    
    def run_all_tools_test(self):
        """运行所有工具的完整测试"""
        print("🚀 开始逐个测试所有MCP工具")
        print("老王专用版 - 详细测试每个工具的参数和功能")
        print("="*80)
        
        try:
            # 1. 启动服务器
            if not self.start_server():
                print("❌ 无法启动MCP服务器")
                return
            
            # 2. 初始化
            if not self.initialize_server():
                print("❌ 无法初始化MCP服务器")
                return
            
            # 3. 获取所有工具
            tools = self.get_all_tools()
            if not tools:
                print("❌ 无法获取工具列表")
                return
            
            print(f"\n🎯 准备测试 {len(tools)} 个工具")
            print("注意: 大部分工具需要API认证，预期会有认证失败")
            
            # 4. 逐个测试工具
            for i, tool in enumerate(tools, 1):
                tool_name = tool.get("name")
                print(f"\n📍 进度: {i}/{len(tools)}")
                
                if tool_name:
                    try:
                        self.test_single_tool(tool_name, tool)
                    except KeyboardInterrupt:
                        print(f"\n⚠️ 用户中断，已测试 {i-1}/{len(tools)} 个工具")
                        break
                    except Exception as e:
                        print(f"❌ 测试工具 {tool_name} 时出现异常: {e}")
                        continue
                else:
                    print(f"⚠️ 工具 {i} 缺少名称，跳过")
            
            # 5. 生成最终报告
            self.generate_final_report()
            
        except KeyboardInterrupt:
            print("\n❌ 用户中断测试")
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_server()


if __name__ == "__main__":
    print("老王专用MCP工具逐个测试器")
    print("将测试所有35个工具的功能、参数、错误处理等")
    print("按 Ctrl+C 可随时中断测试\n")
    
    tester = IndividualToolTester()
    tester.run_all_tools_test()
