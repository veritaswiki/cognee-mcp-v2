"""
MCP协议数据模型定义
基于JSON-RPC 2.0和MCP协议规范
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# MCP协议基础模型
# ============================================================================

class MCPMessage(BaseModel):
    """MCP消息基础模型"""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC版本")


class MCPRequest(MCPMessage):
    """MCP请求模型"""
    method: str = Field(description="请求方法")
    id: Union[str, int] = Field(description="请求ID")
    params: Optional[Dict[str, Any]] = Field(default=None, description="请求参数")


class MCPResponse(MCPMessage):
    """MCP响应模型"""
    id: Union[str, int] = Field(description="对应的请求ID")
    result: Optional[Dict[str, Any]] = Field(default=None, description="成功结果")
    error: Optional[Dict[str, Any]] = Field(default=None, description="错误信息")


class MCPError(BaseModel):
    """MCP错误模型"""
    code: int = Field(description="错误代码")
    message: str = Field(description="错误消息")
    data: Optional[Any] = Field(default=None, description="附加错误数据")


class MCPNotification(MCPMessage):
    """MCP通知模型"""
    method: str = Field(description="通知方法")
    params: Optional[Dict[str, Any]] = Field(default=None, description="通知参数")


# ============================================================================
# MCP服务器信息模型
# ============================================================================

class MCPServerInfo(BaseModel):
    """MCP服务器信息模型"""
    name: str = Field(description="服务器名称")
    version: str = Field(description="服务器版本")
    description: Optional[str] = Field(default=None, description="服务器描述")


class MCPCapabilities(BaseModel):
    """MCP服务器能力模型"""
    tools: Optional[Dict[str, Any]] = Field(default_factory=dict, description="工具能力")
    resources: Optional[Dict[str, Any]] = Field(default_factory=dict, description="资源能力")
    prompts: Optional[Dict[str, Any]] = Field(default_factory=dict, description="提示能力")


class MCPInitializeRequest(BaseModel):
    """MCP初始化请求模型"""
    protocol_version: str = Field(description="协议版本")
    capabilities: MCPCapabilities = Field(description="客户端能力")
    client_info: Dict[str, Any] = Field(description="客户端信息")


class MCPInitializeResponse(BaseModel):
    """MCP初始化响应模型"""
    protocol_version: str = Field(description="协议版本")
    capabilities: MCPCapabilities = Field(description="服务器能力")
    server_info: MCPServerInfo = Field(description="服务器信息")


# ============================================================================
# 工具相关模型
# ============================================================================

class ToolInputSchema(BaseModel):
    """工具输入模式模型"""
    type: str = Field(default="object", description="参数类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="参数属性")
    required: List[str] = Field(default_factory=list, description="必需参数")
    additionalProperties: bool = Field(default=False, description="是否允许额外属性")


class ToolDefinition(BaseModel):
    """工具定义模型"""
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    inputSchema: ToolInputSchema = Field(description="输入参数模式")


class ToolListResponse(BaseModel):
    """工具列表响应模型"""
    tools: List[ToolDefinition] = Field(description="工具定义列表")


class ToolCallRequest(BaseModel):
    """工具调用请求模型"""
    name: str = Field(description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolCallResult(BaseModel):
    """工具调用结果模型"""
    content: List[Dict[str, Any]] = Field(description="结果内容")
    isError: bool = Field(default=False, description="是否为错误结果")


# ============================================================================
# 资源相关模型
# ============================================================================

class ResourceDefinition(BaseModel):
    """资源定义模型"""
    uri: str = Field(description="资源URI")
    name: str = Field(description="资源名称")
    description: Optional[str] = Field(default=None, description="资源描述")
    mimeType: Optional[str] = Field(default=None, description="MIME类型")


class ResourceListResponse(BaseModel):
    """资源列表响应模型"""
    resources: List[ResourceDefinition] = Field(description="资源定义列表")


class ResourceContent(BaseModel):
    """资源内容模型"""
    uri: str = Field(description="资源URI")
    mimeType: str = Field(description="MIME类型")
    text: Optional[str] = Field(default=None, description="文本内容")
    blob: Optional[str] = Field(default=None, description="二进制内容(base64)")


class ResourceReadRequest(BaseModel):
    """资源读取请求模型"""
    uri: str = Field(description="资源URI")


class ResourceReadResponse(BaseModel):
    """资源读取响应模型"""
    contents: List[ResourceContent] = Field(description="资源内容列表")


# ============================================================================
# 提示相关模型
# ============================================================================

class PromptArgument(BaseModel):
    """提示参数模型"""
    name: str = Field(description="参数名称")
    description: Optional[str] = Field(default=None, description="参数描述")
    required: bool = Field(default=False, description="是否必需")


class PromptDefinition(BaseModel):
    """提示定义模型"""
    name: str = Field(description="提示名称")
    description: Optional[str] = Field(default=None, description="提示描述")
    arguments: List[PromptArgument] = Field(default_factory=list, description="参数列表")


class PromptListResponse(BaseModel):
    """提示列表响应模型"""
    prompts: List[PromptDefinition] = Field(description="提示定义列表")


class PromptMessage(BaseModel):
    """提示消息模型"""
    role: str = Field(description="消息角色")
    content: Dict[str, Any] = Field(description="消息内容")


class PromptGetRequest(BaseModel):
    """提示获取请求模型"""
    name: str = Field(description="提示名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="提示参数")


class PromptGetResponse(BaseModel):
    """提示获取响应模型"""
    description: Optional[str] = Field(default=None, description="提示描述")
    messages: List[PromptMessage] = Field(description="提示消息列表")


# ============================================================================
# 特定工具参数模型
# ============================================================================

class AddTextToolArgs(BaseModel):
    """添加文本工具参数"""
    text: str = Field(description="要添加的文本")
    dataset_name: Optional[str] = Field(default="main_dataset", description="数据集名称")


class AddFilesToolArgs(BaseModel):
    """添加文件工具参数"""
    files: List[str] = Field(description="文件路径列表")
    dataset_name: Optional[str] = Field(default="main_dataset", description="数据集名称")


class CognifyToolArgs(BaseModel):
    """知识图谱构建工具参数"""
    datasets: Optional[List[str]] = Field(default=None, description="数据集名称列表")
    dataset_ids: Optional[List[str]] = Field(default=None, description="数据集ID列表")
    run_in_background: bool = Field(default=False, description="是否后台运行")


class SearchToolArgs(BaseModel):
    """搜索工具参数"""
    query: str = Field(description="搜索查询")
    top_k: int = Field(default=10, description="返回结果数")
    rag: bool = Field(default=False, description="是否启用RAG")
    dataset_id: Optional[str] = Field(default=None, description="限制搜索的数据集")
    search_type: Optional[str] = Field(default="graph_completion", description="搜索类型")


class GraphQueryToolArgs(BaseModel):
    """图查询工具参数"""
    cypher: Optional[str] = Field(default=None, description="Cypher查询语句")
    dataset_id: Optional[str] = Field(default=None, description="数据集ID")


class MemoryAppendToolArgs(BaseModel):
    """记忆追加工具参数"""
    dataset_id: str = Field(description="数据集ID")
    role: str = Field(description="角色")
    content: str = Field(description="内容")


class MemoryFeedbackToolArgs(BaseModel):
    """记忆反馈工具参数"""
    dataset_id: str = Field(description="数据集ID")
    memory_index: int = Field(description="记忆索引")
    score: float = Field(description="评分")
    note: Optional[str] = Field(default=None, description="反馈注释")


class OntologyAttachToolArgs(BaseModel):
    """本体附加工具参数"""
    dataset_id: str = Field(description="数据集ID")
    ontology_path: str = Field(description="本体文件路径")


class OntologyExpandToolArgs(BaseModel):
    """本体扩展工具参数"""
    dataset_id: str = Field(description="数据集ID")
    term: str = Field(description="要扩展的术语")
    node_type: str = Field(default="individuals", description="节点类型")
    directed: bool = Field(default=True, description="是否有向")
    persist: bool = Field(default=False, description="是否持久化")


class TemporalQueryToolArgs(BaseModel):
    """时序查询工具参数"""
    dataset_id: str = Field(description="数据集ID")
    start_time: Optional[str] = Field(default=None, description="开始时间")
    end_time: Optional[str] = Field(default=None, description="结束时间")
    limit: int = Field(default=100, description="结果限制")


# ============================================================================
# 错误代码常量
# ============================================================================

class MCPErrorCodes:
    """MCP错误代码常量"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # 自定义错误代码
    AUTHENTICATION_ERROR = -32001
    AUTHORIZATION_ERROR = -32002
    RESOURCE_NOT_FOUND = -32003
    RESOURCE_UNAVAILABLE = -32004
    RATE_LIMIT_EXCEEDED = -32005
    TOOL_EXECUTION_ERROR = -32006