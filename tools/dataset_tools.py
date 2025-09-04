"""
数据集管理工具模块
提供数据集的创建、查询、删除等管理功能
"""

from typing import Any, Dict, List, Optional
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog

logger = structlog.get_logger(__name__)


class ListDatasetsTool(BaseTool):
    """列出所有数据集工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="datasets_list",
            description="获取用户可访问的所有数据集列表",
            category=ToolCategory.DATASET,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "include_empty": {
                    "type": "boolean",
                    "description": "是否包含空数据集",
                    "default": True
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        include_empty = arguments.get("include_empty", True)
        
        logger.info("获取数据集列表", include_empty=include_empty)
        
        try:
            async with get_authenticated_client() as client:
                dataset_list = await client.list_datasets()
                
                # 过滤空数据集
                datasets = dataset_list.datasets
                if not include_empty:
                    datasets = [ds for ds in datasets if ds.data_count > 0]
                
                # 格式化数据集信息
                formatted_datasets = []
                for dataset in datasets:
                    formatted_datasets.append({
                        "id": dataset.id,
                        "name": dataset.name,
                        "description": dataset.description,
                        "data_count": dataset.data_count,
                        "processing_status": dataset.processing_status,
                        "created_at": dataset.created_at.isoformat(),
                        "updated_at": dataset.updated_at.isoformat()
                    })
                
                return {
                    "success": True,
                    "message": f"找到 {len(formatted_datasets)} 个数据集",
                    "datasets": formatted_datasets,
                    "total_count": len(formatted_datasets)
                }
        
        except Exception as e:
            logger.error("获取数据集列表失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"获取数据集列表失败: {str(e)}")


class GetDatasetTool(BaseTool):
    """获取单个数据集详细信息工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="dataset_get",
            description="获取指定数据集的详细信息",
            category=ToolCategory.DATASET,
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
                    "description": "数据集ID"
                }
            },
            required=["dataset_id"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id", "").strip()
        
        if not dataset_id:
            raise ToolExecutionError(self.metadata.name, "数据集ID不能为空")
        
        logger.info("获取数据集详情", dataset_id=dataset_id)
        
        try:
            async with get_authenticated_client() as client:
                dataset = await client.get_dataset(dataset_id)
                
                return {
                    "success": True,
                    "message": "数据集信息获取成功",
                    "dataset": {
                        "id": dataset.id,
                        "name": dataset.name,
                        "description": dataset.description,
                        "owner_id": dataset.owner_id,
                        "data_count": dataset.data_count,
                        "processing_status": dataset.processing_status,
                        "created_at": dataset.created_at.isoformat(),
                        "updated_at": dataset.updated_at.isoformat()
                    }
                }
        
        except Exception as e:
            logger.error("获取数据集详情失败", dataset_id=dataset_id, error=str(e))
            raise ToolExecutionError(self.metadata.name, f"获取数据集详情失败: {str(e)}")


class DeleteDatasetTool(BaseTool):
    """删除数据集工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="dataset_delete",
            description="删除指定的数据集（谨慎操作）",
            category=ToolCategory.DATASET,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "要删除的数据集ID"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "确认删除操作",
                    "default": False
                }
            },
            required=["dataset_id", "confirm"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id", "").strip()
        confirm = arguments.get("confirm", False)
        
        if not dataset_id:
            raise ToolExecutionError(self.metadata.name, "数据集ID不能为空")
        
        if not confirm:
            raise ToolExecutionError(self.metadata.name, "必须确认删除操作 (confirm=true)")
        
        logger.warning("删除数据集", dataset_id=dataset_id)
        
        try:
            async with get_authenticated_client() as client:
                success = await client.delete_dataset(dataset_id)
                
                if success:
                    return {
                        "success": True,
                        "message": f"数据集 '{dataset_id}' 删除成功",
                        "dataset_id": dataset_id
                    }
                else:
                    return {
                        "success": False,
                        "message": f"数据集 '{dataset_id}' 删除失败",
                        "dataset_id": dataset_id
                    }
        
        except Exception as e:
            logger.error("删除数据集失败", dataset_id=dataset_id, error=str(e))
            raise ToolExecutionError(self.metadata.name, f"删除数据集失败: {str(e)}")


class DatasetStatsTool(BaseTool):
    """数据集统计信息工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="dataset_stats",
            description="获取数据集的统计信息",
            category=ToolCategory.DATASET,
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
                    "description": "数据集ID（可选，为空则统计所有数据集）"
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        
        logger.info("获取数据集统计", dataset_id=dataset_id)
        
        try:
            async with get_authenticated_client() as client:
                if dataset_id:
                    # 获取单个数据集统计
                    dataset = await client.get_dataset(dataset_id)
                    graph_stats = await client.get_graph_stats(dataset_id)
                    
                    return {
                        "success": True,
                        "message": "数据集统计获取成功",
                        "dataset_stats": {
                            "dataset_id": dataset.id,
                            "dataset_name": dataset.name,
                            "data_count": dataset.data_count,
                            "node_count": graph_stats.node_count,
                            "edge_count": graph_stats.edge_count,
                            "labels": graph_stats.labels,
                            "relationship_types": graph_stats.relationship_types
                        }
                    }
                else:
                    # 获取所有数据集统计
                    dataset_list = await client.list_datasets()
                    graph_stats = await client.get_graph_stats()
                    
                    total_data_count = sum(ds.data_count for ds in dataset_list.datasets)
                    
                    return {
                        "success": True,
                        "message": "全局统计获取成功",
                        "global_stats": {
                            "total_datasets": dataset_list.total_count,
                            "total_data_count": total_data_count,
                            "total_nodes": graph_stats.node_count,
                            "total_edges": graph_stats.edge_count,
                            "unique_labels": len(graph_stats.labels),
                            "unique_relationship_types": len(graph_stats.relationship_types)
                        },
                        "datasets": [
                            {
                                "id": ds.id,
                                "name": ds.name,
                                "data_count": ds.data_count,
                                "status": ds.processing_status
                            }
                            for ds in dataset_list.datasets
                        ]
                    }
        
        except Exception as e:
            logger.error("获取数据集统计失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"获取数据集统计失败: {str(e)}")


# 自动注册数据集工具
def register_dataset_tools():
    """注册所有数据集管理工具"""
    tools = [
        ListDatasetsTool,
        GetDatasetTool,
        DeleteDatasetTool,
        DatasetStatsTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("数据集管理工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_dataset_tools()