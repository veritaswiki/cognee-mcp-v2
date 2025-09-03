"""
Cognee MCP服务器核心实现
基于JSON-RPC 2.0协议的MCP服务器
"""

import asyncio
import json
import sys
from typing import Any, Dict, Optional, List, Union
from datetime import datetime
from config.settings import get_settings
from core.auth import get_auth_manager, AuthenticationManager
from core.tool_registry import get_tool_registry, ToolRegistry
from core.error_handler import get_error_handler, ErrorHandler, CogneeBaseException
from schemas.mcp_models import (
    MCPRequest, MCPResponse, MCPError, MCPNotification,
    MCPInitializeRequest, MCPInitializeResponse, MCPCapabilities, MCPServerInfo,
    ToolListResponse, ToolCallRequest, ToolCallResult,
    MCPErrorCodes
)
import structlog


logger = structlog.get_logger(__name__)


class MCPServer:
    """Cognee MCP服务器"""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.auth_manager = get_auth_manager()
        self.tool_registry = get_tool_registry()
        self.error_handler = get_error_handler()
        
        # 服务器状态
        self._initialized = False
        self._running = False
        self._client_capabilities: Optional[MCPCapabilities] = None
        
        # 统计信息
        self._request_count = 0
        self._error_count = 0
        self._start_time: Optional[datetime] = None
        
        logger.info(
            "MCP服务器初始化",
            server_name=self.settings.mcp.server_name,
            version=self.settings.mcp.server_version
        )
    
    async def start(self) -> None:
        """启动MCP服务器"""
        if self._running:
            logger.warning("MCP服务器已在运行")
            return
        
        self._running = True
        self._start_time = datetime.utcnow()
        
        logger.info("MCP服务器启动")
        
        try:
            # 主消息循环
            await self._message_loop()
        except Exception as e:
            logger.error("MCP服务器异常终止", error=str(e))
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """关闭MCP服务器"""
        if not self._running:
            return
        
        self._running = False
        
        # 清理资源
        await self.auth_manager.logout()
        
        logger.info("MCP服务器已关闭")
    
    async def _message_loop(self) -> None:
        """主消息循环"""
        while self._running:
            try:
                # 从stdin读取消息
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    # EOF，退出循环
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # 处理消息
                response = await self._handle_message(line)
                
                if response:
                    # 写入响应到stdout
                    output = json.dumps(response.dict() if hasattr(response, 'dict') else response)
                    print(output, flush=True)
            
            except KeyboardInterrupt:
                logger.info("收到中断信号，停止服务器")
                break
            except Exception as e:
                logger.error("消息循环异常", error=str(e))
                self._error_count += 1
    
    async def _handle_message(self, message: str) -> Optional[Union[MCPResponse, Dict[str, Any]]]:
        """处理单个消息"""
        self._request_count += 1
        
        try:
            # 解析JSON消息
            data = json.loads(message)
            
            # 检查是否为通知
            if "id" not in data:
                await self._handle_notification(data)
                return None
            
            # 处理请求
            request = MCPRequest(**data)
            return await self._handle_request(request)
        
        except json.JSONDecodeError as e:
            logger.error("JSON解析错误", error=str(e), message=message[:100])
            return self._create_error_response(
                None, MCPErrorCodes.PARSE_ERROR, f"JSON解析错误: {str(e)}"
            )
        
        except Exception as e:
            logger.error("消息处理异常", error=str(e))
            self._error_count += 1
            
            # 尝试从原始数据获取请求ID
            request_id = None
            try:
                data = json.loads(message)
                request_id = data.get("id")
            except:
                pass
            
            mcp_error = self.error_handler.handle_exception(e)
            return self._create_error_response(request_id, mcp_error.code, mcp_error.message)
    
    async def _handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理MCP请求"""
        method = request.method
        params = request.params or {}
        
        logger.debug("处理MCP请求", method=method, request_id=request.id)
        
        try:
            # 路由请求到相应的处理方法
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list(params)
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "resources/list":
                result = await self._handle_resources_list(params)
            elif method == "resources/read":
                result = await self._handle_resources_read(params)
            elif method == "prompts/list":
                result = await self._handle_prompts_list(params)
            elif method == "prompts/get":
                result = await self._handle_prompts_get(params)
            else:
                return self._create_error_response(
                    request.id, 
                    MCPErrorCodes.METHOD_NOT_FOUND, 
                    f"未知方法: {method}"
                )
            
            return MCPResponse(id=request.id, result=result)
        
        except CogneeBaseException as e:
            mcp_error = e.to_mcp_error()
            return self._create_error_response(request.id, mcp_error.code, mcp_error.message)
        
        except Exception as e:
            logger.error("请求处理异常", method=method, error=str(e))
            mcp_error = self.error_handler.handle_exception(e)
            return self._create_error_response(request.id, mcp_error.code, mcp_error.message)
    
    async def _handle_notification(self, data: Dict[str, Any]) -> None:
        """处理MCP通知"""
        method = data.get("method", "")
        params = data.get("params", {})
        
        logger.debug("处理MCP通知", method=method)
        
        # 处理不同类型的通知
        if method.startswith("notifications/"):
            # 客户端通知，暂时忽略
            pass
    
    # ========================================================================
    # 请求处理方法
    # ========================================================================
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理初始化请求"""
        init_request = MCPInitializeRequest(**params)
        
        # 保存客户端能力
        self._client_capabilities = init_request.capabilities
        
        # 创建服务器能力
        server_capabilities = MCPCapabilities(
            tools={"supports_listing": True, "supports_calling": True},
            resources={"supports_listing": True, "supports_reading": True},
            prompts={"supports_listing": True, "supports_getting": True}
        )
        
        # 创建服务器信息
        server_info = MCPServerInfo(
            name=self.settings.mcp.server_name,
            version=self.settings.mcp.server_version,
            description="Cognee知识图谱MCP服务器 - 企业级模块化重构版本"
        )
        
        self._initialized = True
        
        logger.info(
            "MCP初始化完成",
            client_info=init_request.client_info,
            protocol_version=init_request.protocol_version
        )
        
        # 返回初始化响应
        response = MCPInitializeResponse(
            protocol_version=self.settings.mcp.protocol_version,
            capabilities=server_capabilities,
            server_info=server_info
        )
        
        return response.dict()
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具列表请求"""
        if not self._initialized:
            raise CogneeBaseException("服务器尚未初始化", MCPErrorCodes.INTERNAL_ERROR)
        
        # 获取工具列表
        tools = self.tool_registry.list_tools(enabled_only=True)
        
        logger.debug("返回工具列表", tool_count=len(tools))
        
        response = ToolListResponse(tools=tools)
        return response.dict()
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用请求"""
        if not self._initialized:
            raise CogneeBaseException("服务器尚未初始化", MCPErrorCodes.INTERNAL_ERROR)
        
        call_request = ToolCallRequest(**params)
        
        # 认证检查
        tool = self.tool_registry.get_tool(call_request.name)
        if tool and tool.metadata.requires_auth:
            if not self.auth_manager.is_authenticated():
                try:
                    await self.auth_manager.authenticate()
                except Exception as e:
                    raise CogneeBaseException(
                        f"认证失败: {str(e)}", 
                        MCPErrorCodes.AUTHENTICATION_ERROR
                    )
        
        # 执行工具
        logger.info(
            "执行工具调用",
            tool_name=call_request.name,
            has_arguments=bool(call_request.arguments)
        )
        
        result = await self.tool_registry.call_tool(
            call_request.name,
            call_request.arguments,
            context={
                "server": self,
                "auth_manager": self.auth_manager,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return result.dict()
    
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理资源列表请求"""
        # 返回可用资源列表
        resources = [
            {
                "uri": "config://settings",
                "name": "服务器配置",
                "description": "当前服务器配置信息",
                "mimeType": "application/json"
            },
            {
                "uri": "stats://server",
                "name": "服务器统计",
                "description": "服务器运行统计信息",
                "mimeType": "application/json"
            },
            {
                "uri": "stats://tools",
                "name": "工具统计",
                "description": "工具执行统计信息",
                "mimeType": "application/json"
            }
        ]
        
        return {"resources": resources}
    
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理资源读取请求"""
        uri = params.get("uri", "")
        
        if uri == "config://settings":
            # 返回配置信息（敏感信息已脱敏）
            config_data = self._get_safe_config()
            content = json.dumps(config_data, indent=2, ensure_ascii=False)
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": content
                    }
                ]
            }
        
        elif uri == "stats://server":
            # 返回服务器统计
            stats = self._get_server_stats()
            content = json.dumps(stats, indent=2, ensure_ascii=False, default=str)
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": content
                    }
                ]
            }
        
        elif uri == "stats://tools":
            # 返回工具统计
            stats = self.tool_registry.get_tool_stats()
            content = json.dumps(stats, indent=2, ensure_ascii=False, default=str)
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json", 
                        "text": content
                    }
                ]
            }
        
        else:
            raise CogneeBaseException(f"未知资源: {uri}", MCPErrorCodes.RESOURCE_NOT_FOUND)
    
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理提示列表请求"""
        # 返回可用提示列表
        prompts = [
            {
                "name": "analyze_data",
                "description": "分析数据集并生成洞察",
                "arguments": [
                    {"name": "dataset_id", "description": "数据集ID", "required": True}
                ]
            },
            {
                "name": "create_summary",
                "description": "创建知识图谱摘要",
                "arguments": [
                    {"name": "dataset_id", "description": "数据集ID", "required": True},
                    {"name": "focus_area", "description": "聚焦领域", "required": False}
                ]
            }
        ]
        
        return {"prompts": prompts}
    
    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理提示获取请求"""
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if prompt_name == "analyze_data":
            dataset_id = arguments.get("dataset_id", "")
            
            messages = [
                {
                    "role": "system",
                    "content": {
                        "type": "text",
                        "text": f"你是一个数据分析专家，请分析数据集 {dataset_id} 并提供深入洞察。"
                    }
                },
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"请分析数据集 {dataset_id} 的内容，包括主要实体、关系模式和潜在价值。"
                    }
                }
            ]
            
            return {
                "description": f"分析数据集 {dataset_id}",
                "messages": messages
            }
        
        elif prompt_name == "create_summary":
            dataset_id = arguments.get("dataset_id", "")
            focus_area = arguments.get("focus_area", "全面")
            
            messages = [
                {
                    "role": "system",
                    "content": {
                        "type": "text",
                        "text": f"创建数据集 {dataset_id} 的 {focus_area} 摘要。"
                    }
                }
            ]
            
            return {
                "description": f"创建数据集摘要 ({focus_area})",
                "messages": messages
            }
        
        else:
            raise CogneeBaseException(f"未知提示: {prompt_name}", MCPErrorCodes.RESOURCE_NOT_FOUND)
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _create_error_response(self, request_id: Any, code: int, message: str) -> MCPResponse:
        """创建错误响应"""
        error = MCPError(code=code, message=message)
        return MCPResponse(id=request_id, error=error.dict())
    
    def _get_safe_config(self) -> Dict[str, Any]:
        """获取安全的配置信息（脱敏）"""
        config = {}
        
        # 服务器配置
        config["server"] = {
            "name": self.settings.mcp.server_name,
            "version": self.settings.mcp.server_version,
            "protocol_version": self.settings.mcp.protocol_version,
            "max_concurrent_requests": self.settings.mcp.max_concurrent_requests,
            "request_timeout": self.settings.mcp.request_timeout
        }
        
        # 功能配置
        config["features"] = {
            "time_awareness": self.settings.features.time_awareness,
            "ontology_support": self.settings.features.ontology_support,
            "async_memory": self.settings.features.async_memory,
            "self_improving": self.settings.features.self_improving,
            "advanced_analytics": self.settings.features.advanced_analytics
        }
        
        # API配置（脱敏）
        config["api"] = {
            "url": str(self.settings.api.api_url),
            "timeout": self.settings.api.timeout,
            "has_api_key": bool(self.settings.api.api_key),
            "has_credentials": bool(self.settings.api.api_email and self.settings.api.api_password)
        }
        
        return config
    
    def _get_server_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息"""
        uptime = None
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()
        
        return {
            "status": {
                "initialized": self._initialized,
                "running": self._running,
                "uptime_seconds": uptime,
                "start_time": self._start_time.isoformat() if self._start_time else None
            },
            "requests": {
                "total_requests": self._request_count,
                "error_count": self._error_count,
                "success_rate": (
                    (self._request_count - self._error_count) / self._request_count 
                    if self._request_count > 0 else 0
                )
            },
            "authentication": self.auth_manager.get_auth_status(),
            "tools": self.tool_registry.get_registry_info(),
            "errors": self.error_handler.get_error_stats()
        }
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器基本信息"""
        return {
            "name": self.settings.mcp.server_name,
            "version": self.settings.mcp.server_version,
            "protocol_version": self.settings.mcp.protocol_version,
            "initialized": self._initialized,
            "running": self._running,
            "uptime": (
                (datetime.utcnow() - self._start_time).total_seconds() 
                if self._start_time else None
            )
        }


# ============================================================================
# 服务器工厂和启动函数
# ============================================================================

def create_server(settings: Optional[Any] = None) -> MCPServer:
    """创建MCP服务器实例"""
    return MCPServer(settings)


async def start_server(settings: Optional[Any] = None) -> None:
    """启动MCP服务器"""
    server = create_server(settings)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as e:
        logger.error("服务器启动失败", error=str(e))
        raise
    finally:
        await server.shutdown()


# ============================================================================
# 主入口函数
# ============================================================================

async def main():
    """主入口函数"""
    try:
        # 配置日志
        import structlog
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(structlog.logging, get_settings().logging.level.upper(), 20)
            ),
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # 启动服务器
        await start_server()
    
    except Exception as e:
        logger.error("程序异常退出", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())