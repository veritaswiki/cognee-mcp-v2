"""
Cognee MCP v2.0 主入口文件
企业级模块化重构版本
"""

import asyncio
import sys
import signal
import logging
from pathlib import Path
from typing import Optional
from config.settings import get_settings, Settings
from core.mcp_server import create_server, MCPServer
from core.auth import get_auth_manager
from core.tool_registry import get_tool_registry
from core.error_handler import get_error_handler
import structlog


def setup_logging(settings: Settings) -> None:
    """配置日志系统"""
    # 配置structlog
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            parameters=[structlog.processors.CallsiteParameter.FILENAME,
                       structlog.processors.CallsiteParameter.FUNC_NAME,
                       structlog.processors.CallsiteParameter.LINENO]
        ),
    ]
    
    # 选择输出格式
    if settings.logging.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    elif settings.logging.format == "structured":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.KeyValueRenderer())
    
    # 配置structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.logging.level.upper(), logging.INFO)
        ),
        logger_factory=structlog.WriteLoggerFactory(
            file=sys.stderr if not settings.logging.file_path else open(settings.logging.file_path, 'a')
        ),
        cache_logger_on_first_use=True,
    )


async def load_tools() -> None:
    """加载所有工具"""
    logger = structlog.get_logger(__name__)
    logger.info("开始加载工具")
    
    try:
        # 动态导入工具模块
        from tools import base_tools, graph_tools, dataset_tools
        
        # 如果功能启用，加载对应工具
        settings = get_settings()
        
        if settings.features.time_awareness:
            try:
                from tools import temporal_tools
                logger.info("时序感知工具已加载")
            except ImportError as e:
                logger.warning("时序感知工具加载失败", error=str(e))
        
        if settings.features.ontology_support:
            try:
                from tools import ontology_tools
                logger.info("本体支持工具已加载")
            except ImportError as e:
                logger.warning("本体支持工具加载失败", error=str(e))
        
        if settings.features.async_memory:
            try:
                from tools import memory_tools
                logger.info("异步记忆工具已加载")
            except ImportError as e:
                logger.warning("异步记忆工具加载失败", error=str(e))
        
        if settings.features.self_improving:
            try:
                from tools import self_improving_tools
                logger.info("自我改进工具已加载")
            except ImportError as e:
                logger.warning("自我改进工具加载失败", error=str(e))
        
        # 加载诊断工具
        try:
            from tools import diagnostic_tools
            logger.info("诊断工具已加载")
        except ImportError as e:
            logger.warning("诊断工具加载失败", error=str(e))
        
        # 获取工具统计
        registry = get_tool_registry()
        stats = registry.get_registry_info()
        logger.info("工具加载完成", **stats)
    
    except Exception as e:
        logger.error("工具加载失败", error=str(e))
        raise


async def initialize_services() -> None:
    """初始化所有服务"""
    logger = structlog.get_logger(__name__)
    logger.info("初始化服务")
    
    settings = get_settings()
    
    # 初始化认证管理器
    auth_manager = get_auth_manager()
    logger.info("认证管理器已初始化")
    
    # 初始化工具注册表
    tool_registry = get_tool_registry()
    logger.info("工具注册表已初始化")
    
    # 初始化错误处理器
    error_handler = get_error_handler()
    logger.info("错误处理器已初始化")
    
    # 加载工具
    await load_tools()
    
    logger.info("所有服务初始化完成")


async def health_check() -> bool:
    """健康检查"""
    logger = structlog.get_logger(__name__)
    
    try:
        settings = get_settings()
        auth_manager = get_auth_manager()
        
        # 检查配置
        if not settings.api.api_url:
            logger.error("API URL未配置")
            return False
        
        # 检查认证
        if not settings.api.api_key and not (settings.api.api_email and settings.api.api_password):
            logger.error("认证信息未配置")
            return False
        
        logger.info("健康检查通过")
        return True
    
    except Exception as e:
        logger.error("健康检查失败", error=str(e))
        return False


def setup_signal_handlers(server: MCPServer) -> None:
    """设置信号处理器"""
    logger = structlog.get_logger(__name__)
    
    def signal_handler(signum: int, frame) -> None:
        logger.info("收到停止信号", signal=signum)
        asyncio.create_task(server.shutdown())
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)


async def main() -> None:
    """主函数"""
    # 获取配置
    settings = get_settings()
    
    # 配置日志
    setup_logging(settings)
    logger = structlog.get_logger(__name__)
    
    logger.info(
        "启动Cognee MCP服务器",
        version=settings.mcp.server_version,
        name=settings.mcp.server_name
    )
    
    try:
        # 健康检查
        if not await health_check():
            logger.error("健康检查失败，服务器启动中止")
            sys.exit(1)
        
        # 初始化服务
        await initialize_services()
        
        # 创建服务器
        server = create_server(settings)
        
        # 设置信号处理
        setup_signal_handlers(server)
        
        # 启动服务器
        logger.info("MCP服务器启动中...")
        await server.start()
    
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭服务器")
    
    except Exception as e:
        logger.error("服务器启动失败", error=str(e))
        sys.exit(1)
    
    finally:
        logger.info("服务器已停止")


def cli_main() -> None:
    """CLI入口函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序被用户中断", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"程序异常退出: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()