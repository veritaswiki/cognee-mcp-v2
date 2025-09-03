"""
Cognee API数据模型定义
基于官方API文档的请求和响应模型
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# 基础数据模型
# ============================================================================

class APIResponse(BaseModel):
    """API响应基础模型"""
    success: bool = Field(description="请求是否成功")
    data: Optional[Dict[str, Any]] = Field(default=None, description="响应数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    message: Optional[str] = Field(default=None, description="提示信息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间戳")


class HealthStatus(BaseModel):
    """健康状态模型"""
    status: str = Field(description="服务状态 (ready, degraded, down)")
    health: str = Field(description="健康状态 (healthy, unhealthy)")
    version: Optional[str] = Field(default=None, description="服务版本")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# 认证相关模型
# ============================================================================

class LoginRequest(BaseModel):
    """登录请求模型"""
    email: str = Field(description="用户邮箱")
    password: str = Field(description="用户密码")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: Optional[int] = Field(default=None, description="过期时间(秒)")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class TokenValidation(BaseModel):
    """令牌验证模型"""
    valid: bool = Field(description="令牌是否有效")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")


# ============================================================================
# 数据操作相关模型
# ============================================================================

class AddDataRequest(BaseModel):
    """添加数据请求模型"""
    data: List[str] = Field(description="要添加的数据列表(文件路径、URL等)")
    dataset_name: Optional[str] = Field(default=None, description="数据集名称")
    dataset_id: Optional[str] = Field(default=None, description="数据集ID")
    
    @validator('dataset_name', 'dataset_id')
    def validate_dataset_identifier(cls, v, values):
        """验证数据集标识符"""
        dataset_name = values.get('dataset_name')
        dataset_id = values.get('dataset_id')
        if not dataset_name and not dataset_id:
            raise ValueError('必须提供dataset_name或dataset_id')
        return v


class AddDataResponse(BaseModel):
    """添加数据响应模型"""
    dataset_id: str = Field(description="数据集ID")
    ingested_count: int = Field(description="成功摄入的数据条数")
    failed_count: int = Field(default=0, description="失败的数据条数")
    processing_id: Optional[str] = Field(default=None, description="处理任务ID")


# ============================================================================
# 知识图谱构建相关模型
# ============================================================================

class CognifyRequest(BaseModel):
    """知识图谱构建请求模型"""
    datasets: Optional[List[str]] = Field(default=None, description="数据集名称列表")
    dataset_ids: Optional[List[str]] = Field(default=None, description="数据集ID列表")
    run_in_background: bool = Field(default=False, description="是否后台运行")


class CognifyResponse(BaseModel):
    """知识图谱构建响应模型"""
    pipeline_run_id: str = Field(description="流水线运行ID")
    status: str = Field(description="处理状态")
    dataset_ids: List[str] = Field(description="涉及的数据集ID列表")
    estimated_completion: Optional[datetime] = Field(default=None, description="预估完成时间")


class PipelineStatus(BaseModel):
    """流水线状态模型"""
    pipeline_run_id: str = Field(description="流水线运行ID")
    status: str = Field(description="状态")
    progress: float = Field(default=0.0, description="进度百分比")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")


# ============================================================================
# 搜索相关模型
# ============================================================================

class SearchType(str, Enum):
    """搜索类型枚举"""
    GRAPH_COMPLETION = "graph_completion"
    CHUNKS = "chunks"
    SUMMARIES = "summaries"
    FEEDBACK = "feedback"  # 自我改进记忆搜索


class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: str = Field(description="搜索查询")
    search_type: SearchType = Field(default=SearchType.GRAPH_COMPLETION, description="搜索类型")
    dataset_ids: Optional[List[str]] = Field(default=None, description="限制搜索的数据集ID")
    limit: int = Field(default=10, description="返回结果数量限制")
    include_metadata: bool = Field(default=True, description="是否包含元数据")


class SearchResult(BaseModel):
    """搜索结果项模型"""
    id: str = Field(description="结果ID")
    content: str = Field(description="内容")
    score: float = Field(description="相关性得分")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")
    source: Optional[str] = Field(default=None, description="来源")


class SearchResponse(BaseModel):
    """搜索响应模型"""
    query: str = Field(description="原始查询")
    results: List[SearchResult] = Field(description="搜索结果列表")
    total_count: int = Field(description="总结果数")
    search_time: float = Field(description="搜索耗时(秒)")


# ============================================================================
# 数据集管理相关模型
# ============================================================================

class Dataset(BaseModel):
    """数据集模型"""
    id: str = Field(description="数据集ID")
    name: str = Field(description="数据集名称")
    description: Optional[str] = Field(default=None, description="描述")
    owner_id: str = Field(description="所有者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    data_count: int = Field(default=0, description="数据条数")
    processing_status: Optional[str] = Field(default=None, description="处理状态")


class DatasetList(BaseModel):
    """数据集列表模型"""
    datasets: List[Dataset] = Field(description="数据集列表")
    total_count: int = Field(description="总数量")


# ============================================================================
# 图数据库相关模型
# ============================================================================

class GraphNode(BaseModel):
    """图节点模型"""
    id: str = Field(description="节点ID")
    label: str = Field(description="节点标签")
    properties: Dict[str, Any] = Field(default_factory=dict, description="节点属性")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class GraphRelationship(BaseModel):
    """图关系模型"""
    id: str = Field(description="关系ID")
    type: str = Field(description="关系类型")
    source_id: str = Field(description="源节点ID")
    target_id: str = Field(description="目标节点ID")
    properties: Dict[str, Any] = Field(default_factory=dict, description="关系属性")


class GraphStats(BaseModel):
    """图统计信息模型"""
    node_count: int = Field(description="节点总数")
    edge_count: int = Field(description="边总数")
    labels: List[str] = Field(description="标签列表")
    relationship_types: List[str] = Field(description="关系类型列表")
    dataset_id: Optional[str] = Field(default=None, description="数据集ID")


# ============================================================================
# 时序感知相关模型
# ============================================================================

class TemporalQuery(BaseModel):
    """时序查询模型"""
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    node_labels: Optional[List[str]] = Field(default=None, description="节点标签过滤")
    limit: int = Field(default=100, description="结果限制")


class TemporalMetrics(BaseModel):
    """时序指标模型"""
    dataset_id: str = Field(description="数据集ID")
    time_window: str = Field(description="时间窗口")
    node_count: int = Field(description="节点数量")
    edge_count: int = Field(description="边数量")
    growth_rate: float = Field(description="增长率")
    timestamp: datetime = Field(description="指标时间戳")


# ============================================================================
# 本体支持相关模型
# ============================================================================

class OntologyAttachRequest(BaseModel):
    """本体附加请求模型"""
    dataset_id: str = Field(description="数据集ID")
    ontology_path: str = Field(description="本体文件路径")
    ontology_format: Optional[str] = Field(default="owl", description="本体格式")


class OntologyExpandRequest(BaseModel):
    """本体扩展请求模型"""
    dataset_id: str = Field(description="数据集ID")
    term: str = Field(description="要扩展的术语")
    node_type: str = Field(default="individuals", description="节点类型")
    directed: bool = Field(default=True, description="是否有向")
    persist: bool = Field(default=False, description="是否持久化")


class OntologyInfo(BaseModel):
    """本体信息模型"""
    id: str = Field(description="本体ID")
    name: str = Field(description="本体名称")
    format: str = Field(description="本体格式")
    classes_count: int = Field(description="类数量")
    properties_count: int = Field(description="属性数量")
    individuals_count: int = Field(description="个体数量")


# ============================================================================
# 记忆管理相关模型
# ============================================================================

class MemoryItem(BaseModel):
    """记忆项模型"""
    id: str = Field(description="记忆ID")
    role: str = Field(description="角色 (user, assistant, system)")
    content: str = Field(description="内容")
    dataset_id: str = Field(description="数据集ID")
    created_at: datetime = Field(description="创建时间")
    score: Optional[float] = Field(default=None, description="质量得分")
    feedback: Optional[str] = Field(default=None, description="反馈注释")


class MemoryAppendRequest(BaseModel):
    """记忆追加请求模型"""
    dataset_id: str = Field(description="数据集ID")
    role: str = Field(description="角色")
    content: str = Field(description="内容")


class MemoryFeedbackRequest(BaseModel):
    """记忆反馈请求模型"""
    dataset_id: str = Field(description="数据集ID")
    memory_index: int = Field(description="记忆索引")
    score: float = Field(ge=0.0, le=1.0, description="评分 (0-1)")
    note: Optional[str] = Field(default=None, description="反馈注释")


class MemoryWindowRequest(BaseModel):
    """记忆时间窗口请求模型"""
    dataset_id: str = Field(description="数据集ID")
    start_time: datetime = Field(description="开始时间")
    end_time: datetime = Field(description="结束时间")


# ============================================================================
# 批处理相关模型
# ============================================================================

class BatchOperation(BaseModel):
    """批处理操作模型"""
    operation_type: str = Field(description="操作类型")
    parameters: Dict[str, Any] = Field(description="操作参数")
    priority: int = Field(default=1, description="优先级")


class BatchRequest(BaseModel):
    """批处理请求模型"""
    operations: List[BatchOperation] = Field(description="操作列表")
    dataset_id: Optional[str] = Field(default=None, description="数据集ID")
    run_parallel: bool = Field(default=True, description="是否并行运行")


class BatchResult(BaseModel):
    """批处理结果模型"""
    batch_id: str = Field(description="批处理ID")
    total_operations: int = Field(description="总操作数")
    completed_operations: int = Field(description="已完成操作数")
    failed_operations: int = Field(description="失败操作数")
    status: str = Field(description="批处理状态")
    results: List[Dict[str, Any]] = Field(description="操作结果列表")