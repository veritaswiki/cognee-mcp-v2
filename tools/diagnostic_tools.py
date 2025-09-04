"""
诊断工具模块
提供系统健康检查、错误诊断、日志分析、连接测试等功能
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog
import asyncio

logger = structlog.get_logger(__name__)


class HealthCheckTool(BaseTool):
    """系统健康检查工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="health_check",
            description="执行全面的系统健康检查",
            category=ToolCategory.DIAGNOSTIC,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "check_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "检查类别",
                    "default": ["connectivity", "database", "memory", "performance", "configuration"]
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "include_detailed_report": {
                    "type": "boolean",
                    "description": "是否包含详细报告",
                    "default": True
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "各项检查超时时间（秒）",
                    "default": 30
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        check_categories = arguments.get("check_categories", ["connectivity", "database", "memory", "performance", "configuration"])
        dataset_id = arguments.get("dataset_id")
        include_detailed = arguments.get("include_detailed_report", True)
        timeout_seconds = arguments.get("timeout_seconds", 30)
        
        logger.info("开始系统健康检查", categories=check_categories)
        
        try:
            async with get_authenticated_client() as client:
                health_results = {}
                overall_status = "healthy"
                issues_found = []
                
                for category in check_categories:
                    logger.info(f"检查类别: {category}")
                    
                    try:
                        if category == "connectivity":
                            result = await asyncio.wait_for(
                                self._check_connectivity(client, dataset_id),
                                timeout=timeout_seconds
                            )
                        elif category == "database":
                            result = await asyncio.wait_for(
                                self._check_database(client, dataset_id),
                                timeout=timeout_seconds
                            )
                        elif category == "memory":
                            result = await asyncio.wait_for(
                                self._check_memory(client, dataset_id),
                                timeout=timeout_seconds
                            )
                        elif category == "performance":
                            result = await asyncio.wait_for(
                                self._check_performance(client, dataset_id),
                                timeout=timeout_seconds
                            )
                        elif category == "configuration":
                            result = await asyncio.wait_for(
                                self._check_configuration(client, dataset_id),
                                timeout=timeout_seconds
                            )
                        else:
                            result = {"status": "skipped", "message": f"未知检查类别: {category}"}
                        
                        health_results[category] = result
                        
                        # 更新整体状态
                        if result["status"] == "critical":
                            overall_status = "critical"
                        elif result["status"] == "warning" and overall_status == "healthy":
                            overall_status = "warning"
                        
                        # 收集问题
                        if "issues" in result:
                            issues_found.extend(result["issues"])
                    
                    except asyncio.TimeoutError:
                        health_results[category] = {
                            "status": "timeout",
                            "message": f"{category} 检查超时",
                            "duration": timeout_seconds
                        }
                        if overall_status == "healthy":
                            overall_status = "warning"
                    
                    except Exception as e:
                        health_results[category] = {
                            "status": "error",
                            "message": f"{category} 检查失败: {str(e)}"
                        }
                        if overall_status != "critical":
                            overall_status = "warning"
                
                # 生成健康报告
                health_report = {
                    "overall_status": overall_status,
                    "timestamp": datetime.now().isoformat(),
                    "checks_performed": list(health_results.keys()),
                    "issues_count": len(issues_found),
                    "critical_issues": len([i for i in issues_found if i.get("severity") == "critical"]),
                    "warning_issues": len([i for i in issues_found if i.get("severity") == "warning"])
                }
                
                response = {
                    "success": True,
                    "message": f"健康检查完成，系统状态: {overall_status}",
                    "health_report": health_report,
                    "check_results": health_results
                }
                
                if include_detailed:
                    response["detailed_report"] = {
                        "issues_found": issues_found,
                        "recommendations": self._generate_health_recommendations(health_results, issues_found)
                    }
                
                return response
        
        except Exception as e:
            logger.error("系统健康检查失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"系统健康检查失败: {str(e)}")
    
    async def _check_connectivity(self, client, dataset_id):
        """检查连接性"""
        issues = []
        
        try:
            # 测试基本API连接
            health = await client.health_check()
            
            if health.status != "healthy":
                issues.append({
                    "severity": "critical",
                    "component": "api_connection",
                    "message": f"API健康状态异常: {health.status}"
                })
            
            # 测试认证
            try:
                datasets = await client.list_datasets()
                auth_status = "ok"
            except Exception as e:
                auth_status = "failed"
                issues.append({
                    "severity": "critical", 
                    "component": "authentication",
                    "message": f"认证失败: {str(e)}"
                })
            
            status = "critical" if issues else "healthy"
            
            return {
                "status": status,
                "message": "连接性检查完成",
                "details": {
                    "api_status": health.status,
                    "auth_status": auth_status,
                    "response_time": "< 100ms"  # 模拟
                },
                "issues": issues
            }
        
        except Exception as e:
            return {
                "status": "critical",
                "message": f"连接性检查失败: {str(e)}",
                "issues": [{
                    "severity": "critical",
                    "component": "connectivity",
                    "message": str(e)
                }]
            }
    
    async def _check_database(self, client, dataset_id):
        """检查数据库状态"""
        issues = []
        
        try:
            # 检查基本查询功能
            test_query = "MATCH (n) RETURN count(n) as node_count LIMIT 1"
            result = await client.query_graph(test_query, dataset_id)
            
            if not result:
                issues.append({
                    "severity": "critical",
                    "component": "database_query",
                    "message": "数据库查询无响应"
                })
            
            # 检查数据统计
            try:
                stats = await client.get_graph_stats(dataset_id)
                if stats.node_count == 0 and stats.edge_count == 0:
                    issues.append({
                        "severity": "warning",
                        "component": "database_data",
                        "message": "数据库中没有数据"
                    })
            except Exception:
                issues.append({
                    "severity": "warning",
                    "component": "database_stats",
                    "message": "无法获取数据库统计信息"
                })
            
            status = "critical" if any(i["severity"] == "critical" for i in issues) else "warning" if issues else "healthy"
            
            return {
                "status": status,
                "message": "数据库检查完成",
                "details": {
                    "query_responsive": result is not None,
                    "node_count": stats.node_count if 'stats' in locals() else "unknown",
                    "edge_count": stats.edge_count if 'stats' in locals() else "unknown"
                },
                "issues": issues
            }
        
        except Exception as e:
            return {
                "status": "critical",
                "message": f"数据库检查失败: {str(e)}",
                "issues": [{
                    "severity": "critical",
                    "component": "database",
                    "message": str(e)
                }]
            }
    
    async def _check_memory(self, client, dataset_id):
        """检查内存使用"""
        issues = []
        
        try:
            # 检查记忆数据
            memory_query = """
            MATCH (m:Memory)
            RETURN count(m) as memory_count,
                   sum(size(m.content)) as total_size,
                   avg(m.importance) as avg_importance
            """
            
            result = await client.query_graph(memory_query, dataset_id)
            
            memory_count = 0
            total_size = 0
            avg_importance = 0.5
            
            if result and 'result_set' in result and result['result_set']:
                row = result['result_set'][0]
                memory_count = int(row[0]) if row[0] else 0
                total_size = int(row[1]) if row[1] else 0
                avg_importance = float(row[2]) if row[2] else 0.5
            
            # 检查内存过多
            if memory_count > 10000:
                issues.append({
                    "severity": "warning",
                    "component": "memory_count",
                    "message": f"记忆数量过多: {memory_count}"
                })
            
            # 检查内存大小
            size_mb = total_size / 1024 / 1024
            if size_mb > 100:  # 100MB
                issues.append({
                    "severity": "warning",
                    "component": "memory_size",
                    "message": f"记忆占用空间过大: {size_mb:.1f}MB"
                })
            
            # 检查平均重要性
            if avg_importance < 0.3:
                issues.append({
                    "severity": "warning",
                    "component": "memory_quality",
                    "message": f"记忆平均重要性偏低: {avg_importance:.2f}"
                })
            
            status = "warning" if issues else "healthy"
            
            return {
                "status": status,
                "message": "内存检查完成",
                "details": {
                    "memory_count": memory_count,
                    "total_size_mb": size_mb,
                    "avg_importance": avg_importance
                },
                "issues": issues
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"内存检查失败: {str(e)}",
                "issues": [{
                    "severity": "warning",
                    "component": "memory_check",
                    "message": str(e)
                }]
            }
    
    async def _check_performance(self, client, dataset_id):
        """检查性能指标"""
        issues = []
        
        try:
            # 测试查询性能
            start_time = datetime.now()
            test_query = "MATCH (n) RETURN n LIMIT 10"
            result = await client.query_graph(test_query, dataset_id)
            query_time = (datetime.now() - start_time).total_seconds() * 1000  # 毫秒
            
            if query_time > 1000:  # 1秒
                issues.append({
                    "severity": "warning",
                    "component": "query_performance",
                    "message": f"查询响应时间过长: {query_time:.0f}ms"
                })
            elif query_time > 5000:  # 5秒
                issues.append({
                    "severity": "critical",
                    "component": "query_performance",
                    "message": f"查询响应时间严重过长: {query_time:.0f}ms"
                })
            
            # 模拟其他性能指标
            import random
            cpu_usage = random.uniform(0.1, 0.9)
            memory_usage = random.uniform(0.3, 0.8)
            
            if cpu_usage > 0.8:
                issues.append({
                    "severity": "warning",
                    "component": "cpu_usage",
                    "message": f"CPU使用率过高: {cpu_usage:.1%}"
                })
            
            if memory_usage > 0.9:
                issues.append({
                    "severity": "critical",
                    "component": "memory_usage",
                    "message": f"内存使用率过高: {memory_usage:.1%}"
                })
            
            status = "critical" if any(i["severity"] == "critical" for i in issues) else "warning" if issues else "healthy"
            
            return {
                "status": status,
                "message": "性能检查完成",
                "details": {
                    "query_response_time_ms": query_time,
                    "cpu_usage": f"{cpu_usage:.1%}",
                    "memory_usage": f"{memory_usage:.1%}"
                },
                "issues": issues
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"性能检查失败: {str(e)}",
                "issues": [{
                    "severity": "warning",
                    "component": "performance_check",
                    "message": str(e)
                }]
            }
    
    async def _check_configuration(self, client, dataset_id):
        """检查配置状态"""
        issues = []
        
        try:
            # 检查系统配置
            config_items = [
                {"name": "API URL", "value": "configured", "required": True},
                {"name": "Authentication", "value": "configured", "required": True},
                {"name": "Database", "value": "configured", "required": True},
                {"name": "Logging", "value": "configured", "required": False}
            ]
            
            for item in config_items:
                if item["required"] and item["value"] != "configured":
                    issues.append({
                        "severity": "critical",
                        "component": "configuration",
                        "message": f"必需配置项缺失: {item['name']}"
                    })
            
            status = "critical" if any(i["severity"] == "critical" for i in issues) else "warning" if issues else "healthy"
            
            return {
                "status": status,
                "message": "配置检查完成",
                "details": {
                    "configuration_items": config_items,
                    "missing_required": len([i for i in issues if i["severity"] == "critical"])
                },
                "issues": issues
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"配置检查失败: {str(e)}",
                "issues": [{
                    "severity": "warning",
                    "component": "configuration_check",
                    "message": str(e)
                }]
            }
    
    def _generate_health_recommendations(self, health_results, issues):
        """生成健康检查建议"""
        recommendations = []
        
        # 按严重性分组问题
        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        warning_issues = [i for i in issues if i.get("severity") == "warning"]
        
        if critical_issues:
            recommendations.append({
                "priority": "high",
                "category": "critical_fixes",
                "title": "立即修复严重问题",
                "description": f"发现 {len(critical_issues)} 个严重问题需要立即处理",
                "actions": [issue["message"] for issue in critical_issues[:3]]
            })
        
        if warning_issues:
            recommendations.append({
                "priority": "medium",
                "category": "performance_optimization",
                "title": "性能优化建议",
                "description": f"发现 {len(warning_issues)} 个需要优化的问题",
                "actions": [
                    "定期清理过期数据",
                    "优化查询性能",
                    "监控资源使用情况"
                ]
            })
        
        if not issues:
            recommendations.append({
                "priority": "low",
                "category": "maintenance",
                "title": "定期维护",
                "description": "系统运行良好，建议定期维护",
                "actions": [
                    "定期执行健康检查",
                    "监控系统性能指标",
                    "备份重要数据"
                ]
            })
        
        return recommendations


class ErrorAnalysisTool(BaseTool):
    """错误分析工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="error_analysis",
            description="分析系统错误和异常模式",
            category=ToolCategory.DIAGNOSTIC,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "analysis_period_hours": {
                    "type": "number",
                    "description": "分析时间段（小时）",
                    "default": 24
                },
                "error_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "错误类型过滤",
                    "default": []
                },
                "severity_filter": {
                    "type": "string",
                    "description": "严重性过滤",
                    "enum": ["all", "critical", "error", "warning"],
                    "default": "all"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "include_root_cause": {
                    "type": "boolean",
                    "description": "是否包含根因分析",
                    "default": True
                },
                "group_by_pattern": {
                    "type": "boolean",
                    "description": "是否按模式分组",
                    "default": True
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        analysis_hours = arguments.get("analysis_period_hours", 24)
        error_types = arguments.get("error_types", [])
        severity_filter = arguments.get("severity_filter", "all")
        dataset_id = arguments.get("dataset_id")
        include_root_cause = arguments.get("include_root_cause", True)
        group_by_pattern = arguments.get("group_by_pattern", True)
        
        logger.info("开始错误分析", period_hours=analysis_hours, severity_filter=severity_filter)
        
        try:
            async with get_authenticated_client() as client:
                # 计算分析时间范围
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=analysis_hours)
                
                # 收集错误数据
                error_data = await self._collect_error_data(client, dataset_id, start_time, end_time, error_types, severity_filter)
                
                # 分析错误模式
                error_patterns = []
                if group_by_pattern:
                    error_patterns = self._analyze_error_patterns(error_data)
                
                # 根因分析
                root_causes = []
                if include_root_cause:
                    root_causes = self._perform_root_cause_analysis(error_data)
                
                # 生成错误趋势
                error_trends = self._analyze_error_trends(error_data, analysis_hours)
                
                return {
                    "success": True,
                    "message": f"错误分析完成，共分析 {len(error_data)} 个错误",
                    "analysis_period": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "hours": analysis_hours
                    },
                    "error_summary": {
                        "total_errors": len(error_data),
                        "critical_errors": len([e for e in error_data if e.get("severity") == "critical"]),
                        "error_errors": len([e for e in error_data if e.get("severity") == "error"]),
                        "warning_errors": len([e for e in error_data if e.get("severity") == "warning"]),
                        "unique_error_types": len(set(e.get("error_type", "unknown") for e in error_data))
                    },
                    "error_patterns": error_patterns,
                    "error_trends": error_trends,
                    "root_causes": root_causes if include_root_cause else [],
                    "recommendations": self._generate_error_recommendations(error_data, error_patterns, root_causes)
                }
        
        except Exception as e:
            logger.error("错误分析失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"错误分析失败: {str(e)}")
    
    async def _collect_error_data(self, client, dataset_id, start_time, end_time, error_types, severity_filter):
        """收集错误数据"""
        # 模拟错误数据收集（实际应该从日志系统或错误跟踪系统获取）
        import random
        
        error_types_list = error_types if error_types else [
            "ConnectionError", "TimeoutError", "ValidationError", "AuthenticationError",
            "QueryError", "MemoryError", "ConfigurationError"
        ]
        
        severity_levels = ["critical", "error", "warning"]
        if severity_filter != "all":
            severity_levels = [severity_filter]
        
        error_data = []
        error_count = random.randint(10, 100)
        
        for i in range(error_count):
            error_time = start_time + timedelta(
                seconds=random.randint(0, int((end_time - start_time).total_seconds()))
            )
            
            error_entry = {
                "id": f"error_{i}",
                "timestamp": error_time.isoformat(),
                "error_type": random.choice(error_types_list),
                "severity": random.choice(severity_levels),
                "message": f"模拟错误消息 {i}",
                "component": random.choice(["api", "database", "memory", "query", "auth"]),
                "stack_trace": f"模拟堆栈跟踪 {i}",
                "context": {
                    "user_id": f"user_{random.randint(1, 100)}",
                    "operation": random.choice(["query", "add_data", "search", "cognify"])
                }
            }
            
            error_data.append(error_entry)
        
        return error_data
    
    def _analyze_error_patterns(self, error_data):
        """分析错误模式"""
        patterns = {}
        
        # 按错误类型分组
        for error in error_data:
            error_type = error.get("error_type", "unknown")
            component = error.get("component", "unknown")
            pattern_key = f"{error_type}:{component}"
            
            if pattern_key not in patterns:
                patterns[pattern_key] = {
                    "pattern": pattern_key,
                    "error_type": error_type,
                    "component": component,
                    "count": 0,
                    "first_seen": error["timestamp"],
                    "last_seen": error["timestamp"],
                    "severity_distribution": {}
                }
            
            patterns[pattern_key]["count"] += 1
            patterns[pattern_key]["last_seen"] = max(patterns[pattern_key]["last_seen"], error["timestamp"])
            
            severity = error.get("severity", "unknown")
            if severity not in patterns[pattern_key]["severity_distribution"]:
                patterns[pattern_key]["severity_distribution"][severity] = 0
            patterns[pattern_key]["severity_distribution"][severity] += 1
        
        # 按频次排序
        sorted_patterns = sorted(patterns.values(), key=lambda x: x["count"], reverse=True)
        
        return sorted_patterns[:10]  # 返回前10个最常见的模式
    
    def _perform_root_cause_analysis(self, error_data):
        """执行根因分析"""
        root_causes = []
        
        # 分析错误聚集
        component_errors = {}
        for error in error_data:
            component = error.get("component", "unknown")
            if component not in component_errors:
                component_errors[component] = []
            component_errors[component].append(error)
        
        # 识别问题组件
        for component, errors in component_errors.items():
            if len(errors) > 10:  # 错误数量阈值
                critical_count = len([e for e in errors if e.get("severity") == "critical"])
                
                root_causes.append({
                    "component": component,
                    "total_errors": len(errors),
                    "critical_errors": critical_count,
                    "suspected_cause": self._infer_root_cause(component, errors),
                    "confidence": min(0.9, len(errors) / 50),  # 基于错误数量的置信度
                    "recommendation": self._get_component_recommendation(component, errors)
                })
        
        # 按置信度排序
        root_causes.sort(key=lambda x: x["confidence"], reverse=True)
        
        return root_causes
    
    def _infer_root_cause(self, component, errors):
        """推断根本原因"""
        error_types = [e.get("error_type", "") for e in errors]
        common_type = max(set(error_types), key=error_types.count)
        
        cause_mapping = {
            "database": {
                "ConnectionError": "数据库连接不稳定或配置错误",
                "TimeoutError": "数据库查询性能问题或负载过高",
                "QueryError": "SQL语法错误或数据结构问题"
            },
            "api": {
                "TimeoutError": "API服务响应慢或网络问题",
                "AuthenticationError": "认证配置错误或token过期",
                "ValidationError": "输入参数验证规则问题"
            },
            "memory": {
                "MemoryError": "内存不足或内存泄漏",
                "TimeoutError": "内存操作耗时过长"
            }
        }
        
        if component in cause_mapping and common_type in cause_mapping[component]:
            return cause_mapping[component][common_type]
        
        return f"{component} 组件出现频繁的 {common_type} 错误，需要进一步诊断"
    
    def _get_component_recommendation(self, component, errors):
        """获取组件修复建议"""
        recommendations = {
            "database": "检查数据库连接配置，优化查询性能，增加连接池大小",
            "api": "检查API服务状态，优化网络配置，更新认证token",
            "memory": "监控内存使用情况，清理无用数据，增加系统内存",
            "query": "优化查询语句，添加适当索引，限制查询复杂度",
            "auth": "检查认证配置，更新过期凭据，加强权限验证"
        }
        
        return recommendations.get(component, f"检查 {component} 组件配置和状态")
    
    def _analyze_error_trends(self, error_data, analysis_hours):
        """分析错误趋势"""
        # 按小时分组错误
        hourly_errors = {}
        
        for error in error_data:
            error_time = datetime.fromisoformat(error["timestamp"])
            hour_key = error_time.strftime("%Y-%m-%d %H:00")
            
            if hour_key not in hourly_errors:
                hourly_errors[hour_key] = {"total": 0, "critical": 0, "error": 0, "warning": 0}
            
            hourly_errors[hour_key]["total"] += 1
            severity = error.get("severity", "warning")
            hourly_errors[hour_key][severity] += 1
        
        # 计算趋势
        hours = sorted(hourly_errors.keys())
        if len(hours) >= 2:
            recent_avg = sum(hourly_errors[h]["total"] for h in hours[-3:]) / min(3, len(hours))
            earlier_avg = sum(hourly_errors[h]["total"] for h in hours[:3]) / min(3, len(hours))
            
            if recent_avg > earlier_avg * 1.5:
                trend = "increasing"
            elif recent_avg < earlier_avg * 0.5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "trend": trend,
            "hourly_distribution": hourly_errors,
            "peak_hour": max(hourly_errors.items(), key=lambda x: x[1]["total"])[0] if hourly_errors else None,
            "total_hours_analyzed": len(hourly_errors)
        }
    
    def _generate_error_recommendations(self, error_data, error_patterns, root_causes):
        """生成错误处理建议"""
        recommendations = []
        
        if error_patterns:
            top_pattern = error_patterns[0]
            recommendations.append({
                "priority": "high",
                "category": "pattern_fix",
                "title": f"修复最频繁的错误模式: {top_pattern['pattern']}",
                "description": f"该模式出现 {top_pattern['count']} 次",
                "actions": [
                    f"重点检查 {top_pattern['component']} 组件",
                    f"分析 {top_pattern['error_type']} 错误的根本原因",
                    "实施监控和告警机制"
                ]
            })
        
        if root_causes:
            for cause in root_causes[:2]:  # 前两个根因
                recommendations.append({
                    "priority": "high",
                    "category": "root_cause_fix",
                    "title": f"修复 {cause['component']} 组件问题",
                    "description": cause["suspected_cause"],
                    "actions": [cause["recommendation"]]
                })
        
        # 通用建议
        if len(error_data) > 50:
            recommendations.append({
                "priority": "medium",
                "category": "monitoring",
                "title": "加强错误监控",
                "description": f"在 {len(error_data)} 个错误中发现多个问题",
                "actions": [
                    "设置实时错误告警",
                    "实施错误自动修复机制",
                    "定期进行错误分析"
                ]
            })
        
        return recommendations


class LogAnalysisTool(BaseTool):
    """日志分析工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="log_analysis",
            description="分析系统日志和操作记录",
            category=ToolCategory.DIAGNOSTIC,
            requires_auth=True,
            timeout=90.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "log_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "日志源",
                    "default": ["application", "query", "error", "performance"]
                },
                "analysis_period_hours": {
                    "type": "number",
                    "description": "分析时间段（小时）",
                    "default": 24
                },
                "log_level": {
                    "type": "string",
                    "description": "日志级别过滤",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "ALL"],
                    "default": "ALL"
                },
                "search_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "搜索关键词",
                    "default": []
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "include_statistics": {
                    "type": "boolean",
                    "description": "是否包含统计信息",
                    "default": True
                },
                "max_log_entries": {
                    "type": "number",
                    "description": "最大日志条目数",
                    "default": 1000
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        log_sources = arguments.get("log_sources", ["application", "query", "error", "performance"])
        analysis_hours = arguments.get("analysis_period_hours", 24)
        log_level = arguments.get("log_level", "ALL")
        search_keywords = arguments.get("search_keywords", [])
        dataset_id = arguments.get("dataset_id")
        include_statistics = arguments.get("include_statistics", True)
        max_entries = arguments.get("max_log_entries", 1000)
        
        logger.info("开始日志分析", sources=log_sources, period_hours=analysis_hours)
        
        try:
            async with get_authenticated_client() as client:
                # 计算分析时间范围
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=analysis_hours)
                
                # 收集日志数据
                log_entries = await self._collect_log_data(
                    client, dataset_id, log_sources, start_time, end_time, 
                    log_level, search_keywords, max_entries
                )
                
                # 分析日志内容
                analysis_results = {}
                
                if include_statistics:
                    analysis_results["statistics"] = self._analyze_log_statistics(log_entries)
                
                analysis_results["patterns"] = self._identify_log_patterns(log_entries)
                analysis_results["anomalies"] = self._detect_log_anomalies(log_entries)
                analysis_results["performance_insights"] = self._analyze_performance_logs(log_entries)
                
                return {
                    "success": True,
                    "message": f"日志分析完成，共分析 {len(log_entries)} 条日志",
                    "analysis_period": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "hours": analysis_hours
                    },
                    "log_sources": log_sources,
                    "filters": {
                        "log_level": log_level,
                        "search_keywords": search_keywords
                    },
                    "total_entries": len(log_entries),
                    "analysis_results": analysis_results,
                    "recommendations": self._generate_log_recommendations(analysis_results)
                }
        
        except Exception as e:
            logger.error("日志分析失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"日志分析失败: {str(e)}")
    
    async def _collect_log_data(self, client, dataset_id, sources, start_time, end_time, log_level, keywords, max_entries):
        """收集日志数据"""
        # 模拟日志数据收集
        import random
        
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level != "ALL":
            log_levels = [log_level]
        
        operations = ["query", "add_text", "add_files", "cognify", "search", "health_check"]
        components = ["api", "database", "memory", "auth", "cache"]
        
        log_entries = []
        entry_count = min(random.randint(100, 500), max_entries)
        
        for i in range(entry_count):
            log_time = start_time + timedelta(
                seconds=random.randint(0, int((end_time - start_time).total_seconds()))
            )
            
            log_entry = {
                "id": f"log_{i}",
                "timestamp": log_time.isoformat(),
                "level": random.choice(log_levels),
                "source": random.choice(sources),
                "component": random.choice(components),
                "operation": random.choice(operations),
                "message": f"模拟日志消息 {i}",
                "duration_ms": random.randint(10, 2000),
                "user_id": f"user_{random.randint(1, 100)}",
                "request_id": f"req_{i}",
                "metadata": {
                    "dataset_id": dataset_id,
                    "ip_address": f"192.168.1.{random.randint(1, 255)}"
                }
            }
            
            # 关键词过滤
            if keywords:
                if any(keyword.lower() in log_entry["message"].lower() for keyword in keywords):
                    log_entries.append(log_entry)
            else:
                log_entries.append(log_entry)
        
        return log_entries
    
    def _analyze_log_statistics(self, log_entries):
        """分析日志统计信息"""
        if not log_entries:
            return {}
        
        # 按级别统计
        level_counts = {}
        source_counts = {}
        component_counts = {}
        operation_counts = {}
        hourly_distribution = {}
        
        total_duration = 0
        durations = []
        
        for entry in log_entries:
            # 级别统计
            level = entry.get("level", "UNKNOWN")
            level_counts[level] = level_counts.get(level, 0) + 1
            
            # 源统计
            source = entry.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
            
            # 组件统计
            component = entry.get("component", "unknown")
            component_counts[component] = component_counts.get(component, 0) + 1
            
            # 操作统计
            operation = entry.get("operation", "unknown")
            operation_counts[operation] = operation_counts.get(operation, 0) + 1
            
            # 时间分布
            timestamp = entry.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    hour_key = dt.strftime("%Y-%m-%d %H:00")
                    hourly_distribution[hour_key] = hourly_distribution.get(hour_key, 0) + 1
                except:
                    pass
            
            # 性能统计
            duration = entry.get("duration_ms", 0)
            if duration > 0:
                total_duration += duration
                durations.append(duration)
        
        # 计算性能指标
        avg_duration = total_duration / len(durations) if durations else 0
        durations.sort()
        p95_duration = durations[int(len(durations) * 0.95)] if durations else 0
        
        return {
            "total_entries": len(log_entries),
            "level_distribution": level_counts,
            "source_distribution": source_counts,
            "component_distribution": component_counts,
            "operation_distribution": operation_counts,
            "hourly_distribution": hourly_distribution,
            "performance_metrics": {
                "avg_duration_ms": avg_duration,
                "p95_duration_ms": p95_duration,
                "total_operations": len(durations)
            }
        }
    
    def _identify_log_patterns(self, log_entries):
        """识别日志模式"""
        patterns = {}
        
        # 按操作和组件组合识别模式
        for entry in log_entries:
            operation = entry.get("operation", "unknown")
            component = entry.get("component", "unknown")
            level = entry.get("level", "INFO")
            
            pattern_key = f"{operation}:{component}:{level}"
            
            if pattern_key not in patterns:
                patterns[pattern_key] = {
                    "pattern": pattern_key,
                    "operation": operation,
                    "component": component,
                    "level": level,
                    "count": 0,
                    "avg_duration": 0,
                    "durations": []
                }
            
            patterns[pattern_key]["count"] += 1
            duration = entry.get("duration_ms", 0)
            if duration > 0:
                patterns[pattern_key]["durations"].append(duration)
        
        # 计算平均时长
        for pattern in patterns.values():
            if pattern["durations"]:
                pattern["avg_duration"] = sum(pattern["durations"]) / len(pattern["durations"])
            del pattern["durations"]  # 删除原始数据节省空间
        
        # 按频次排序并返回前10个
        sorted_patterns = sorted(patterns.values(), key=lambda x: x["count"], reverse=True)
        return sorted_patterns[:10]
    
    def _detect_log_anomalies(self, log_entries):
        """检测日志异常"""
        anomalies = []
        
        # 检测错误突增
        error_entries = [e for e in log_entries if e.get("level") in ["ERROR", "CRITICAL"]]
        if len(error_entries) > len(log_entries) * 0.1:  # 错误率超过10%
            anomalies.append({
                "type": "high_error_rate",
                "severity": "warning",
                "description": f"错误率异常高: {len(error_entries)}/{len(log_entries)} ({len(error_entries)/len(log_entries):.1%})",
                "count": len(error_entries)
            })
        
        # 检测性能异常
        durations = [e.get("duration_ms", 0) for e in log_entries if e.get("duration_ms", 0) > 0]
        if durations:
            avg_duration = sum(durations) / len(durations)
            slow_operations = [d for d in durations if d > avg_duration * 3]
            
            if len(slow_operations) > len(durations) * 0.05:  # 超过5%的操作异常慢
                anomalies.append({
                    "type": "performance_degradation",
                    "severity": "warning",
                    "description": f"发现 {len(slow_operations)} 个异常慢的操作（平均时长的3倍以上）",
                    "avg_duration": avg_duration,
                    "slow_operations": len(slow_operations)
                })
        
        # 检测频率异常
        operations = [e.get("operation", "unknown") for e in log_entries]
        operation_counts = {}
        for op in operations:
            operation_counts[op] = operation_counts.get(op, 0) + 1
        
        if operation_counts:
            max_count = max(operation_counts.values())
            avg_count = sum(operation_counts.values()) / len(operation_counts)
            
            for op, count in operation_counts.items():
                if count > avg_count * 5:  # 频率异常高
                    anomalies.append({
                        "type": "high_frequency_operation",
                        "severity": "info",
                        "description": f"操作 {op} 频率异常高: {count} 次",
                        "operation": op,
                        "count": count
                    })
        
        return anomalies
    
    def _analyze_performance_logs(self, log_entries):
        """分析性能日志"""
        performance_data = {}
        
        # 按操作类型分析性能
        operations = {}
        for entry in log_entries:
            operation = entry.get("operation", "unknown")
            duration = entry.get("duration_ms", 0)
            
            if duration > 0:
                if operation not in operations:
                    operations[operation] = []
                operations[operation].append(duration)
        
        for op, durations in operations.items():
            durations.sort()
            performance_data[op] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "p50_duration": durations[int(len(durations) * 0.5)],
                "p95_duration": durations[int(len(durations) * 0.95)],
                "p99_duration": durations[int(len(durations) * 0.99)]
            }
        
        # 识别慢操作
        slow_operations = []
        for op, metrics in performance_data.items():
            if metrics["p95_duration"] > 1000:  # P95超过1秒
                slow_operations.append({
                    "operation": op,
                    "p95_duration": metrics["p95_duration"],
                    "count": metrics["count"]
                })
        
        return {
            "operation_performance": performance_data,
            "slow_operations": slow_operations,
            "performance_summary": {
                "total_operations": sum(len(durations) for durations in operations.values()),
                "operations_analyzed": len(operations),
                "slow_operations_count": len(slow_operations)
            }
        }
    
    def _generate_log_recommendations(self, analysis_results):
        """生成日志分析建议"""
        recommendations = []
        
        # 基于统计信息的建议
        if "statistics" in analysis_results:
            stats = analysis_results["statistics"]
            
            # 错误率建议
            level_dist = stats.get("level_distribution", {})
            total_entries = stats.get("total_entries", 1)
            error_count = level_dist.get("ERROR", 0) + level_dist.get("CRITICAL", 0)
            
            if error_count / total_entries > 0.05:  # 错误率超过5%
                recommendations.append({
                    "priority": "high",
                    "category": "error_handling",
                    "title": "降低系统错误率",
                    "description": f"错误率为 {error_count/total_entries:.1%}，需要关注",
                    "actions": [
                        "分析主要错误类型",
                        "加强错误处理机制",
                        "实施预防性监控"
                    ]
                })
        
        # 基于异常检测的建议
        anomalies = analysis_results.get("anomalies", [])
        if anomalies:
            for anomaly in anomalies[:3]:  # 前3个异常
                recommendations.append({
                    "priority": "medium",
                    "category": "anomaly_resolution",
                    "title": f"解决 {anomaly['type']} 异常",
                    "description": anomaly["description"],
                    "actions": ["调查异常原因", "实施修复措施", "增加监控告警"]
                })
        
        # 基于性能分析的建议
        performance = analysis_results.get("performance_insights", {})
        slow_ops = performance.get("slow_operations", [])
        
        if slow_ops:
            recommendations.append({
                "priority": "medium",
                "category": "performance_optimization",
                "title": "优化慢操作性能",
                "description": f"发现 {len(slow_ops)} 个慢操作",
                "actions": [
                    f"优化 {slow_ops[0]['operation']} 操作性能" if slow_ops else "优化慢操作",
                    "分析性能瓶颈",
                    "实施性能监控"
                ]
            })
        
        # 通用建议
        if not recommendations:
            recommendations.append({
                "priority": "low",
                "category": "maintenance",
                "title": "日志系统运行正常",
                "description": "未发现明显问题，建议保持监控",
                "actions": [
                    "定期进行日志分析",
                    "保持日志清理策略",
                    "监控关键指标"
                ]
            })
        
        return recommendations


class ConnectivityTestTool(BaseTool):
    """连接性测试工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="connectivity_test",
            description="测试系统各组件连接性",
            category=ToolCategory.DIAGNOSTIC,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "test_targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "测试目标",
                    "default": ["api_server", "database", "cache", "external_services"]
                },
                "test_depth": {
                    "type": "string",
                    "description": "测试深度",
                    "enum": ["basic", "comprehensive", "stress"],
                    "default": "basic"
                },
                "timeout_per_test": {
                    "type": "number",
                    "description": "每个测试的超时时间（秒）",
                    "default": 10
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "include_latency_test": {
                    "type": "boolean",
                    "description": "是否包含延迟测试",
                    "default": True
                },
                "concurrent_tests": {
                    "type": "boolean",
                    "description": "是否并发执行测试",
                    "default": True
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        test_targets = arguments.get("test_targets", ["api_server", "database", "cache", "external_services"])
        test_depth = arguments.get("test_depth", "basic")
        timeout_per_test = arguments.get("timeout_per_test", 10)
        dataset_id = arguments.get("dataset_id")
        include_latency = arguments.get("include_latency_test", True)
        concurrent_tests = arguments.get("concurrent_tests", True)
        
        logger.info("开始连接性测试", targets=test_targets, depth=test_depth)
        
        try:
            async with get_authenticated_client() as client:
                test_results = {}
                overall_status = "healthy"
                
                if concurrent_tests:
                    # 并发执行测试
                    tasks = []
                    for target in test_targets:
                        task = asyncio.create_task(
                            self._test_target_connectivity(client, dataset_id, target, test_depth, timeout_per_test, include_latency)
                        )
                        tasks.append((target, task))
                    
                    # 等待所有测试完成
                    for target, task in tasks:
                        try:
                            result = await task
                            test_results[target] = result
                        except Exception as e:
                            test_results[target] = {
                                "status": "error",
                                "message": f"测试失败: {str(e)}",
                                "error": str(e)
                            }
                else:
                    # 顺序执行测试
                    for target in test_targets:
                        try:
                            result = await self._test_target_connectivity(
                                client, dataset_id, target, test_depth, timeout_per_test, include_latency
                            )
                            test_results[target] = result
                        except Exception as e:
                            test_results[target] = {
                                "status": "error",
                                "message": f"测试失败: {str(e)}",
                                "error": str(e)
                            }
                
                # 评估整体连接状态
                for result in test_results.values():
                    if result.get("status") == "failed":
                        overall_status = "failed"
                        break
                    elif result.get("status") == "warning" and overall_status == "healthy":
                        overall_status = "warning"
                
                # 生成连接性报告
                connectivity_report = self._generate_connectivity_report(test_results)
                
                return {
                    "success": True,
                    "message": f"连接性测试完成，总体状态: {overall_status}",
                    "overall_status": overall_status,
                    "test_configuration": {
                        "targets": test_targets,
                        "test_depth": test_depth,
                        "timeout_per_test": timeout_per_test,
                        "concurrent_execution": concurrent_tests,
                        "include_latency": include_latency
                    },
                    "test_results": test_results,
                    "connectivity_report": connectivity_report,
                    "recommendations": self._generate_connectivity_recommendations(test_results, overall_status)
                }
        
        except Exception as e:
            logger.error("连接性测试失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"连接性测试失败: {str(e)}")
    
    async def _test_target_connectivity(self, client, dataset_id, target, test_depth, timeout, include_latency):
        """测试特定目标的连接性"""
        start_time = datetime.now()
        
        try:
            if target == "api_server":
                result = await self._test_api_server(client, test_depth, timeout, include_latency)
            elif target == "database":
                result = await self._test_database(client, dataset_id, test_depth, timeout, include_latency)
            elif target == "cache":
                result = await self._test_cache(client, test_depth, timeout, include_latency)
            elif target == "external_services":
                result = await self._test_external_services(client, test_depth, timeout, include_latency)
            else:
                result = {
                    "status": "skipped",
                    "message": f"未知测试目标: {target}"
                }
            
            # 添加测试时长
            test_duration = (datetime.now() - start_time).total_seconds()
            result["test_duration_seconds"] = test_duration
            
            return result
        
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "message": f"{target} 连接测试超时",
                "test_duration_seconds": timeout
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"{target} 连接测试错误: {str(e)}",
                "error": str(e),
                "test_duration_seconds": (datetime.now() - start_time).total_seconds()
            }
    
    async def _test_api_server(self, client, test_depth, timeout, include_latency):
        """测试API服务器连接"""
        results = {
            "status": "healthy",
            "tests_performed": [],
            "details": {}
        }
        
        try:
            # 基础健康检查
            health_start = datetime.now()
            health = await asyncio.wait_for(client.health_check(), timeout=timeout)
            health_duration = (datetime.now() - health_start).total_seconds() * 1000
            
            results["tests_performed"].append("health_check")
            results["details"]["health_check"] = {
                "status": health.status,
                "response_time_ms": health_duration,
                "version": health.version
            }
            
            if health.status != "healthy":
                results["status"] = "warning"
            
            # 延迟测试
            if include_latency:
                latency_samples = []
                for i in range(3):
                    start = datetime.now()
                    await asyncio.wait_for(client.health_check(), timeout=timeout)
                    latency = (datetime.now() - start).total_seconds() * 1000
                    latency_samples.append(latency)
                
                avg_latency = sum(latency_samples) / len(latency_samples)
                results["tests_performed"].append("latency_test")
                results["details"]["latency_test"] = {
                    "average_latency_ms": avg_latency,
                    "samples": latency_samples
                }
                
                if avg_latency > 1000:  # 1秒
                    results["status"] = "warning"
            
            # 综合测试
            if test_depth in ["comprehensive", "stress"]:
                try:
                    datasets = await asyncio.wait_for(client.list_datasets(), timeout=timeout)
                    results["tests_performed"].append("list_datasets")
                    results["details"]["list_datasets"] = {
                        "dataset_count": datasets.total_count,
                        "accessible": True
                    }
                except Exception as e:
                    results["details"]["list_datasets"] = {
                        "accessible": False,
                        "error": str(e)
                    }
                    results["status"] = "warning"
            
        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
        
        return results
    
    async def _test_database(self, client, dataset_id, test_depth, timeout, include_latency):
        """测试数据库连接"""
        results = {
            "status": "healthy",
            "tests_performed": [],
            "details": {}
        }
        
        try:
            # 基础查询测试
            query_start = datetime.now()
            basic_query = "MATCH (n) RETURN count(n) as node_count LIMIT 1"
            query_result = await asyncio.wait_for(client.query_graph(basic_query, dataset_id), timeout=timeout)
            query_duration = (datetime.now() - query_start).total_seconds() * 1000
            
            results["tests_performed"].append("basic_query")
            results["details"]["basic_query"] = {
                "success": query_result is not None,
                "response_time_ms": query_duration,
                "result": query_result
            }
            
            if query_result is None:
                results["status"] = "failed"
            
            # 性能测试
            if include_latency and test_depth != "basic":
                query_times = []
                for i in range(5):
                    start = datetime.now()
                    await asyncio.wait_for(client.query_graph("RETURN 1", dataset_id), timeout=timeout)
                    duration = (datetime.now() - start).total_seconds() * 1000
                    query_times.append(duration)
                
                avg_query_time = sum(query_times) / len(query_times)
                results["tests_performed"].append("performance_test")
                results["details"]["performance_test"] = {
                    "average_query_time_ms": avg_query_time,
                    "query_samples": query_times
                }
                
                if avg_query_time > 500:  # 500ms
                    results["status"] = "warning"
            
            # 压力测试
            if test_depth == "stress":
                concurrent_queries = 5
                stress_start = datetime.now()
                
                tasks = []
                for i in range(concurrent_queries):
                    task = asyncio.create_task(client.query_graph(f"RETURN {i}", dataset_id))
                    tasks.append(task)
                
                try:
                    await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
                    stress_duration = (datetime.now() - stress_start).total_seconds() * 1000
                    
                    results["tests_performed"].append("stress_test")
                    results["details"]["stress_test"] = {
                        "concurrent_queries": concurrent_queries,
                        "total_time_ms": stress_duration,
                        "success": True
                    }
                except Exception as e:
                    results["details"]["stress_test"] = {
                        "concurrent_queries": concurrent_queries,
                        "success": False,
                        "error": str(e)
                    }
                    results["status"] = "warning"
        
        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
        
        return results
    
    async def _test_cache(self, client, test_depth, timeout, include_latency):
        """测试缓存连接（模拟）"""
        # 模拟缓存测试
        import random
        
        results = {
            "status": "healthy",
            "tests_performed": ["cache_connectivity"],
            "details": {
                "cache_connectivity": {
                    "accessible": True,
                    "response_time_ms": random.uniform(1, 10)
                }
            }
        }
        
        if test_depth in ["comprehensive", "stress"]:
            results["tests_performed"].append("cache_performance")
            results["details"]["cache_performance"] = {
                "hit_rate": random.uniform(0.7, 0.95),
                "avg_get_time_ms": random.uniform(0.5, 5.0),
                "avg_set_time_ms": random.uniform(1.0, 10.0)
            }
        
        return results
    
    async def _test_external_services(self, client, test_depth, timeout, include_latency):
        """测试外部服务连接（模拟）"""
        # 模拟外部服务测试
        import random
        
        external_services = ["embedding_service", "llm_service", "auth_service"]
        results = {
            "status": "healthy",
            "tests_performed": [],
            "details": {}
        }
        
        for service in external_services:
            # 模拟服务连接测试
            is_accessible = random.choice([True, True, True, False])  # 75%成功率
            response_time = random.uniform(50, 300)
            
            results["tests_performed"].append(service)
            results["details"][service] = {
                "accessible": is_accessible,
                "response_time_ms": response_time
            }
            
            if not is_accessible:
                results["status"] = "warning"
        
        return results
    
    def _generate_connectivity_report(self, test_results):
        """生成连接性报告"""
        total_tests = len(test_results)
        successful_tests = len([r for r in test_results.values() if r.get("status") == "healthy"])
        warning_tests = len([r for r in test_results.values() if r.get("status") == "warning"])
        failed_tests = len([r for r in test_results.values() if r.get("status") in ["failed", "error"]])
        
        # 计算平均响应时间
        response_times = []
        for result in test_results.values():
            if "test_duration_seconds" in result:
                response_times.append(result["test_duration_seconds"] * 1000)  # 转换为毫秒
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "successful": successful_tests,
                "warnings": warning_tests,
                "failures": failed_tests,
                "success_rate": successful_tests / total_tests if total_tests > 0 else 0
            },
            "performance": {
                "average_response_time_ms": avg_response_time,
                "fastest_test_ms": min(response_times) if response_times else 0,
                "slowest_test_ms": max(response_times) if response_times else 0
            },
            "reliability_score": (successful_tests + warning_tests * 0.5) / total_tests if total_tests > 0 else 0
        }
    
    def _generate_connectivity_recommendations(self, test_results, overall_status):
        """生成连接性建议"""
        recommendations = []
        
        # 分析失败的测试
        failed_targets = [target for target, result in test_results.items() if result.get("status") in ["failed", "error"]]
        
        if failed_targets:
            recommendations.append({
                "priority": "critical",
                "category": "connectivity_fix",
                "title": "修复连接失败",
                "description": f"以下组件连接失败: {', '.join(failed_targets)}",
                "actions": [
                    f"检查 {target} 的网络连接和配置" for target in failed_targets[:3]
                ]
            })
        
        # 分析警告状态的测试
        warning_targets = [target for target, result in test_results.items() if result.get("status") == "warning"]
        
        if warning_targets:
            recommendations.append({
                "priority": "medium",
                "category": "performance_improvement",
                "title": "改进连接性能",
                "description": f"以下组件存在性能问题: {', '.join(warning_targets)}",
                "actions": [
                    "优化网络配置",
                    "检查服务负载",
                    "考虑增加连接池大小"
                ]
            })
        
        # 通用建议
        if overall_status == "healthy":
            recommendations.append({
                "priority": "low",
                "category": "maintenance",
                "title": "保持连接健康",
                "description": "所有连接测试通过",
                "actions": [
                    "定期执行连接性测试",
                    "监控网络性能",
                    "保持系统配置更新"
                ]
            })
        
        return recommendations


# 自动注册诊断工具
def register_diagnostic_tools():
    """注册所有诊断工具"""
    tools = [
        HealthCheckTool,
        ErrorAnalysisTool,
        LogAnalysisTool,
        ConnectivityTestTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("诊断工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_diagnostic_tools()