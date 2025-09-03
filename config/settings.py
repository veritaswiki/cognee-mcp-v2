"""
Cognee MCP v2.0 配置管理
企业级配置系统，支持环境变量、配置文件和动态配置
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import Field, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # 兼容Pydantic v1
    from pydantic import BaseSettings
from pydantic.networks import HttpUrl
import yaml


class CogneeAPISettings(BaseSettings):
    """Cognee API连接配置"""
    
    # API服务地址
    api_url: HttpUrl = Field(
        default="https://mcp-cognee.veritas.wiki",
        env="COGNEE_API_URL",
        description="Cognee API服务地址"
    )
    
    # API认证配置
    api_key: Optional[str] = Field(
        default=None, 
        env="COGNEE_API_KEY",
        description="JWT Token或API密钥"
    )
    api_key_header: str = Field(
        default="Authorization",
        env="COGNEE_API_KEY_HEADER", 
        description="API密钥请求头名称"
    )
    api_key_scheme: str = Field(
        default="Bearer",
        env="COGNEE_API_KEY_SCHEME",
        description="认证方案 (Bearer/Token/ApiKey)"
    )
    
    # 用户凭据 (备选认证方式)
    api_email: Optional[str] = Field(
        default=None,
        env="COGNEE_API_EMAIL",
        description="用户邮箱"
    )
    api_password: Optional[str] = Field(
        default=None,
        env="COGNEE_API_PASSWORD", 
        description="用户密码"
    )
    
    # 请求配置
    timeout: float = Field(
        default=180.0,
        env="COGNEE_TIMEOUT",
        description="API请求超时时间(秒)"
    )
    max_retries: int = Field(
        default=3,
        env="COGNEE_MAX_RETRIES",
        description="最大重试次数"
    )
    retry_delay: float = Field(
        default=1.0,
        env="COGNEE_RETRY_DELAY",
        description="重试延迟时间(秒)"
    )
    
    @validator('api_url')
    def validate_api_url(cls, v):
        """验证API URL格式"""
        if isinstance(v, str):
            if not v.startswith(('http://', 'https://')):
                raise ValueError('API URL必须以http://或https://开头')
        return v


class MCPServerSettings(BaseSettings):
    """MCP服务器配置"""
    
    protocol_version: str = Field(
        default="2024-11-05",
        env="MCP_PROTOCOL_VERSION",
        description="MCP协议版本"
    )
    server_name: str = Field(
        default="cognee-mcp-v2",
        env="MCP_SERVER_NAME",
        description="MCP服务器名称"
    )
    server_version: str = Field(
        default="2.0.0", 
        env="MCP_SERVER_VERSION",
        description="MCP服务器版本"
    )
    
    # 并发配置
    max_concurrent_requests: int = Field(
        default=10,
        env="MCP_MAX_CONCURRENT_REQUESTS",
        description="最大并发请求数"
    )
    request_timeout: float = Field(
        default=60.0,
        env="MCP_REQUEST_TIMEOUT",
        description="单个请求超时时间(秒)"
    )
    keepalive_timeout: float = Field(
        default=30.0,
        env="MCP_KEEPALIVE_TIMEOUT",
        description="连接保活超时(秒)"
    )


class FeatureSettings(BaseSettings):
    """功能模块配置"""
    
    # 功能开关
    time_awareness: bool = Field(
        default=True,
        env="FEATURE_TIME_AWARENESS",
        description="启用时序感知功能"
    )
    ontology_support: bool = Field(
        default=True,
        env="FEATURE_ONTOLOGY_SUPPORT",
        description="启用本体支持功能"
    )
    async_memory: bool = Field(
        default=True,
        env="FEATURE_ASYNC_MEMORY", 
        description="启用异步记忆功能"
    )
    self_improving: bool = Field(
        default=True,
        env="FEATURE_SELF_IMPROVING",
        description="启用自我改进功能"
    )
    advanced_analytics: bool = Field(
        default=True,
        env="FEATURE_ADVANCED_ANALYTICS",
        description="启用高级分析功能"
    )


class TemporalSettings(BaseSettings):
    """时序感知模块配置"""
    
    cache_size: int = Field(
        default=1000,
        env="TEMPORAL_CACHE_SIZE",
        description="时序数据缓存大小"
    )
    query_limit: int = Field(
        default=500,
        env="TEMPORAL_QUERY_LIMIT",
        description="时序查询结果限制"
    )
    metrics_interval: int = Field(
        default=300,
        env="TEMPORAL_METRICS_INTERVAL",
        description="时序指标收集间隔(秒)"
    )


class OntologySettings(BaseSettings):
    """本体支持模块配置"""
    
    cache_size: int = Field(
        default=100,
        env="ONTOLOGY_CACHE_SIZE",
        description="本体缓存大小"
    )
    max_file_size: int = Field(
        default=10485760,  # 10MB
        env="ONTOLOGY_MAX_FILE_SIZE",
        description="本体文件最大大小(字节)"
    )
    supported_formats: List[str] = Field(
        default=["owl", "rdf", "ttl", "xml"],
        env="ONTOLOGY_SUPPORTED_FORMATS",
        description="支持的本体文件格式"
    )


class MemorySettings(BaseSettings):
    """异步记忆模块配置"""
    
    batch_size: int = Field(
        default=100,
        env="MEMORY_BATCH_SIZE",
        description="批处理大小"
    )
    concurrent_limit: int = Field(
        default=20,
        env="MEMORY_CONCURRENT_LIMIT",
        description="并发操作限制"
    )
    cache_ttl: int = Field(
        default=3600,
        env="MEMORY_CACHE_TTL",
        description="缓存生存时间(秒)"
    )


class FeedbackSettings(BaseSettings):
    """自我改进模块配置"""
    
    sentiment_threshold: float = Field(
        default=0.5,
        env="FEEDBACK_SENTIMENT_THRESHOLD",
        description="情感分析阈值"
    )
    quality_threshold: float = Field(
        default=0.7,
        env="FEEDBACK_QUALITY_THRESHOLD", 
        description="质量评估阈值"
    )
    learning_rate: float = Field(
        default=0.01,
        env="FEEDBACK_LEARNING_RATE",
        description="学习率"
    )


class LoggingSettings(BaseSettings):
    """日志配置"""
    
    level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="日志级别"
    )
    format: str = Field(
        default="structured",
        env="LOG_FORMAT",
        description="日志格式 (structured, json, simple)"
    )
    file_path: Optional[Path] = Field(
        default=None,
        env="LOG_FILE_PATH",
        description="日志文件路径"
    )
    max_file_size: str = Field(
        default="100MB",
        env="LOG_MAX_FILE_SIZE",
        description="单个日志文件最大大小"
    )
    backup_count: int = Field(
        default=5,
        env="LOG_BACKUP_COUNT",
        description="日志文件备份数量"
    )


class MonitoringSettings(BaseSettings):
    """监控配置"""
    
    metrics_enabled: bool = Field(
        default=True,
        env="METRICS_ENABLED",
        description="启用指标收集"
    )
    metrics_port: int = Field(
        default=9090,
        env="METRICS_PORT",
        description="指标服务端口"
    )
    metrics_path: str = Field(
        default="/metrics",
        env="METRICS_PATH",
        description="指标端点路径"
    )
    health_check_interval: int = Field(
        default=30,
        env="HEALTH_CHECK_INTERVAL",
        description="健康检查间隔(秒)"
    )


class SecuritySettings(BaseSettings):
    """安全配置"""
    
    rate_limit_enabled: bool = Field(
        default=True,
        env="RATE_LIMIT_ENABLED",
        description="启用速率限制"
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        env="RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="每分钟请求限制"
    )
    rate_limit_requests_per_hour: int = Field(
        default=1000,
        env="RATE_LIMIT_REQUESTS_PER_HOUR",
        description="每小时请求限制"
    )
    encrypt_sensitive_data: bool = Field(
        default=True,
        env="ENCRYPT_SENSITIVE_DATA",
        description="加密敏感数据"
    )
    audit_log_enabled: bool = Field(
        default=True,
        env="AUDIT_LOG_ENABLED",
        description="启用审计日志"
    )


class CacheSettings(BaseSettings):
    """缓存配置"""
    
    type: str = Field(
        default="memory",
        env="CACHE_TYPE",
        description="缓存类型 (memory, redis, file)"
    )
    default_ttl: int = Field(
        default=3600,
        env="CACHE_DEFAULT_TTL",
        description="默认缓存生存时间(秒)"
    )
    max_size: int = Field(
        default=1000,
        env="CACHE_MAX_SIZE",
        description="缓存最大条目数"
    )
    
    # Redis配置
    redis_url: Optional[str] = Field(
        default=None,
        env="REDIS_URL",
        description="Redis连接URL"
    )
    redis_timeout: float = Field(
        default=5.0,
        env="REDIS_TIMEOUT",
        description="Redis操作超时(秒)"
    )


class Settings(BaseSettings):
    """主配置类 - 聚合所有配置模块"""
    
    # 基础配置
    debug: bool = Field(default=False, env="DEBUG", description="调试模式")
    dev_mode: bool = Field(default=False, env="DEV_MODE", description="开发模式")
    timezone: str = Field(default="UTC", env="TIMEZONE", description="时区")
    
    # 子配置模块
    api: CogneeAPISettings = CogneeAPISettings()
    mcp: MCPServerSettings = MCPServerSettings()
    features: FeatureSettings = FeatureSettings()
    temporal: TemporalSettings = TemporalSettings()
    ontology: OntologySettings = OntologySettings()
    memory: MemorySettings = MemorySettings()
    feedback: FeedbackSettings = FeedbackSettings()
    logging: LoggingSettings = LoggingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    security: SecuritySettings = SecuritySettings()
    cache: CacheSettings = CacheSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        use_enum_values = True
        env_nested_delimiter = '__'
    
    @classmethod
    def load_from_file(cls, config_file: Union[str, Path]) -> 'Settings':
        """从配置文件加载设置"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        if config_path.suffix.lower() in ['.yaml', '.yml']:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        elif config_path.suffix.lower() == '.json':
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")
        
        return cls(**config_data)
    
    def save_to_file(self, config_file: Union[str, Path]) -> None:
        """保存配置到文件"""
        config_path = Path(config_file)
        config_data = self.dict()
        
        if config_path.suffix.lower() in ['.yaml', '.yml']:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config_data, f, default_flow_style=False, allow_unicode=True)
        elif config_path.suffix.lower() == '.json':
            import json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")
    
    def get_cognee_auth_headers(self) -> Dict[str, str]:
        """获取Cognee API认证请求头"""
        headers = {}
        
        if self.api.api_key:
            if self.api.api_key_header.lower() == 'authorization':
                headers['Authorization'] = f"{self.api.api_key_scheme} {self.api.api_key}".strip()
            else:
                headers[self.api.api_key_header] = self.api.api_key
        
        return headers
    
    def is_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        feature_map = {
            'time_awareness': self.features.time_awareness,
            'ontology_support': self.features.ontology_support,
            'async_memory': self.features.async_memory,
            'self_improving': self.features.self_improving,
            'advanced_analytics': self.features.advanced_analytics,
        }
        return feature_map.get(feature, False)


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取全局配置实例"""
    return settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global settings
    settings = Settings()
    return settings