"""
图数据库操作工具模块
提供图查询、标签管理、统计等功能
"""

from typing import Any, Dict, List, Optional
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog

logger = structlog.get_logger(__name__)


class GraphQueryTool(BaseTool):
    """图数据库查询工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="graph_query",
            description="执行Cypher查询语句查询图数据库",
            category=ToolCategory.GRAPH,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "cypher": {
                    "type": "string",
                    "description": "Cypher查询语句"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选，限制查询范围）"
                }
            },
            required=["cypher"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cypher = arguments.get("cypher", "").strip()
        dataset_id = arguments.get("dataset_id")
        
        if not cypher:
            raise ToolExecutionError(self.metadata.name, "Cypher查询语句不能为空")
        
        logger.info("执行图查询", cypher=cypher[:100], dataset_id=dataset_id)
        
        try:
            async with get_authenticated_client() as client:
                result = await client.query_graph(cypher, dataset_id)
                
                return {
                    "success": True,
                    "message": "图查询执行成功",
                    "cypher": cypher,
                    "dataset_id": dataset_id,
                    "result": result
                }
        
        except Exception as e:
            logger.error("图查询执行失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"图查询执行失败: {str(e)}")


class GraphLabelsTool(BaseTool):
    """获取图标签工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="graph_labels",
            description="获取图数据库中的所有节点标签",
            category=ToolCategory.GRAPH,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "limit": {
                    "type": "number",
                    "description": "返回标签数量限制",
                    "default": 50
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        limit = arguments.get("limit", 50)
        
        logger.info("获取图标签", dataset_id=dataset_id, limit=limit)
        
        try:
            async with get_authenticated_client() as client:
                labels = await client.get_graph_labels(dataset_id, limit)
                
                return {
                    "success": True,
                    "message": f"找到 {len(labels)} 个图标签",
                    "dataset_id": dataset_id,
                    "labels": labels,
                    "count": len(labels)
                }
        
        except Exception as e:
            logger.error("获取图标签失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"获取图标签失败: {str(e)}")


class GraphStatsTool(BaseTool):
    """图统计信息工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="graph_stats",
            description="获取图数据库的统计信息",
            category=ToolCategory.GRAPH,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选，为空则返回全局统计）"
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        
        logger.info("获取图统计信息", dataset_id=dataset_id)
        
        try:
            async with get_authenticated_client() as client:
                stats = await client.get_graph_stats(dataset_id)
                
                return {
                    "success": True,
                    "message": "图统计信息获取成功",
                    "dataset_id": dataset_id,
                    "statistics": {
                        "node_count": stats.node_count,
                        "edge_count": stats.edge_count,
                        "unique_labels": len(stats.labels),
                        "unique_relationship_types": len(stats.relationship_types),
                        "labels": stats.labels,
                        "relationship_types": stats.relationship_types
                    }
                }
        
        except Exception as e:
            logger.error("获取图统计失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"获取图统计失败: {str(e)}")


class GraphSampleTool(BaseTool):
    """图采样工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="graph_sample",
            description="从图数据库中采样节点和关系进行检查",
            category=ToolCategory.GRAPH,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "node_limit": {
                    "type": "number",
                    "description": "节点采样数量",
                    "default": 10
                },
                "rel_limit": {
                    "type": "number",
                    "description": "关系采样数量", 
                    "default": 10
                },
                "label": {
                    "type": "string",
                    "description": "特定标签的节点（可选）"
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        node_limit = arguments.get("node_limit", 10)
        rel_limit = arguments.get("rel_limit", 10)
        label = arguments.get("label")
        
        logger.info("图数据采样", dataset_id=dataset_id, node_limit=node_limit, label=label)
        
        try:
            async with get_authenticated_client() as client:
                # 构造采样查询
                if label:
                    node_query = f"MATCH (n:{label}) RETURN n LIMIT {node_limit}"
                else:
                    node_query = f"MATCH (n) RETURN n LIMIT {node_limit}"
                
                rel_query = f"MATCH (a)-[r]->(b) RETURN a, r, b LIMIT {rel_limit}"
                
                # 执行查询
                node_result = await client.query_graph(node_query, dataset_id)
                rel_result = await client.query_graph(rel_query, dataset_id)
                
                return {
                    "success": True,
                    "message": "图数据采样完成",
                    "dataset_id": dataset_id,
                    "sample_data": {
                        "nodes": {
                            "query": node_query,
                            "result": node_result,
                            "limit": node_limit
                        },
                        "relationships": {
                            "query": rel_query,
                            "result": rel_result,
                            "limit": rel_limit
                        }
                    }
                }
        
        except Exception as e:
            logger.error("图数据采样失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"图数据采样失败: {str(e)}")


class GraphCountsByLabelTool(BaseTool):
    """按标签统计节点数量工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="graph_counts_by_label",
            description="按节点标签统计数量",
            category=ToolCategory.GRAPH,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "limit": {
                    "type": "number",
                    "description": "返回标签数量限制",
                    "default": 100
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        limit = arguments.get("limit", 100)
        
        logger.info("按标签统计节点", dataset_id=dataset_id, limit=limit)
        
        try:
            async with get_authenticated_client() as client:
                # 先获取所有标签
                labels = await client.get_graph_labels(dataset_id, limit)
                
                # 为每个标签统计节点数
                label_counts = {}
                for label in labels:
                    count_query = f"MATCH (n:{label}) RETURN count(n) as count"
                    result = await client.query_graph(count_query, dataset_id)
                    
                    # 解析计数结果
                    if result and 'result_set' in result and result['result_set']:
                        count = result['result_set'][0][0] if result['result_set'][0] else 0
                    else:
                        count = 0
                    
                    label_counts[label] = count
                
                # 按数量排序
                sorted_counts = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
                
                return {
                    "success": True,
                    "message": f"统计了 {len(sorted_counts)} 个标签的节点数量",
                    "dataset_id": dataset_id,
                    "label_counts": dict(sorted_counts),
                    "top_labels": sorted_counts[:10],  # 前10个
                    "total_labels": len(sorted_counts)
                }
        
        except Exception as e:
            logger.error("按标签统计失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"按标签统计失败: {str(e)}")


# 自动注册图工具
def register_graph_tools():
    """注册所有图数据库工具"""
    tools = [
        GraphQueryTool,
        GraphLabelsTool,
        GraphStatsTool,
        GraphSampleTool,
        GraphCountsByLabelTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("图数据库工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_graph_tools()