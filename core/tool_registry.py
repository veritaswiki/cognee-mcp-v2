"""
插件化工具注册表
动态工具管理和执行系统
"""

import asyncio
import inspect
from typing import Any, Dict, List, Optional, Callable, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from config.settings import get_settings
from core.error_handler import ToolExecutionError, ValidationError, handle_errors
from schemas.mcp_models import ToolDefinition, ToolInputSchema, ToolCallResult
import structlog


logger = structlog.get_logger(__name__)


class ToolCategory(str, Enum):
    """工具分类枚举"""
    BASIC = "basic"                    # 基础功能
    GRAPH = "graph"                    # 图数据库操作
    DATASET = "dataset"                # 数据集管理
    TEMPORAL = "temporal"              # 时序感知
    ONTOLOGY = "ontology"              # 本体支持
    MEMORY = "memory"                  # 异步记忆
    SELF_IMPROVING = "self_improving"  # 自我改进
    DIAGNOSTIC = "diagnostic"          # 诊断监控


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    category: ToolCategory
    description: str
    version: str = "1.0.0"
    author: Optional[str] = None
    requires_auth: bool = True
    requires_permissions: List[str] = None
    rate_limit: Optional[int] = None  # 每分钟调用次数限制
    timeout: float = 30.0  # 超时时间(秒)
    enabled: bool = True
    
    def __post_init__(self):
        if self.requires_permissions is None:
            self.requires_permissions = []


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata
        self._call_count = 0
        self._last_call_time = None
        self._execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_execution_time": 0.0,
            "average_execution_time": 0.0
        }
    
    @abstractmethod
    def get_input_schema(self) -> ToolInputSchema:
        """获取工具输入模式"""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行工具"""
        pass
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> None:
        """验证输入参数"""
        schema = self.get_input_schema()
        
        # 检查必需参数
        for required_field in schema.required:
            if required_field not in arguments:
                raise ValidationError(
                    required_field, 
                    None, 
                    f"缺少必需参数: {required_field}"
                )
        
        # 检查参数类型 (简单验证)
        for field_name, field_schema in schema.properties.items():
            if field_name in arguments:
                value = arguments[field_name]
                expected_type = field_schema.get('type')
                
                if expected_type == 'string' and not isinstance(value, str):
                    raise ValidationError(field_name, value, "期望字符串类型")
                elif expected_type == 'number' and not isinstance(value, (int, float)):
                    raise ValidationError(field_name, value, "期望数字类型")
                elif expected_type == 'boolean' and not isinstance(value, bool):
                    raise ValidationError(field_name, value, "期望布尔类型")
                elif expected_type == 'array' and not isinstance(value, list):
                    raise ValidationError(field_name, value, "期望数组类型")
                elif expected_type == 'object' and not isinstance(value, dict):
                    raise ValidationError(field_name, value, "期望对象类型")
    
    def to_tool_definition(self) -> ToolDefinition:
        """转换为工具定义"""
        return ToolDefinition(
            name=self.metadata.name,
            description=self.metadata.description,
            inputSchema=self.get_input_schema()
        )
    
    def update_stats(self, execution_time: float, success: bool) -> None:
        """更新执行统计"""
        self._execution_stats["total_calls"] += 1
        self._execution_stats["total_execution_time"] += execution_time
        
        if success:
            self._execution_stats["successful_calls"] += 1
        else:
            self._execution_stats["failed_calls"] += 1
        
        # 更新平均执行时间
        if self._execution_stats["total_calls"] > 0:
            self._execution_stats["average_execution_time"] = (
                self._execution_stats["total_execution_time"] / 
                self._execution_stats["total_calls"]
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        return {
            "metadata": self.metadata.__dict__,
            "stats": self._execution_stats.copy()
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[ToolCategory, List[str]] = {}
        self._rate_limiters: Dict[str, Dict[str, Any]] = {}
        
        # 初始化分类
        for category in ToolCategory:
            self._categories[category] = []
        
        logger.info("工具注册表初始化")
    
    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        tool_name = tool.metadata.name
        
        # 检查工具名称冲突
        if tool_name in self._tools:
            logger.warning("工具名称冲突，覆盖现有工具", tool_name=tool_name)
        
        # 注册工具
        self._tools[tool_name] = tool
        
        # 添加到分类
        category = tool.metadata.category
        if tool_name not in self._categories[category]:
            self._categories[category].append(tool_name)
        
        # 初始化速率限制器
        if tool.metadata.rate_limit:
            self._rate_limiters[tool_name] = {
                "calls": 0,
                "reset_time": None,
                "limit": tool.metadata.rate_limit
            }
        
        logger.info(
            "工具注册成功", 
            tool_name=tool_name, 
            category=category.value,
            requires_auth=tool.metadata.requires_auth
        )
    
    def unregister_tool(self, tool_name: str) -> bool:
        """取消注册工具"""
        if tool_name not in self._tools:
            return False
        
        tool = self._tools[tool_name]
        
        # 从分类中移除
        category = tool.metadata.category
        if tool_name in self._categories[category]:
            self._categories[category].remove(tool_name)
        
        # 移除速率限制器
        if tool_name in self._rate_limiters:
            del self._rate_limiters[tool_name]
        
        # 移除工具
        del self._tools[tool_name]
        
        logger.info("工具取消注册", tool_name=tool_name)
        return True
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(tool_name)
    
    def list_tools(self, category: Optional[ToolCategory] = None, enabled_only: bool = True) -> List[ToolDefinition]:
        """列出工具定义"""
        tools = []
        
        for tool_name, tool in self._tools.items():
            # 过滤条件
            if enabled_only and not tool.metadata.enabled:
                continue
            
            if category and tool.metadata.category != category:
                continue
            
            tools.append(tool.to_tool_definition())
        
        return tools
    
    def list_tool_names(self, category: Optional[ToolCategory] = None) -> List[str]:
        """列出工具名称"""
        if category:
            return self._categories[category].copy()
        
        return list(self._tools.keys())
    
    def get_categories(self) -> Dict[str, List[str]]:
        """获取工具分类"""
        return {cat.value: tools for cat, tools in self._categories.items()}
    
    @handle_errors(reraise=False)
    async def call_tool(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolCallResult:
        """调用工具"""
        import time
        
        # 获取工具
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolCallResult(
                content=[{"type": "text", "text": f"工具 '{tool_name}' 不存在"}],
                isError=True
            )
        
        # 检查工具是否启用
        if not tool.metadata.enabled:
            return ToolCallResult(
                content=[{"type": "text", "text": f"工具 '{tool_name}' 已禁用"}],
                isError=True
            )
        
        # 速率限制检查
        if not self._check_rate_limit(tool_name):
            return ToolCallResult(
                content=[{"type": "text", "text": f"工具 '{tool_name}' 达到速率限制"}],
                isError=True
            )
        
        # 参数验证
        try:
            tool.validate_arguments(arguments)
        except ValidationError as e:
            return ToolCallResult(
                content=[{"type": "text", "text": f"参数验证失败: {e.message}"}],
                isError=True
            )
        
        # 执行工具
        start_time = time.time()
        success = False
        
        try:
            # 设置超时
            result = await asyncio.wait_for(
                tool.execute(arguments, context),
                timeout=tool.metadata.timeout
            )
            
            success = True
            execution_time = time.time() - start_time
            
            # 更新统计
            tool.update_stats(execution_time, success)
            
            # 格式化结果
            if isinstance(result, dict):
                content = [{"type": "text", "text": str(result)}]
            elif isinstance(result, str):
                content = [{"type": "text", "text": result}]
            else:
                content = [{"type": "text", "text": str(result)}]
            
            logger.debug(
                "工具执行成功", 
                tool_name=tool_name, 
                execution_time=execution_time
            )
            
            return ToolCallResult(content=content, isError=False)
        
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            tool.update_stats(execution_time, success)
            
            return ToolCallResult(
                content=[{"type": "text", "text": f"工具 '{tool_name}' 执行超时"}],
                isError=True
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            tool.update_stats(execution_time, success)
            
            logger.error(
                "工具执行失败", 
                tool_name=tool_name, 
                error=str(e),
                execution_time=execution_time
            )
            
            return ToolCallResult(
                content=[{"type": "text", "text": f"工具执行失败: {str(e)}"}],
                isError=True
            )
    
    def _check_rate_limit(self, tool_name: str) -> bool:
        """检查速率限制"""
        if tool_name not in self._rate_limiters:
            return True
        
        import time
        from datetime import datetime, timedelta
        
        limiter = self._rate_limiters[tool_name]
        now = datetime.utcnow()
        
        # 重置计数器
        if limiter["reset_time"] is None or now >= limiter["reset_time"]:
            limiter["calls"] = 0
            limiter["reset_time"] = now + timedelta(minutes=1)
        
        # 检查限制
        if limiter["calls"] >= limiter["limit"]:
            return False
        
        limiter["calls"] += 1
        return True
    
    def get_tool_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """获取工具统计信息"""
        if tool_name:
            tool = self.get_tool(tool_name)
            return tool.get_stats() if tool else {}
        
        # 返回所有工具统计
        stats = {}
        for name, tool in self._tools.items():
            stats[name] = tool.get_stats()
        
        return stats
    
    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        tool = self.get_tool(tool_name)
        if tool:
            tool.metadata.enabled = True
            logger.info("工具已启用", tool_name=tool_name)
            return True
        return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        tool = self.get_tool(tool_name)
        if tool:
            tool.metadata.enabled = False
            logger.info("工具已禁用", tool_name=tool_name)
            return True
        return False
    
    def reload_tools(self) -> None:
        """重新加载工具"""
        # 清空现有工具
        self._tools.clear()
        for category in self._categories:
            self._categories[category].clear()
        self._rate_limiters.clear()
        
        logger.info("工具注册表已重置，需要重新注册工具")
    
    def get_registry_info(self) -> Dict[str, Any]:
        """获取注册表信息"""
        return {
            "total_tools": len(self._tools),
            "categories": {
                cat.value: len(tools) for cat, tools in self._categories.items()
            },
            "enabled_tools": len([t for t in self._tools.values() if t.metadata.enabled]),
            "disabled_tools": len([t for t in self._tools.values() if not t.metadata.enabled]),
            "rate_limited_tools": len(self._rate_limiters)
        }
    
    def get_tools_by_category(self) -> Dict[str, List[str]]:
        """按类别获取工具列表"""
        return {
            cat.value: tools.copy() for cat, tools in self._categories.items()
        }


# ============================================================================
# 工具装饰器
# ============================================================================

def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.BASIC,
    requires_auth: bool = True,
    rate_limit: Optional[int] = None,
    timeout: float = 30.0,
    **metadata_kwargs
):
    """工具装饰器"""
    def decorator(func):
        class DecoratedTool(BaseTool):
            def __init__(self):
                metadata = ToolMetadata(
                    name=name,
                    description=description,
                    category=category,
                    requires_auth=requires_auth,
                    rate_limit=rate_limit,
                    timeout=timeout,
                    **metadata_kwargs
                )
                super().__init__(metadata)
                self._func = func
            
            def get_input_schema(self) -> ToolInputSchema:
                # 从函数签名生成输入模式
                sig = inspect.signature(self._func)
                properties = {}
                required = []
                
                for param_name, param in sig.parameters.items():
                    if param_name in ['self', 'context']:
                        continue
                    
                    param_info = {"type": "string"}  # 默认类型
                    
                    # 根据类型注解推断
                    if param.annotation != param.empty:
                        if param.annotation == int:
                            param_info["type"] = "number"
                        elif param.annotation == float:
                            param_info["type"] = "number"
                        elif param.annotation == bool:
                            param_info["type"] = "boolean"
                        elif param.annotation == list:
                            param_info["type"] = "array"
                        elif param.annotation == dict:
                            param_info["type"] = "object"
                    
                    # 检查是否必需
                    if param.default == param.empty:
                        required.append(param_name)
                    else:
                        param_info["default"] = param.default
                    
                    properties[param_name] = param_info
                
                return ToolInputSchema(
                    type="object",
                    properties=properties,
                    required=required
                )
            
            async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                # 调用装饰的函数
                if inspect.iscoroutinefunction(self._func):
                    return await self._func(**arguments, context=context)
                else:
                    return self._func(**arguments, context=context)
        
        return DecoratedTool
    
    return decorator


# ============================================================================
# 全局工具注册表
# ============================================================================

_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool_class(tool_class: Type[BaseTool]) -> None:
    """注册工具类"""
    registry = get_tool_registry()
    tool_instance = tool_class()
    registry.register_tool(tool_instance)