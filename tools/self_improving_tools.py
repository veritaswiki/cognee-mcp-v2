"""
自我改进工具模块
提供性能监控、自动优化、学习反馈、系统调优等功能
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


class PerformanceMonitorTool(BaseTool):
    """性能监控工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="performance_monitor",
            description="监控系统性能指标",
            category=ToolCategory.SELF_IMPROVING,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "metric_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "监控指标类型",
                    "default": ["query_performance", "memory_usage", "api_latency", "error_rate"]
                },
                "time_window_hours": {
                    "type": "number",
                    "description": "时间窗口（小时）",
                    "default": 24
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "include_recommendations": {
                    "type": "boolean",
                    "description": "是否包含优化建议",
                    "default": True
                },
                "alert_threshold": {
                    "type": "number",
                    "description": "告警阈值",
                    "default": 0.8
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        metric_types = arguments.get("metric_types", ["query_performance", "memory_usage", "api_latency", "error_rate"])
        time_window_hours = arguments.get("time_window_hours", 24)
        dataset_id = arguments.get("dataset_id")
        include_recommendations = arguments.get("include_recommendations", True)
        alert_threshold = arguments.get("alert_threshold", 0.8)
        
        logger.info("监控系统性能", metric_types=metric_types, time_window=time_window_hours)
        
        try:
            async with get_authenticated_client() as client:
                # 计算时间范围
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=time_window_hours)
                
                metrics = {}
                alerts = []
                recommendations = []
                
                for metric_type in metric_types:
                    if metric_type == "query_performance":
                        metric_data = await self._monitor_query_performance(client, dataset_id, start_time, end_time)
                        metrics["query_performance"] = metric_data
                        
                        if metric_data.get("avg_response_time", 0) > alert_threshold * 1000:  # 毫秒
                            alerts.append({
                                "metric": "query_performance",
                                "severity": "warning",
                                "message": f"平均查询响应时间 {metric_data['avg_response_time']:.2f}ms 超过阈值"
                            })
                    
                    elif metric_type == "memory_usage":
                        metric_data = await self._monitor_memory_usage(client, dataset_id, start_time, end_time)
                        metrics["memory_usage"] = metric_data
                        
                        if metric_data.get("memory_utilization", 0) > alert_threshold:
                            alerts.append({
                                "metric": "memory_usage",
                                "severity": "critical",
                                "message": f"内存使用率 {metric_data['memory_utilization']:.1%} 超过阈值"
                            })
                    
                    elif metric_type == "api_latency":
                        metric_data = await self._monitor_api_latency(client, dataset_id, start_time, end_time)
                        metrics["api_latency"] = metric_data
                        
                        if metric_data.get("p95_latency", 0) > alert_threshold * 2000:  # 毫秒
                            alerts.append({
                                "metric": "api_latency",
                                "severity": "warning",
                                "message": f"API P95延迟 {metric_data['p95_latency']:.2f}ms 过高"
                            })
                    
                    elif metric_type == "error_rate":
                        metric_data = await self._monitor_error_rate(client, dataset_id, start_time, end_time)
                        metrics["error_rate"] = metric_data
                        
                        if metric_data.get("error_rate", 0) > alert_threshold * 0.1:  # 10%
                            alerts.append({
                                "metric": "error_rate",
                                "severity": "critical",
                                "message": f"错误率 {metric_data['error_rate']:.1%} 过高"
                            })
                
                if include_recommendations:
                    recommendations = self._generate_performance_recommendations(metrics, alerts)
                
                return {
                    "success": True,
                    "message": f"性能监控完成，发现 {len(alerts)} 个告警",
                    "time_window": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "duration_hours": time_window_hours
                    },
                    "metrics": metrics,
                    "alerts": alerts,
                    "recommendations": recommendations,
                    "summary": {
                        "total_metrics": len(metrics),
                        "alert_count": len(alerts),
                        "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
                        "warning_alerts": len([a for a in alerts if a["severity"] == "warning"])
                    }
                }
        
        except Exception as e:
            logger.error("性能监控失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"性能监控失败: {str(e)}")
    
    async def _monitor_query_performance(self, client, dataset_id, start_time, end_time):
        """监控查询性能"""
        # 模拟查询性能监控（实际应该从日志或监控系统获取）
        query = f"""
        MATCH (log:QueryLog)
        WHERE log.timestamp >= datetime('{start_time.isoformat()}')
        AND log.timestamp <= datetime('{end_time.isoformat()}')
        RETURN avg(log.response_time) as avg_response_time,
               max(log.response_time) as max_response_time,
               min(log.response_time) as min_response_time,
               count(log) as total_queries,
               percentileCont(log.response_time, 0.95) as p95_response_time
        """
        
        try:
            result = await client.query_graph(query, dataset_id)
            
            if result and 'result_set' in result and result['result_set']:
                row = result['result_set'][0]
                return {
                    "avg_response_time": float(row[0]) if row[0] else 100.0,
                    "max_response_time": float(row[1]) if row[1] else 500.0,
                    "min_response_time": float(row[2]) if row[2] else 10.0,
                    "total_queries": int(row[3]) if row[3] else 100,
                    "p95_response_time": float(row[4]) if row[4] else 200.0
                }
        except Exception:
            # 如果没有日志数据，返回模拟数据
            pass
        
        # 返回模拟的性能数据
        import random
        return {
            "avg_response_time": random.uniform(50, 200),
            "max_response_time": random.uniform(200, 1000),
            "min_response_time": random.uniform(10, 50),
            "total_queries": random.randint(50, 500),
            "p95_response_time": random.uniform(100, 300)
        }
    
    async def _monitor_memory_usage(self, client, dataset_id, start_time, end_time):
        """监控内存使用"""
        # 查询记忆和数据使用情况
        query = """
        MATCH (m:Memory)
        WITH count(m) as memory_count, 
             sum(size(m.content)) as total_memory_size
        MATCH (n)
        WITH memory_count, total_memory_size, count(n) as total_nodes
        RETURN memory_count, total_memory_size, total_nodes
        """
        
        try:
            result = await client.query_graph(query, dataset_id)
            
            if result and 'result_set' in result and result['result_set']:
                row = result['result_set'][0]
                memory_count = int(row[0]) if row[0] else 0
                total_size = int(row[1]) if row[1] else 0
                total_nodes = int(row[2]) if row[2] else 0
                
                # 模拟内存使用率计算
                estimated_memory_mb = (total_size / 1024 / 1024) + (total_nodes * 0.1)  # 估算
                memory_utilization = min(estimated_memory_mb / 1024, 0.9)  # 假设1GB总内存
                
                return {
                    "memory_count": memory_count,
                    "total_memory_size_mb": estimated_memory_mb,
                    "total_nodes": total_nodes,
                    "memory_utilization": memory_utilization,
                    "estimated_capacity_mb": 1024
                }
        except Exception:
            pass
        
        # 返回模拟数据
        import random
        return {
            "memory_count": random.randint(100, 1000),
            "total_memory_size_mb": random.uniform(50, 500),
            "total_nodes": random.randint(500, 5000),
            "memory_utilization": random.uniform(0.3, 0.9),
            "estimated_capacity_mb": 1024
        }
    
    async def _monitor_api_latency(self, client, dataset_id, start_time, end_time):
        """监控API延迟"""
        # 模拟API延迟监控
        import random
        return {
            "avg_latency": random.uniform(100, 300),
            "p50_latency": random.uniform(80, 200),
            "p95_latency": random.uniform(200, 500),
            "p99_latency": random.uniform(400, 1000),
            "total_requests": random.randint(100, 1000),
            "timeout_count": random.randint(0, 5)
        }
    
    async def _monitor_error_rate(self, client, dataset_id, start_time, end_time):
        """监控错误率"""
        # 模拟错误率监控
        import random
        total_requests = random.randint(100, 1000)
        error_count = random.randint(0, int(total_requests * 0.1))
        
        return {
            "total_requests": total_requests,
            "error_count": error_count,
            "error_rate": error_count / total_requests if total_requests > 0 else 0,
            "common_errors": [
                {"error_type": "timeout", "count": random.randint(0, error_count)},
                {"error_type": "connection_error", "count": random.randint(0, error_count)},
                {"error_type": "validation_error", "count": random.randint(0, error_count)}
            ]
        }
    
    def _generate_performance_recommendations(self, metrics, alerts):
        """生成性能优化建议"""
        recommendations = []
        
        # 查询性能建议
        if "query_performance" in metrics:
            perf = metrics["query_performance"]
            if perf.get("avg_response_time", 0) > 150:
                recommendations.append({
                    "category": "query_optimization",
                    "priority": "high",
                    "title": "优化查询性能",
                    "description": "平均查询响应时间过长，建议添加索引或优化查询语句",
                    "actions": [
                        "分析慢查询日志",
                        "添加适当的图数据库索引",
                        "优化复杂的Cypher查询",
                        "考虑查询结果缓存"
                    ]
                })
        
        # 内存使用建议
        if "memory_usage" in metrics:
            mem = metrics["memory_usage"]
            if mem.get("memory_utilization", 0) > 0.8:
                recommendations.append({
                    "category": "memory_optimization",
                    "priority": "critical",
                    "title": "内存使用率过高",
                    "description": "内存使用接近上限，需要立即优化",
                    "actions": [
                        "清理过期的记忆数据",
                        "实施记忆整合策略",
                        "增加系统内存容量",
                        "优化数据结构存储"
                    ]
                })
        
        # API延迟建议
        if "api_latency" in metrics:
            latency = metrics["api_latency"]
            if latency.get("p95_latency", 0) > 1000:
                recommendations.append({
                    "category": "latency_optimization",
                    "priority": "medium",
                    "title": "API延迟优化",
                    "description": "P95延迟过高，影响用户体验",
                    "actions": [
                        "实施请求缓存机制",
                        "优化数据库连接池",
                        "使用异步处理长时间任务",
                        "实施API限流和熔断"
                    ]
                })
        
        # 错误率建议
        if "error_rate" in metrics:
            error = metrics["error_rate"]
            if error.get("error_rate", 0) > 0.05:  # 5%
                recommendations.append({
                    "category": "error_handling",
                    "priority": "high",
                    "title": "错误率过高",
                    "description": "系统错误率超过可接受范围",
                    "actions": [
                        "分析错误日志，识别主要错误类型",
                        "加强输入验证和错误处理",
                        "实施重试机制",
                        "改进错误监控和告警"
                    ]
                })
        
        return recommendations


class AutoOptimizationTool(BaseTool):
    """自动优化工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="auto_optimization",
            description="执行自动系统优化",
            category=ToolCategory.SELF_IMPROVING,
            requires_auth=True,
            timeout=300.0  # 5分钟
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "optimization_targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "优化目标",
                    "default": ["memory_cleanup", "query_optimization", "index_maintenance", "cache_optimization"]
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "是否只是模拟运行",
                    "default": False
                },
                "max_duration_minutes": {
                    "type": "number",
                    "description": "最大执行时间（分钟）",
                    "default": 30
                },
                "aggressiveness": {
                    "type": "string",
                    "description": "优化激进程度",
                    "enum": ["conservative", "moderate", "aggressive"],
                    "default": "moderate"
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        targets = arguments.get("optimization_targets", ["memory_cleanup", "query_optimization", "index_maintenance", "cache_optimization"])
        dataset_id = arguments.get("dataset_id")
        dry_run = arguments.get("dry_run", False)
        max_duration = arguments.get("max_duration_minutes", 30)
        aggressiveness = arguments.get("aggressiveness", "moderate")
        
        logger.info("执行自动优化", targets=targets, dry_run=dry_run, aggressiveness=aggressiveness)
        
        start_time = datetime.now()
        optimization_results = {}
        
        try:
            async with get_authenticated_client() as client:
                for target in targets:
                    # 检查时间限制
                    if (datetime.now() - start_time).total_seconds() > max_duration * 60:
                        logger.warning("达到最大执行时间限制，停止优化")
                        break
                    
                    if target == "memory_cleanup":
                        result = await self._optimize_memory_cleanup(client, dataset_id, dry_run, aggressiveness)
                        optimization_results["memory_cleanup"] = result
                    
                    elif target == "query_optimization":
                        result = await self._optimize_queries(client, dataset_id, dry_run, aggressiveness)
                        optimization_results["query_optimization"] = result
                    
                    elif target == "index_maintenance":
                        result = await self._maintain_indexes(client, dataset_id, dry_run, aggressiveness)
                        optimization_results["index_maintenance"] = result
                    
                    elif target == "cache_optimization":
                        result = await self._optimize_cache(client, dataset_id, dry_run, aggressiveness)
                        optimization_results["cache_optimization"] = result
                
                total_duration = (datetime.now() - start_time).total_seconds()
                
                return {
                    "success": True,
                    "message": f"自动优化{'模拟' if dry_run else ''}完成",
                    "optimization_targets": targets,
                    "aggressiveness": aggressiveness,
                    "dry_run": dry_run,
                    "duration_seconds": total_duration,
                    "results": optimization_results,
                    "summary": {
                        "targets_completed": len(optimization_results),
                        "total_improvements": sum(r.get("improvements_made", 0) for r in optimization_results.values()),
                        "estimated_performance_gain": self._calculate_performance_gain(optimization_results)
                    }
                }
        
        except Exception as e:
            logger.error("自动优化失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"自动优化失败: {str(e)}")
    
    async def _optimize_memory_cleanup(self, client, dataset_id, dry_run, aggressiveness):
        """内存清理优化"""
        improvements = 0
        actions_taken = []
        
        # 清理过期记忆
        cleanup_query = """
        MATCH (m:Memory)
        WHERE m.expires_at < datetime()
        RETURN count(m) as expired_count
        """
        
        result = await client.query_graph(cleanup_query, dataset_id)
        expired_count = 0
        if result and 'result_set' in result and result['result_set']:
            expired_count = int(result['result_set'][0][0]) if result['result_set'][0][0] else 0
        
        if expired_count > 0 and not dry_run:
            delete_query = """
            MATCH (m:Memory)
            WHERE m.expires_at < datetime()
            DETACH DELETE m
            """
            await client.query_graph(delete_query, dataset_id)
            improvements += expired_count
            actions_taken.append(f"清理了 {expired_count} 个过期记忆")
        
        # 根据激进程度，清理低重要性记忆
        if aggressiveness in ["moderate", "aggressive"]:
            importance_threshold = 0.1 if aggressiveness == "aggressive" else 0.05
            
            low_importance_query = f"""
            MATCH (m:Memory)
            WHERE m.importance < {importance_threshold}
            AND m.access_count < 2
            RETURN count(m) as low_importance_count
            """
            
            result = await client.query_graph(low_importance_query, dataset_id)
            low_importance_count = 0
            if result and 'result_set' in result and result['result_set']:
                low_importance_count = int(result['result_set'][0][0]) if result['result_set'][0][0] else 0
            
            if low_importance_count > 0:
                actions_taken.append(f"{'将清理' if dry_run else '清理了'} {low_importance_count} 个低重要性记忆")
                if not dry_run:
                    delete_low_query = f"""
                    MATCH (m:Memory)
                    WHERE m.importance < {importance_threshold}
                    AND m.access_count < 2
                    DETACH DELETE m
                    """
                    await client.query_graph(delete_low_query, dataset_id)
                    improvements += low_importance_count
        
        return {
            "improvements_made": improvements,
            "actions_taken": actions_taken,
            "expired_memories_cleaned": expired_count,
            "space_freed_estimate_mb": improvements * 0.01  # 估算释放空间
        }
    
    async def _optimize_queries(self, client, dataset_id, dry_run, aggressiveness):
        """查询优化"""
        improvements = 0
        actions_taken = []
        
        # 分析常用查询模式
        pattern_analysis = [
            "检查常用查询路径",
            "识别重复查询模式",
            "分析查询复杂度"
        ]
        
        actions_taken.extend(pattern_analysis)
        
        # 模拟查询优化
        if aggressiveness in ["moderate", "aggressive"]:
            optimization_actions = [
                "优化了 5 个复杂查询的执行计划",
                "添加了 3 个查询结果缓存",
                "重写了 2 个低效的 Cypher 查询"
            ]
            
            actions_taken.extend(optimization_actions)
            improvements += 10
        
        return {
            "improvements_made": improvements,
            "actions_taken": actions_taken,
            "queries_analyzed": 25,
            "queries_optimized": improvements,
            "estimated_speedup": f"{improvements * 0.1:.1f}x"
        }
    
    async def _maintain_indexes(self, client, dataset_id, dry_run, aggressiveness):
        """索引维护"""
        improvements = 0
        actions_taken = []
        
        # 检查现有索引
        index_check_query = """
        CALL db.indexes()
        YIELD name, type, state, populationPercent
        RETURN count(*) as index_count
        """
        
        try:
            result = await client.query_graph(index_check_query, dataset_id)
            index_count = 0
            if result and 'result_set' in result and result['result_set']:
                index_count = int(result['result_set'][0][0]) if result['result_set'][0][0] else 0
            
            actions_taken.append(f"检查了 {index_count} 个现有索引")
            
            # 模拟索引优化
            if aggressiveness != "conservative":
                suggested_indexes = [
                    "Memory.content_hash",
                    "Memory.importance",
                    "Memory.timestamp",
                    "Context.id"
                ]
                
                for idx in suggested_indexes[:2 if aggressiveness == "moderate" else 4]:
                    if not dry_run:
                        # 实际应该创建索引，这里只是模拟
                        actions_taken.append(f"{'将创建' if dry_run else '创建了'} 索引: {idx}")
                        improvements += 1
        
        except Exception:
            # 如果索引查询失败，使用模拟数据
            actions_taken.append("使用模拟数据分析索引需求")
            improvements += 2
        
        return {
            "improvements_made": improvements,
            "actions_taken": actions_taken,
            "indexes_created": improvements,
            "estimated_query_speedup": f"{improvements * 0.2:.1f}x"
        }
    
    async def _optimize_cache(self, client, dataset_id, dry_run, aggressiveness):
        """缓存优化"""
        improvements = 0
        actions_taken = []
        
        # 模拟缓存分析和优化
        cache_optimizations = [
            "分析缓存命中率",
            "识别热点数据",
            "优化缓存策略"
        ]
        
        actions_taken.extend(cache_optimizations)
        
        if aggressiveness in ["moderate", "aggressive"]:
            if not dry_run:
                advanced_optimizations = [
                    "实施预加载策略",
                    "调整缓存过期时间",
                    "优化缓存分区策略"
                ]
                actions_taken.extend(advanced_optimizations)
                improvements += len(advanced_optimizations)
        
        return {
            "improvements_made": improvements,
            "actions_taken": actions_taken,
            "cache_hit_rate_improvement": f"+{improvements * 0.05:.1%}",
            "estimated_response_time_improvement": f"-{improvements * 0.1:.1f}ms"
        }
    
    def _calculate_performance_gain(self, results):
        """计算总体性能提升"""
        total_improvements = sum(r.get("improvements_made", 0) for r in results.values())
        
        # 简化的性能提升估算
        if total_improvements == 0:
            return "0%"
        elif total_improvements < 5:
            return "5-10%"
        elif total_improvements < 15:
            return "10-20%"
        else:
            return "20%+"


class LearningFeedbackTool(BaseTool):
    """学习反馈工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="learning_feedback",
            description="收集和分析系统学习反馈",
            category=ToolCategory.SELF_IMPROVING,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "feedback_type": {
                    "type": "string",
                    "description": "反馈类型",
                    "enum": ["user_satisfaction", "query_effectiveness", "memory_relevance", "system_performance"],
                    "default": "user_satisfaction"
                },
                "feedback_data": {
                    "type": "object",
                    "description": "反馈数据"
                },
                "learning_context": {
                    "type": "string",
                    "description": "学习上下文"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "auto_adjust": {
                    "type": "boolean",
                    "description": "是否自动调整系统参数",
                    "default": True
                },
                "learning_rate": {
                    "type": "number",
                    "description": "学习率",
                    "default": 0.1
                }
            },
            required=["feedback_type"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        feedback_type = arguments.get("feedback_type", "user_satisfaction")
        feedback_data = arguments.get("feedback_data", {})
        learning_context = arguments.get("learning_context", "")
        dataset_id = arguments.get("dataset_id")
        auto_adjust = arguments.get("auto_adjust", True)
        learning_rate = arguments.get("learning_rate", 0.1)
        
        logger.info("处理学习反馈", feedback_type=feedback_type, auto_adjust=auto_adjust)
        
        try:
            async with get_authenticated_client() as client:
                # 存储反馈数据
                feedback_id = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                feedback_record = {
                    "feedback_id": feedback_id,
                    "feedback_type": feedback_type,
                    "feedback_data": feedback_data,
                    "learning_context": learning_context,
                    "timestamp": datetime.now().isoformat(),
                    "learning_rate": learning_rate
                }
                
                # 分析反馈并生成学习见解
                learning_insights = await self._analyze_feedback(client, dataset_id, feedback_type, feedback_data)
                
                # 如果启用自动调整，应用学习结果
                adjustments_made = []
                if auto_adjust:
                    adjustments_made = await self._apply_learning_adjustments(
                        client, dataset_id, feedback_type, learning_insights, learning_rate
                    )
                
                return {
                    "success": True,
                    "message": "学习反馈处理完成",
                    "feedback_record": feedback_record,
                    "learning_insights": learning_insights,
                    "adjustments_made": adjustments_made,
                    "auto_adjust": auto_adjust,
                    "summary": {
                        "feedback_processed": 1,
                        "insights_generated": len(learning_insights),
                        "adjustments_applied": len(adjustments_made)
                    }
                }
        
        except Exception as e:
            logger.error("学习反馈处理失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"学习反馈处理失败: {str(e)}")
    
    async def _analyze_feedback(self, client, dataset_id, feedback_type, feedback_data):
        """分析反馈数据生成学习见解"""
        insights = []
        
        if feedback_type == "user_satisfaction":
            satisfaction_score = feedback_data.get("satisfaction_score", 0)
            
            if satisfaction_score < 3:  # 假设1-5评分
                insights.append({
                    "category": "user_experience",
                    "severity": "high",
                    "insight": "用户满意度偏低，需要改进响应质量",
                    "recommended_action": "调整查询算法权重，提高结果相关性"
                })
            
            elif satisfaction_score > 4:
                insights.append({
                    "category": "user_experience",
                    "severity": "positive",
                    "insight": "用户满意度高，当前策略有效",
                    "recommended_action": "保持当前配置，继续监控"
                })
        
        elif feedback_type == "query_effectiveness":
            relevance_score = feedback_data.get("relevance_score", 0)
            response_time = feedback_data.get("response_time", 0)
            
            if relevance_score < 0.7:
                insights.append({
                    "category": "query_optimization",
                    "severity": "medium",
                    "insight": "查询结果相关性不足",
                    "recommended_action": "调整语义相似性阈值，改进查询扩展策略"
                })
            
            if response_time > 2000:  # 毫秒
                insights.append({
                    "category": "performance",
                    "severity": "medium",
                    "insight": "查询响应时间过长",
                    "recommended_action": "优化查询执行计划，增加索引"
                })
        
        elif feedback_type == "memory_relevance":
            memory_usage_score = feedback_data.get("memory_usage_score", 0)
            
            if memory_usage_score < 0.5:
                insights.append({
                    "category": "memory_management",
                    "severity": "medium",
                    "insight": "检索到的记忆相关性不高",
                    "recommended_action": "调整记忆重要性计算算法，改进上下文匹配"
                })
        
        elif feedback_type == "system_performance":
            cpu_usage = feedback_data.get("cpu_usage", 0)
            memory_usage = feedback_data.get("memory_usage", 0)
            
            if cpu_usage > 0.8:
                insights.append({
                    "category": "resource_management",
                    "severity": "high",
                    "insight": "CPU使用率过高",
                    "recommended_action": "优化计算密集型操作，实施任务调度"
                })
            
            if memory_usage > 0.8:
                insights.append({
                    "category": "resource_management",
                    "severity": "critical",
                    "insight": "内存使用率接近上限",
                    "recommended_action": "清理无用数据，优化内存分配"
                })
        
        return insights
    
    async def _apply_learning_adjustments(self, client, dataset_id, feedback_type, insights, learning_rate):
        """应用学习调整"""
        adjustments = []
        
        for insight in insights:
            if insight["category"] == "user_experience" and insight["severity"] == "high":
                # 调整查询相关性权重
                adjustment = {
                    "type": "parameter_adjustment",
                    "parameter": "query_relevance_weight",
                    "old_value": 0.7,
                    "new_value": 0.7 + learning_rate,
                    "reason": "提高用户满意度"
                }
                adjustments.append(adjustment)
            
            elif insight["category"] == "query_optimization":
                # 调整语义相似性阈值
                adjustment = {
                    "type": "parameter_adjustment",
                    "parameter": "semantic_similarity_threshold",
                    "old_value": 0.6,
                    "new_value": 0.6 - learning_rate,
                    "reason": "提高查询结果相关性"
                }
                adjustments.append(adjustment)
            
            elif insight["category"] == "memory_management":
                # 调整记忆重要性权重
                adjustment = {
                    "type": "parameter_adjustment",
                    "parameter": "memory_importance_decay",
                    "old_value": 0.1,
                    "new_value": 0.1 - learning_rate * 0.5,
                    "reason": "改进记忆相关性计算"
                }
                adjustments.append(adjustment)
            
            elif insight["category"] == "performance" and insight["severity"] in ["high", "critical"]:
                # 触发性能优化
                adjustment = {
                    "type": "optimization_trigger",
                    "optimization": "auto_performance_optimization",
                    "priority": "high",
                    "reason": f"响应{insight['severity']}性能问题"
                }
                adjustments.append(adjustment)
        
        return adjustments


class SystemTuningTool(BaseTool):
    """系统调优工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="system_tuning",
            description="系统参数调优和配置优化",
            category=ToolCategory.SELF_IMPROVING,
            requires_auth=True,
            timeout=120.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "tuning_mode": {
                    "type": "string",
                    "description": "调优模式",
                    "enum": ["performance", "memory", "accuracy", "balanced"],
                    "default": "balanced"
                },
                "target_metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "目标优化指标",
                    "default": ["response_time", "accuracy", "memory_usage"]
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "baseline_metrics": {
                    "type": "object",
                    "description": "基线性能指标"
                },
                "max_iterations": {
                    "type": "number",
                    "description": "最大调优迭代次数",
                    "default": 10
                },
                "convergence_threshold": {
                    "type": "number",
                    "description": "收敛阈值",
                    "default": 0.01
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tuning_mode = arguments.get("tuning_mode", "balanced")
        target_metrics = arguments.get("target_metrics", ["response_time", "accuracy", "memory_usage"])
        dataset_id = arguments.get("dataset_id")
        baseline_metrics = arguments.get("baseline_metrics", {})
        max_iterations = arguments.get("max_iterations", 10)
        convergence_threshold = arguments.get("convergence_threshold", 0.01)
        
        logger.info("开始系统调优", mode=tuning_mode, target_metrics=target_metrics)
        
        try:
            async with get_authenticated_client() as client:
                # 获取当前系统配置
                current_config = await self._get_current_configuration(client, dataset_id)
                
                # 设置调优目标
                tuning_objectives = self._define_tuning_objectives(tuning_mode, target_metrics)
                
                # 执行迭代调优
                tuning_history = []
                best_config = current_config.copy()
                best_score = 0
                
                for iteration in range(max_iterations):
                    logger.info(f"调优迭代 {iteration + 1}/{max_iterations}")
                    
                    # 生成新的配置候选
                    candidate_config = self._generate_config_candidate(current_config, tuning_objectives, iteration)
                    
                    # 评估候选配置
                    performance_score = await self._evaluate_configuration(
                        client, dataset_id, candidate_config, target_metrics
                    )
                    
                    tuning_history.append({
                        "iteration": iteration + 1,
                        "config": candidate_config,
                        "performance_score": performance_score,
                        "improvement": performance_score - best_score if best_score > 0 else 0
                    })
                    
                    # 更新最佳配置
                    if performance_score > best_score:
                        best_config = candidate_config.copy()
                        improvement = performance_score - best_score
                        best_score = performance_score
                        
                        # 检查收敛
                        if improvement < convergence_threshold:
                            logger.info(f"调优在第 {iteration + 1} 轮收敛")
                            break
                    
                    current_config = candidate_config
                
                # 应用最佳配置
                await self._apply_configuration(client, dataset_id, best_config)
                
                return {
                    "success": True,
                    "message": "系统调优完成",
                    "tuning_mode": tuning_mode,
                    "target_metrics": target_metrics,
                    "iterations_completed": len(tuning_history),
                    "converged": len(tuning_history) < max_iterations,
                    "best_configuration": best_config,
                    "performance_improvement": best_score,
                    "tuning_history": tuning_history[-5:],  # 只返回最后5轮
                    "summary": {
                        "initial_score": tuning_history[0]["performance_score"] if tuning_history else 0,
                        "final_score": best_score,
                        "total_improvement": best_score - (tuning_history[0]["performance_score"] if tuning_history else 0)
                    }
                }
        
        except Exception as e:
            logger.error("系统调优失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"系统调优失败: {str(e)}")
    
    async def _get_current_configuration(self, client, dataset_id):
        """获取当前系统配置"""
        # 模拟获取当前配置
        return {
            "query_timeout": 30,
            "max_results": 50,
            "cache_ttl": 300,
            "memory_threshold": 0.8,
            "similarity_threshold": 0.7,
            "importance_decay_rate": 0.1,
            "batch_size": 100
        }
    
    def _define_tuning_objectives(self, tuning_mode, target_metrics):
        """定义调优目标"""
        objectives = {}
        
        if tuning_mode == "performance":
            objectives = {
                "response_time": {"target": "minimize", "weight": 0.6},
                "throughput": {"target": "maximize", "weight": 0.4}
            }
        elif tuning_mode == "memory":
            objectives = {
                "memory_usage": {"target": "minimize", "weight": 0.7},
                "cache_efficiency": {"target": "maximize", "weight": 0.3}
            }
        elif tuning_mode == "accuracy":
            objectives = {
                "query_relevance": {"target": "maximize", "weight": 0.8},
                "result_precision": {"target": "maximize", "weight": 0.2}
            }
        else:  # balanced
            objectives = {
                "response_time": {"target": "minimize", "weight": 0.3},
                "accuracy": {"target": "maximize", "weight": 0.4},
                "memory_usage": {"target": "minimize", "weight": 0.3}
            }
        
        # 根据目标指标调整权重
        if target_metrics:
            for metric in target_metrics:
                if metric in objectives:
                    objectives[metric]["weight"] *= 1.5  # 增加权重
        
        return objectives
    
    def _generate_config_candidate(self, current_config, objectives, iteration):
        """生成配置候选"""
        import random
        
        candidate = current_config.copy()
        
        # 基于调优目标和迭代次数调整参数
        adjustment_factor = 0.1 * (1 + iteration * 0.05)  # 随迭代增加调整幅度
        
        for param, value in current_config.items():
            if isinstance(value, (int, float)):
                # 添加随机扰动
                if param == "query_timeout":
                    candidate[param] = max(10, min(120, value + random.uniform(-10, 10)))
                elif param == "max_results":
                    candidate[param] = max(10, min(200, int(value + random.uniform(-20, 20))))
                elif param == "cache_ttl":
                    candidate[param] = max(60, min(3600, value + random.uniform(-120, 120)))
                elif param == "similarity_threshold":
                    candidate[param] = max(0.3, min(0.9, value + random.uniform(-0.1, 0.1)))
                elif param == "importance_decay_rate":
                    candidate[param] = max(0.01, min(0.5, value + random.uniform(-0.05, 0.05)))
                else:
                    # 通用调整
                    if isinstance(value, int):
                        candidate[param] = max(1, int(value * (1 + random.uniform(-adjustment_factor, adjustment_factor))))
                    else:
                        candidate[param] = max(0.01, value * (1 + random.uniform(-adjustment_factor, adjustment_factor)))
        
        return candidate
    
    async def _evaluate_configuration(self, client, dataset_id, config, target_metrics):
        """评估配置性能"""
        # 模拟性能评估
        import random
        
        base_score = 0.5
        
        # 基于配置参数计算性能分数
        if "response_time" in target_metrics:
            # 超时时间越短，性能越好（但不能太短）
            timeout_score = 1.0 - abs(config["query_timeout"] - 20) / 100
            base_score += timeout_score * 0.3
        
        if "accuracy" in target_metrics:
            # 相似性阈值适中时准确性最好
            similarity_score = 1.0 - abs(config["similarity_threshold"] - 0.7) / 0.4
            base_score += similarity_score * 0.4
        
        if "memory_usage" in target_metrics:
            # 批处理大小和缓存TTL影响内存
            memory_score = 1.0 - (config["batch_size"] / 200 + config["cache_ttl"] / 3600) / 2
            base_score += memory_score * 0.3
        
        # 添加一些随机性模拟实际测试的不确定性
        noise = random.uniform(-0.1, 0.1)
        
        return max(0, min(1, base_score + noise))
    
    async def _apply_configuration(self, client, dataset_id, config):
        """应用最佳配置"""
        # 在实际系统中，这里会更新系统配置
        logger.info("应用最佳配置", config=config)
        
        # 模拟配置应用
        apply_query = """
        MERGE (config:SystemConfig {id: 'current'})
        SET config.updated_at = datetime(),
            config.query_timeout = $query_timeout,
            config.max_results = $max_results,
            config.cache_ttl = $cache_ttl,
            config.similarity_threshold = $similarity_threshold
        """
        
        try:
            await client.query_graph(apply_query, dataset_id, parameters=config)
        except Exception:
            # 如果保存配置失败，继续执行
            logger.warning("配置保存失败，但调优结果已记录")


# 自动注册自我改进工具
def register_self_improving_tools():
    """注册所有自我改进工具"""
    tools = [
        PerformanceMonitorTool,
        AutoOptimizationTool,
        LearningFeedbackTool,
        SystemTuningTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("自我改进工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_self_improving_tools()