"""
Cognee API客户端
基于官方API文档的异步HTTP客户端实现
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import httpx
from config.settings import get_settings
from core.error_handler import (
    APIConnectionError, 
    AuthenticationError, 
    ValidationError,
    handle_errors,
    retry_on_error,
    ErrorRecoveryStrategy
)
from schemas.api_models import (
    APIResponse, HealthStatus, LoginResponse, AddDataRequest, AddDataResponse,
    CognifyRequest, CognifyResponse, SearchRequest, SearchResponse,
    Dataset, DatasetList, GraphStats
)
import structlog


logger = structlog.get_logger(__name__)


class CogneeAPIClient:
    """Cognee API异步客户端"""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.base_url = str(self.settings.api.api_url).rstrip('/')
        self.timeout = self.settings.api.timeout
        
        # HTTP客户端配置
        self._client: Optional[httpx.AsyncClient] = None
        self._auth_headers: Dict[str, str] = {}
        self._session_cookie: Optional[str] = None
        
        # 认证状态
        self._authenticated = False
        self._token_expires_at: Optional[datetime] = None
        
        # 速率限制
        self._last_request_time = datetime.min
        self._request_count = 0
        self._rate_limit_window = timedelta(minutes=1)
        
        logger.info("Cognee API客户端初始化", base_url=self.base_url)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """确保HTTP客户端已初始化"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(
                    max_connections=self.settings.api.max_retries * 2,
                    max_keepalive_connections=5
                )
            )
    
    async def close(self) -> None:
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _check_rate_limit(self) -> None:
        """检查速率限制"""
        now = datetime.utcnow()
        
        # 重置计数器
        if now - self._last_request_time > self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = now
        
        # 检查限制
        if self._request_count >= self.settings.security.rate_limit_requests_per_minute:
            raise Exception(f"速率限制: 每分钟最多 {self.settings.security.rate_limit_requests_per_minute} 请求")
        
        self._request_count += 1
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证请求头"""
        headers = {"Content-Type": "application/json"}
        
        # API密钥认证
        if self.settings.api.api_key:
            if self.settings.api.api_key_header.lower() == 'authorization':
                auth_value = f"{self.settings.api.api_key_scheme} {self.settings.api.api_key}".strip()
                headers['Authorization'] = auth_value
            else:
                headers[self.settings.api.api_key_header] = self.settings.api.api_key
        
        # Cookie认证
        if self._session_cookie:
            headers['Cookie'] = self._session_cookie
        
        return headers
    
    @retry_on_error(max_retries=3, backoff_factor=1.0, retry_exceptions=(httpx.RequestError,))
    @handle_errors(reraise=False)
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发起HTTP请求"""
        await self._ensure_client()
        await self._check_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_auth_headers()
        
        logger.debug(
            "发起API请求",
            method=method,
            url=url,
            has_data=data is not None,
            has_params=params is not None
        )
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            )
            
            # 检查HTTP状态
            if response.status_code == 401:
                raise AuthenticationError("API认证失败，请检查认证信息")
            elif response.status_code == 403:
                raise AuthenticationError("权限不足，无法访问该资源")
            elif response.status_code == 429:
                raise Exception("API速率限制，请稍后重试")
            elif response.status_code >= 500:
                raise APIConnectionError(url, f"服务器错误: {response.status_code}")
            
            response.raise_for_status()
            
            # 解析响应
            if response.headers.get("content-type", "").startswith("application/json"):
                result = response.json()
            else:
                result = {"content": response.text}
            
            logger.debug(
                "API请求成功",
                status_code=response.status_code,
                response_size=len(str(result))
            )
            
            return result
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP错误 {e.response.status_code}"
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    error_msg = error_data["detail"]
            except:
                pass
            
            raise APIConnectionError(url, error_msg)
        
        except httpx.RequestError as e:
            raise APIConnectionError(url, f"请求失败: {str(e)}")
    
    # ========================================================================
    # 认证方法
    # ========================================================================
    
    @handle_errors(reraise=True)
    async def login(self, email: Optional[str] = None, password: Optional[str] = None) -> LoginResponse:
        """用户登录"""
        email = email or self.settings.api.api_email
        password = password or self.settings.api.api_password
        
        if not email or not password:
            raise AuthenticationError("缺少登录凭据")
        
        login_data = {"email": email, "password": password}
        
        try:
            response = await self._make_request("POST", "/api/v1/auth/login", data=login_data)
            
            login_result = LoginResponse(**response)
            
            # 更新认证状态
            if login_result.access_token:
                self._auth_headers["Authorization"] = f"Bearer {login_result.access_token}"
                self._authenticated = True
                
                if login_result.expires_in:
                    self._token_expires_at = datetime.utcnow() + timedelta(seconds=login_result.expires_in)
                
                logger.info("登录成功", user_id=login_result.user_id)
            
            return login_result
            
        except Exception as e:
            logger.error("登录失败", error=str(e))
            raise AuthenticationError(f"登录失败: {str(e)}")
    
    async def logout(self) -> bool:
        """用户登出"""
        try:
            await self._make_request("POST", "/api/v1/auth/logout")
            
            # 清理认证状态
            self._auth_headers.clear()
            self._session_cookie = None
            self._authenticated = False
            self._token_expires_at = None
            
            logger.info("登出成功")
            return True
            
        except Exception as e:
            logger.error("登出失败", error=str(e))
            return False
    
    async def is_authenticated(self) -> bool:
        """检查认证状态"""
        # 检查令牌是否过期
        if self._token_expires_at and datetime.utcnow() >= self._token_expires_at:
            self._authenticated = False
        
        return self._authenticated
    
    # ========================================================================
    # 健康检查
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def health_check(self) -> HealthStatus:
        """服务健康检查"""
        try:
            response = await self._make_request("GET", "/health")
            return HealthStatus(**response)
        except Exception as e:
            logger.error("健康检查失败", error=str(e))
            return HealthStatus(
                status="down",
                health="unhealthy",
                timestamp=datetime.utcnow()
            )
    
    @handle_errors(reraise=False)
    async def detailed_health_check(self) -> Dict[str, Any]:
        """详细健康检查"""
        try:
            return await self._make_request("GET", "/health/detailed")
        except Exception as e:
            logger.error("详细健康检查失败", error=str(e))
            return {"status": "error", "message": str(e)}
    
    # ========================================================================
    # 数据操作方法
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def add_data(self, request: AddDataRequest) -> AddDataResponse:
        """添加数据到数据集"""
        logger.info("添加数据", data_count=len(request.data), dataset_name=request.dataset_name)
        
        response = await self._make_request("POST", "/api/v1/add", data=request.dict())
        return AddDataResponse(**response)
    
    @handle_errors(reraise=False)
    async def add_text(self, text: str, dataset_name: str = "main_dataset") -> AddDataResponse:
        """添加文本数据"""
        request = AddDataRequest(data=[text], dataset_name=dataset_name)
        return await self.add_data(request)
    
    @handle_errors(reraise=False)
    async def add_files(self, files: List[str], dataset_name: str = "main_dataset") -> AddDataResponse:
        """添加文件数据"""
        request = AddDataRequest(data=files, dataset_name=dataset_name)
        return await self.add_data(request)
    
    # ========================================================================
    # 知识图谱构建方法
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def cognify(self, request: CognifyRequest) -> CognifyResponse:
        """构建知识图谱"""
        logger.info("开始知识图谱构建", datasets=request.datasets, background=request.run_in_background)
        
        response = await self._make_request("POST", "/api/v1/cognify", data=request.dict())
        return CognifyResponse(**response)
    
    @handle_errors(reraise=False)
    async def cognify_datasets(
        self, 
        datasets: Optional[List[str]] = None,
        dataset_ids: Optional[List[str]] = None,
        run_in_background: bool = False
    ) -> CognifyResponse:
        """构建指定数据集的知识图谱"""
        request = CognifyRequest(
            datasets=datasets,
            dataset_ids=dataset_ids,
            run_in_background=run_in_background
        )
        return await self.cognify(request)
    
    # ========================================================================
    # 搜索方法
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def search(self, request: SearchRequest) -> SearchResponse:
        """语义搜索"""
        logger.info("执行搜索", query=request.query[:50], search_type=request.search_type)
        
        response = await self._make_request("POST", "/api/v1/search", data=request.dict())
        return SearchResponse(**response)
    
    @handle_errors(reraise=False)
    async def simple_search(
        self, 
        query: str, 
        limit: int = 10, 
        dataset_ids: Optional[List[str]] = None
    ) -> SearchResponse:
        """简单搜索"""
        request = SearchRequest(
            query=query,
            limit=limit,
            dataset_ids=dataset_ids
        )
        return await self.search(request)
    
    # ========================================================================
    # 数据集管理方法
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def list_datasets(self) -> DatasetList:
        """获取数据集列表"""
        response = await self._make_request("GET", "/api/v1/datasets")
        return DatasetList(**response)
    
    @handle_errors(reraise=False)
    async def get_dataset(self, dataset_id: str) -> Dataset:
        """获取单个数据集信息"""
        response = await self._make_request("GET", f"/api/v1/datasets/{dataset_id}")
        return Dataset(**response)
    
    @handle_errors(reraise=False)
    async def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集"""
        try:
            await self._make_request("DELETE", f"/api/v1/datasets/{dataset_id}")
            logger.info("数据集删除成功", dataset_id=dataset_id)
            return True
        except Exception as e:
            logger.error("数据集删除失败", dataset_id=dataset_id, error=str(e))
            return False
    
    # ========================================================================
    # 图数据库方法
    # ========================================================================
    
    @handle_errors(reraise=False)
    async def get_graph_stats(self, dataset_id: Optional[str] = None) -> GraphStats:
        """获取图统计信息"""
        endpoint = "/api/v1/datasets/graph/stats"
        params = {"dataset_id": dataset_id} if dataset_id else None
        
        response = await self._make_request("GET", endpoint, params=params)
        return GraphStats(**response)
    
    @handle_errors(reraise=False)
    async def get_graph_labels(self, dataset_id: Optional[str] = None, limit: int = 50) -> List[str]:
        """获取图标签列表"""
        endpoint = f"/api/v1/datasets/{dataset_id}/graph/labels" if dataset_id else "/api/v1/graph/labels"
        params = {"limit": limit}
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("labels", [])
    
    @handle_errors(reraise=False)
    async def query_graph(self, cypher: str, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """执行图查询"""
        if dataset_id:
            endpoint = f"/api/v1/datasets/{dataset_id}/graph"
            data = {"cypher": cypher}
        else:
            endpoint = "/api/v1/graph/query"
            data = {"cypher": cypher}
        
        return await self._make_request("POST", endpoint, data=data)
    
    # ========================================================================
    # 高级功能方法 (四大模块)
    # ========================================================================
    
    # 本体支持
    @handle_errors(reraise=False)
    async def attach_ontology(self, dataset_id: str, ontology_path: str) -> Dict[str, Any]:
        """附加本体文件"""
        endpoint = f"/api/v1/datasets/{dataset_id}/ontology/attach"
        data = {"ontology_path": ontology_path}
        return await self._make_request("POST", endpoint, data=data)
    
    @handle_errors(reraise=False)
    async def expand_ontology(
        self, 
        dataset_id: str, 
        term: str, 
        node_type: str = "individuals",
        directed: bool = True,
        persist: bool = False
    ) -> Dict[str, Any]:
        """扩展本体"""
        endpoint = f"/api/v1/datasets/{dataset_id}/ontology/expand"
        data = {
            "term": term,
            "node_type": node_type,
            "directed": directed,
            "persist": persist
        }
        return await self._make_request("POST", endpoint, data=data)
    
    # 异步记忆
    @handle_errors(reraise=False)
    async def append_memory(self, dataset_id: str, role: str, content: str) -> Dict[str, Any]:
        """追加记忆项"""
        endpoint = f"/api/v1/datasets/{dataset_id}/memory/append"
        data = {"role": role, "content": content}
        return await self._make_request("POST", endpoint, data=data)
    
    @handle_errors(reraise=False)
    async def get_memory(self, dataset_id: str) -> List[Dict[str, Any]]:
        """获取记忆列表"""
        endpoint = f"/api/v1/datasets/{dataset_id}/memory"
        response = await self._make_request("GET", endpoint)
        return response.get("memories", [])
    
    @handle_errors(reraise=False)
    async def clear_memory(self, dataset_id: str) -> bool:
        """清空记忆"""
        endpoint = f"/api/v1/datasets/{dataset_id}/memory/clear"
        try:
            await self._make_request("POST", endpoint)
            return True
        except Exception:
            return False
    
    # 自我改进记忆
    @handle_errors(reraise=False)
    async def submit_feedback(
        self, 
        dataset_id: str, 
        memory_index: int, 
        score: float, 
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """提交记忆反馈"""
        endpoint = f"/api/v1/datasets/{dataset_id}/memory/feedback"
        data = {
            "memory_index": memory_index,
            "score": score,
            "note": note
        }
        return await self._make_request("POST", endpoint, data=data)
    
    # 时序感知
    @handle_errors(reraise=False)
    async def get_temporal_metrics(self, dataset_id: str) -> Dict[str, Any]:
        """获取时序指标"""
        endpoint = f"/api/v1/datasets/{dataset_id}/graph/metrics/time"
        return await self._make_request("GET", endpoint)
    
    # ========================================================================
    # 工具方法
    # ========================================================================
    
    async def ensure_authentication(self) -> bool:
        """确保认证状态"""
        if await self.is_authenticated():
            return True
        
        # 尝试使用API密钥
        if self.settings.api.api_key:
            try:
                await self.health_check()
                self._authenticated = True
                return True
            except AuthenticationError:
                pass
        
        # 尝试登录
        if self.settings.api.api_email and self.settings.api.api_password:
            try:
                await self.login()
                return True
            except AuthenticationError:
                pass
        
        raise AuthenticationError("无法建立认证，请检查API密钥或登录凭据")


# ============================================================================
# 工厂函数
# ============================================================================

def create_api_client(settings: Optional[Any] = None) -> CogneeAPIClient:
    """创建API客户端实例"""
    return CogneeAPIClient(settings)


async def get_authenticated_client(settings: Optional[Any] = None) -> CogneeAPIClient:
    """获取已认证的API客户端"""
    client = CogneeAPIClient(settings)
    await client.ensure_authentication()
    return client