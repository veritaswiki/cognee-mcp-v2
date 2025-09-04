"""
Cognee基础工具集
实现核心功能：add_text, add_files, cognify, search
"""

from typing import Any, Dict, List, Optional
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
from schemas.api_models import AddDataRequest, CognifyRequest, SearchRequest
import structlog

logger = structlog.get_logger(__name__)


class AddTextTool(BaseTool):
    """添加文本数据工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="add_text",
            description="添加纯文本数据到指定数据集",
            category=ToolCategory.BASIC,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "text": {
                    "type": "string",
                    "description": "要添加的文本内容"
                },
                "dataset_name": {
                    "type": "string", 
                    "description": "目标数据集名称",
                    "default": "main_dataset"
                }
            },
            required=["text"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        text = arguments.get("text", "")
        dataset_name = arguments.get("dataset_name", "main_dataset")
        
        if not text.strip():
            raise ToolExecutionError(self.metadata.name, "文本内容不能为空")
        
        logger.info("添加文本数据", dataset_name=dataset_name, text_length=len(text))
        
        try:
            async with get_authenticated_client() as client:
                result = await client.add_text(text, dataset_name)
                
                return {
                    "success": True,
                    "message": f"成功添加文本到数据集 '{dataset_name}'",
                    "dataset_id": result.dataset_id,
                    "ingested_count": result.ingested_count,
                    "processing_id": result.processing_id
                }
        
        except Exception as e:
            logger.error("添加文本失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"添加文本失败: {str(e)}")


class AddFilesTool(BaseTool):
    """添加文件数据工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="add_files",
            description="添加文件列表到指定数据集",
            category=ToolCategory.BASIC,
            requires_auth=True,
            timeout=120.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件路径列表或URL列表"
                },
                "dataset_name": {
                    "type": "string",
                    "description": "目标数据集名称",
                    "default": "main_dataset"
                }
            },
            required=["files"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        files = arguments.get("files", [])
        dataset_name = arguments.get("dataset_name", "main_dataset")
        
        if not files:
            raise ToolExecutionError(self.metadata.name, "文件列表不能为空")
        
        logger.info("添加文件数据", dataset_name=dataset_name, file_count=len(files))
        
        try:
            async with get_authenticated_client() as client:
                result = await client.add_files(files, dataset_name)
                
                return {
                    "success": True,
                    "message": f"成功添加 {len(files)} 个文件到数据集 '{dataset_name}'",
                    "dataset_id": result.dataset_id,
                    "ingested_count": result.ingested_count,
                    "failed_count": result.failed_count,
                    "processing_id": result.processing_id
                }
        
        except Exception as e:
            logger.error("添加文件失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"添加文件失败: {str(e)}")


class CognifyTool(BaseTool):
    """知识图谱构建工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="cognify",
            description="将数据集处理成知识图谱",
            category=ToolCategory.BASIC,
            requires_auth=True,
            timeout=300.0  # 5分钟超时
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "datasets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要处理的数据集名称列表"
                },
                "dataset_ids": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "要处理的数据集ID列表"
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "是否在后台运行",
                    "default": False
                }
            },
            required=[]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        datasets = arguments.get("datasets")
        dataset_ids = arguments.get("dataset_ids")
        run_in_background = arguments.get("run_in_background", False)
        
        if not datasets and not dataset_ids:
            # 如果没有指定数据集，处理所有数据集
            logger.info("未指定数据集，将处理所有可用数据集")
        
        logger.info(
            "开始知识图谱构建",
            datasets=datasets,
            dataset_ids=dataset_ids,
            background=run_in_background
        )
        
        try:
            async with get_authenticated_client() as client:
                request = CognifyRequest(
                    datasets=datasets,
                    dataset_ids=dataset_ids,
                    run_in_background=run_in_background
                )
                
                result = await client.cognify(request)
                
                return {
                    "success": True,
                    "message": "知识图谱构建任务已启动",
                    "pipeline_run_id": result.pipeline_run_id,
                    "status": result.status,
                    "dataset_ids": result.dataset_ids,
                    "estimated_completion": result.estimated_completion.isoformat() if result.estimated_completion else None,
                    "background": run_in_background
                }
        
        except Exception as e:
            logger.error("知识图谱构建失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"知识图谱构建失败: {str(e)}")


class SearchTool(BaseTool):
    """语义搜索工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="search",
            description="在知识图谱中进行语义搜索",
            category=ToolCategory.BASIC,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "query": {
                    "type": "string",
                    "description": "搜索查询文本"
                },
                "limit": {
                    "type": "number",
                    "description": "返回结果数量限制",
                    "default": 10
                },
                "dataset_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限制搜索的数据集ID列表"
                },
                "search_type": {
                    "type": "string",
                    "description": "搜索类型",
                    "enum": ["graph_completion", "chunks", "summaries", "feedback"],
                    "default": "graph_completion"
                },
                "include_metadata": {
                    "type": "boolean",
                    "description": "是否包含元数据",
                    "default": True
                }
            },
            required=["query"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = arguments.get("query", "").strip()
        limit = arguments.get("limit", 10)
        dataset_ids = arguments.get("dataset_ids")
        search_type = arguments.get("search_type", "graph_completion")
        include_metadata = arguments.get("include_metadata", True)
        
        if not query:
            raise ToolExecutionError(self.metadata.name, "搜索查询不能为空")
        
        logger.info("执行语义搜索", query=query[:50], limit=limit, search_type=search_type)
        
        try:
            async with get_authenticated_client() as client:
                # 使用简化的搜索API
                result = await client.simple_search(query, limit, dataset_ids)
                
                # 格式化搜索结果
                formatted_results = []
                for item in result.results:
                    formatted_item = {
                        "id": item.id,
                        "content": item.content,
                        "score": item.score,
                        "source": item.source
                    }
                    
                    if include_metadata and item.metadata:
                        formatted_item["metadata"] = item.metadata
                    
                    formatted_results.append(formatted_item)
                
                return {
                    "success": True,
                    "query": result.query,
                    "results": formatted_results,
                    "total_count": result.total_count,
                    "search_time": result.search_time,
                    "search_type": search_type
                }
        
        except Exception as e:
            logger.error("语义搜索失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"语义搜索失败: {str(e)}")


class StatusTool(BaseTool):
    """服务状态检查工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="status",
            description="检查Cognee服务状态",
            category=ToolCategory.DIAGNOSTIC,
            requires_auth=False,
            timeout=10.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "detailed": {
                    "type": "boolean",
                    "description": "是否返回详细状态信息",
                    "default": False
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        detailed = arguments.get("detailed", False)
        
        logger.info("检查服务状态", detailed=detailed)
        
        try:
            async with get_authenticated_client() as client:
                if detailed:
                    result = await client.detailed_health_check()
                else:
                    health = await client.health_check()
                    result = {
                        "status": health.status,
                        "health": health.health,
                        "version": health.version,
                        "timestamp": health.timestamp.isoformat()
                    }
                
                return {
                    "success": True,
                    "message": "服务状态检查完成",
                    **result
                }
        
        except Exception as e:
            logger.error("状态检查失败", error=str(e))
            return {
                "success": False,
                "message": "服务状态检查失败",
                "error": str(e),
                "status": "unknown"
            }


# 自动注册所有基础工具
def register_base_tools():
    """注册所有基础工具"""
    tools = [
        AddTextTool,
        AddFilesTool,
        CognifyTool, 
        SearchTool,
        StatusTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("基础工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_base_tools()