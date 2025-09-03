"""
企业级错误处理模块
统一的异常处理、日志记录和错误恢复机制
"""

import traceback
import logging
from typing import Any, Dict, Optional, Type, Union
from datetime import datetime
from functools import wraps
from schemas.mcp_models import MCPError, MCPErrorCodes


# ============================================================================
# 自定义异常类
# ============================================================================

class CogneeBaseException(Exception):
    """Cognee基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: int = MCPErrorCodes.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow()
        super().__init__(message)
    
    def to_mcp_error(self) -> MCPError:
        """转换为MCP错误对象"""
        return MCPError(
            code=self.error_code,
            message=self.message,
            data={
                "details": self.details,
                "timestamp": self.timestamp.isoformat(),
                "original_error": str(self.original_exception) if self.original_exception else None
            }
        )


class AuthenticationError(CogneeBaseException):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(message, error_code=MCPErrorCodes.AUTHENTICATION_ERROR, **kwargs)


class AuthorizationError(CogneeBaseException):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", **kwargs):
        super().__init__(message, error_code=MCPErrorCodes.AUTHORIZATION_ERROR, **kwargs)


class ResourceNotFoundError(CogneeBaseException):
    """资源未找到错误"""
    
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        message = f"{resource_type} '{resource_id}' 未找到"
        super().__init__(
            message, 
            error_code=MCPErrorCodes.RESOURCE_NOT_FOUND, 
            details={"resource_type": resource_type, "resource_id": resource_id},
            **kwargs
        )


class ResourceUnavailableError(CogneeBaseException):
    """资源不可用错误"""
    
    def __init__(self, message: str = "资源暂时不可用", **kwargs):
        super().__init__(message, error_code=MCPErrorCodes.RESOURCE_UNAVAILABLE, **kwargs)


class RateLimitExceededError(CogneeBaseException):
    """速率限制超过错误"""
    
    def __init__(self, limit: int, window: str, **kwargs):
        message = f"速率限制超过: {limit} 请求/{window}"
        super().__init__(
            message, 
            error_code=MCPErrorCodes.RATE_LIMIT_EXCEEDED,
            details={"limit": limit, "window": window},
            **kwargs
        )


class ToolExecutionError(CogneeBaseException):
    """工具执行错误"""
    
    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(
            f"工具 '{tool_name}' 执行失败: {message}",
            error_code=MCPErrorCodes.TOOL_EXECUTION_ERROR,
            details={"tool_name": tool_name},
            **kwargs
        )


class APIConnectionError(CogneeBaseException):
    """API连接错误"""
    
    def __init__(self, api_url: str, message: str = "API连接失败", **kwargs):
        super().__init__(
            f"{message}: {api_url}",
            details={"api_url": api_url},
            **kwargs
        )


class ValidationError(CogneeBaseException):
    """数据验证错误"""
    
    def __init__(self, field: str, value: Any, message: str, **kwargs):
        super().__init__(
            f"字段 '{field}' 验证失败: {message}",
            error_code=MCPErrorCodes.INVALID_PARAMS,
            details={"field": field, "value": str(value)},
            **kwargs
        )


# ============================================================================
# 错误处理器类
# ============================================================================

class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": []
        }
    
    def handle_exception(
        self, 
        exception: Exception, 
        context: Optional[Dict[str, Any]] = None
    ) -> MCPError:
        """处理异常并返回MCP错误"""
        context = context or {}
        
        # 更新统计信息
        self._update_error_stats(exception)
        
        # 记录日志
        self._log_exception(exception, context)
        
        # 转换为MCP错误
        if isinstance(exception, CogneeBaseException):
            return exception.to_mcp_error()
        
        # 处理标准异常
        return self._convert_standard_exception(exception, context)
    
    def _update_error_stats(self, exception: Exception) -> None:
        """更新错误统计"""
        self._error_stats["total_errors"] += 1
        
        error_type = type(exception).__name__
        if error_type not in self._error_stats["error_types"]:
            self._error_stats["error_types"][error_type] = 0
        self._error_stats["error_types"][error_type] += 1
        
        # 保持最近50个错误记录
        self._error_stats["recent_errors"].append({
            "type": error_type,
            "message": str(exception),
            "timestamp": datetime.utcnow().isoformat()
        })
        if len(self._error_stats["recent_errors"]) > 50:
            self._error_stats["recent_errors"] = self._error_stats["recent_errors"][-50:]
    
    def _log_exception(self, exception: Exception, context: Dict[str, Any]) -> None:
        """记录异常日志"""
        error_details = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        if isinstance(exception, CogneeBaseException):
            self.logger.error(
                f"Cognee异常: {exception.message}",
                extra={"error_details": error_details, "error_code": exception.error_code}
            )
        else:
            self.logger.error(
                f"未处理异常: {str(exception)}",
                extra={"error_details": error_details}
            )
    
    def _convert_standard_exception(
        self, 
        exception: Exception, 
        context: Dict[str, Any]
    ) -> MCPError:
        """转换标准异常为MCP错误"""
        error_mapping = {
            ValueError: MCPErrorCodes.INVALID_PARAMS,
            TypeError: MCPErrorCodes.INVALID_PARAMS,
            KeyError: MCPErrorCodes.INVALID_PARAMS,
            FileNotFoundError: MCPErrorCodes.RESOURCE_NOT_FOUND,
            PermissionError: MCPErrorCodes.AUTHORIZATION_ERROR,
            ConnectionError: MCPErrorCodes.RESOURCE_UNAVAILABLE,
            TimeoutError: MCPErrorCodes.RESOURCE_UNAVAILABLE,
        }
        
        error_code = error_mapping.get(type(exception), MCPErrorCodes.INTERNAL_ERROR)
        
        return MCPError(
            code=error_code,
            message=str(exception),
            data={
                "context": context,
                "exception_type": type(exception).__name__,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return self._error_stats.copy()
    
    def clear_error_stats(self) -> None:
        """清空错误统计"""
        self._error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": []
        }


# ============================================================================
# 错误处理装饰器
# ============================================================================

def handle_errors(
    error_handler: Optional[ErrorHandler] = None,
    reraise: bool = False,
    default_return: Any = None
):
    """错误处理装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or ErrorHandler()
                mcp_error = handler.handle_exception(e, {
                    "function": func.__name__,
                    "args": str(args)[:200],  # 限制长度避免日志过长
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                })
                
                if reraise:
                    raise
                
                return default_return or {"error": mcp_error.dict()}
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or ErrorHandler()
                mcp_error = handler.handle_exception(e, {
                    "function": func.__name__,
                    "args": str(args)[:200],
                    "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                })
                
                if reraise:
                    raise
                
                return default_return or {"error": mcp_error.dict()}
        
        # 根据函数是否为协程选择包装器
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def retry_on_error(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    retry_exceptions: tuple = (Exception,)
):
    """错误重试装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # 指数退避
                    import asyncio
                    delay = backoff_factor * (2 ** attempt)
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # 指数退避
                    import time
                    delay = backoff_factor * (2 ** attempt)
                    time.sleep(delay)
            
            raise last_exception
        
        # 根据函数是否为协程选择包装器
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# 全局错误处理器实例
# ============================================================================

# 创建全局错误处理器
global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return global_error_handler


# ============================================================================
# 错误恢复策略
# ============================================================================

class ErrorRecoveryStrategy:
    """错误恢复策略"""
    
    @staticmethod
    async def recover_api_connection(api_client, max_attempts: int = 3) -> bool:
        """API连接错误恢复"""
        for attempt in range(max_attempts):
            try:
                await api_client.health_check()
                return True
            except Exception:
                if attempt < max_attempts - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        return False
    
    @staticmethod
    async def recover_authentication(auth_manager) -> bool:
        """认证错误恢复"""
        try:
            # 尝试使用刷新令牌
            await auth_manager.refresh_token()
            return True
        except Exception:
            try:
                # 尝试重新登录
                await auth_manager.login()
                return True
            except Exception:
                return False
    
    @staticmethod
    def recover_rate_limit(delay_seconds: int = 60) -> bool:
        """速率限制错误恢复"""
        import time
        time.sleep(delay_seconds)
        return True