"""
多层认证管理器
支持API密钥、JWT Token、Cookie等多种认证方式
"""

import asyncio
import jwt
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import secrets
from config.settings import get_settings
from core.error_handler import AuthenticationError, AuthorizationError, handle_errors
from core.api_client import CogneeAPIClient
import structlog


logger = structlog.get_logger(__name__)


class AuthMethod(str, Enum):
    """认证方法枚举"""
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    EMAIL_PASSWORD = "email_password"
    COOKIE = "cookie"


@dataclass
class AuthToken:
    """认证令牌数据类"""
    token: str
    token_type: str
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None
    permissions: List[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
    
    def is_expired(self) -> bool:
        """检查令牌是否过期"""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at
    
    def expires_in_seconds(self) -> Optional[int]:
        """获取令牌剩余有效时间(秒)"""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions


@dataclass
class UserSession:
    """用户会话数据类"""
    user_id: str
    email: Optional[str] = None
    roles: List[str] = None
    tenants: List[str] = None
    session_id: Optional[str] = None
    created_at: datetime = None
    last_activity: datetime = None
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.tenants is None:
            self.tenants = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.last_activity is None:
            self.last_activity = datetime.utcnow()
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.utcnow()
    
    def has_role(self, role: str) -> bool:
        """检查是否有指定角色"""
        return role in self.roles
    
    def has_tenant_access(self, tenant: str) -> bool:
        """检查是否有租户访问权限"""
        return tenant in self.tenants


class AuthenticationManager:
    """认证管理器"""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        
        # 认证状态
        self._current_token: Optional[AuthToken] = None
        self._current_session: Optional[UserSession] = None
        self._auth_method: Optional[AuthMethod] = None
        
        # API客户端
        self._api_client: Optional[CogneeAPIClient] = None
        
        # 令牌缓存
        self._token_cache: Dict[str, AuthToken] = {}
        
        # 会话管理
        self._active_sessions: Dict[str, UserSession] = {}
        self._session_timeout = timedelta(hours=24)
        
        logger.info("认证管理器初始化")
    
    # ========================================================================
    # 公共认证接口
    # ========================================================================
    
    @handle_errors(reraise=True)
    async def authenticate(self, force_refresh: bool = False) -> AuthToken:
        """主认证方法，自动选择最佳认证方式"""
        
        # 如果已认证且未过期，直接返回
        if not force_refresh and self._current_token and not self._current_token.is_expired():
            return self._current_token
        
        # 尝试不同认证方式
        auth_methods = [
            (AuthMethod.API_KEY, self._authenticate_with_api_key),
            (AuthMethod.JWT_TOKEN, self._authenticate_with_jwt),
            (AuthMethod.EMAIL_PASSWORD, self._authenticate_with_credentials),
        ]
        
        last_error = None
        for method, auth_func in auth_methods:
            try:
                token = await auth_func()
                if token:
                    self._current_token = token
                    self._auth_method = method
                    logger.info("认证成功", method=method.value)
                    return token
            except Exception as e:
                last_error = e
                logger.debug("认证方法失败", method=method.value, error=str(e))
        
        # 所有认证方法都失败
        raise AuthenticationError(f"所有认证方法都失败: {str(last_error)}")
    
    @handle_errors(reraise=True)
    async def refresh_authentication(self) -> AuthToken:
        """刷新认证"""
        if not self._current_token:
            raise AuthenticationError("没有当前认证令牌")
        
        # 尝试刷新令牌
        try:
            if self._auth_method == AuthMethod.JWT_TOKEN:
                return await self._refresh_jwt_token()
            elif self._auth_method == AuthMethod.EMAIL_PASSWORD:
                return await self._authenticate_with_credentials()
            else:
                # API密钥不需要刷新，重新验证即可
                return await self._authenticate_with_api_key()
        except Exception as e:
            logger.error("令牌刷新失败", error=str(e))
            # 刷新失败，清除当前认证状态
            await self.logout()
            raise AuthenticationError(f"令牌刷新失败: {str(e)}")
    
    async def logout(self) -> None:
        """登出"""
        try:
            # 如果有API客户端，执行远程登出
            if self._api_client:
                await self._api_client.logout()
        except Exception as e:
            logger.warning("远程登出失败", error=str(e))
        
        # 清除本地认证状态
        self._current_token = None
        self._current_session = None
        self._auth_method = None
        
        # 关闭API客户端
        if self._api_client:
            await self._api_client.close()
            self._api_client = None
        
        logger.info("登出完成")
    
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return (
            self._current_token is not None and 
            not self._current_token.is_expired()
        )
    
    def get_current_token(self) -> Optional[AuthToken]:
        """获取当前认证令牌"""
        if self._current_token and self._current_token.is_expired():
            return None
        return self._current_token
    
    def get_current_session(self) -> Optional[UserSession]:
        """获取当前用户会话"""
        return self._current_session
    
    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证请求头"""
        headers = {}
        
        if self._current_token:
            if self._auth_method == AuthMethod.API_KEY:
                if self.settings.api.api_key_header.lower() == 'authorization':
                    scheme = self.settings.api.api_key_scheme
                    headers['Authorization'] = f"{scheme} {self._current_token.token}".strip()
                else:
                    headers[self.settings.api.api_key_header] = self._current_token.token
            
            elif self._auth_method == AuthMethod.JWT_TOKEN:
                headers['Authorization'] = f"Bearer {self._current_token.token}"
        
        return headers
    
    # ========================================================================
    # 权限管理
    # ========================================================================
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        if not self.is_authenticated():
            return False
        
        return self._current_token.has_permission(permission)
    
    def require_permission(self, permission: str) -> None:
        """要求指定权限，无权限时抛出异常"""
        if not self.has_permission(permission):
            raise AuthorizationError(f"缺少权限: {permission}")
    
    def has_role(self, role: str) -> bool:
        """检查是否有指定角色"""
        if not self._current_session:
            return False
        
        return self._current_session.has_role(role)
    
    def require_role(self, role: str) -> None:
        """要求指定角色，无角色时抛出异常"""
        if not self.has_role(role):
            raise AuthorizationError(f"缺少角色: {role}")
    
    # ========================================================================
    # 具体认证方法实现
    # ========================================================================
    
    async def _authenticate_with_api_key(self) -> Optional[AuthToken]:
        """API密钥认证"""
        api_key = self.settings.api.api_key
        if not api_key:
            return None
        
        # 验证API密钥有效性
        await self._ensure_api_client()
        try:
            health = await self._api_client.health_check()
            if health.status == "ready":
                return AuthToken(
                    token=api_key,
                    token_type="api_key",
                    permissions=["*"]  # API密钥通常有全部权限
                )
        except Exception as e:
            logger.debug("API密钥验证失败", error=str(e))
            return None
    
    async def _authenticate_with_jwt(self) -> Optional[AuthToken]:
        """JWT令牌认证"""
        jwt_token = self.settings.api.api_key if self.settings.api.api_key_scheme.lower() == "bearer" else None
        if not jwt_token:
            return None
        
        try:
            # 解析JWT令牌 (不验证签名，只检查结构)
            payload = jwt.decode(jwt_token, options={"verify_signature": False})
            
            expires_at = None
            if 'exp' in payload:
                expires_at = datetime.fromtimestamp(payload['exp'])
                if expires_at <= datetime.utcnow():
                    logger.debug("JWT令牌已过期")
                    return None
            
            user_id = payload.get('sub')
            permissions = payload.get('permissions', [])
            
            # 验证令牌有效性
            await self._ensure_api_client()
            health = await self._api_client.health_check()
            if health.status == "ready":
                return AuthToken(
                    token=jwt_token,
                    token_type="bearer",
                    expires_at=expires_at,
                    user_id=user_id,
                    permissions=permissions
                )
        
        except jwt.InvalidTokenError as e:
            logger.debug("JWT令牌无效", error=str(e))
            return None
        except Exception as e:
            logger.debug("JWT认证失败", error=str(e))
            return None
    
    async def _authenticate_with_credentials(self) -> Optional[AuthToken]:
        """用户名密码认证"""
        email = self.settings.api.api_email
        password = self.settings.api.api_password
        
        if not email or not password:
            return None
        
        try:
            await self._ensure_api_client()
            login_result = await self._api_client.login(email, password)
            
            expires_at = None
            if login_result.expires_in:
                expires_at = datetime.utcnow() + timedelta(seconds=login_result.expires_in)
            
            # 创建用户会话
            self._current_session = UserSession(
                user_id=login_result.user_id or email,
                email=email,
                session_id=self._generate_session_id()
            )
            
            return AuthToken(
                token=login_result.access_token,
                token_type=login_result.token_type,
                expires_at=expires_at,
                user_id=login_result.user_id,
                permissions=[]  # 权限需要单独获取
            )
        
        except Exception as e:
            logger.debug("凭据认证失败", error=str(e))
            return None
    
    async def _refresh_jwt_token(self) -> AuthToken:
        """刷新JWT令牌"""
        if not self._current_token:
            raise AuthenticationError("没有当前令牌")
        
        # 尝试使用刷新令牌API (如果存在)
        try:
            await self._ensure_api_client()
            # 注意: 这里假设有刷新令牌的API，实际需要根据官方API文档调整
            # response = await self._api_client._make_request("POST", "/api/v1/auth/refresh")
            # 如果没有刷新API，回退到重新认证
            return await self._authenticate_with_credentials()
        except Exception as e:
            raise AuthenticationError(f"令牌刷新失败: {str(e)}")
    
    # ========================================================================
    # 会话管理
    # ========================================================================
    
    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return secrets.token_hex(16)
    
    def create_session(self, user_id: str, email: Optional[str] = None) -> UserSession:
        """创建用户会话"""
        session = UserSession(
            user_id=user_id,
            email=email,
            session_id=self._generate_session_id()
        )
        
        self._active_sessions[session.session_id] = session
        self._current_session = session
        
        logger.info("用户会话创建", user_id=user_id, session_id=session.session_id)
        return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """获取会话"""
        session = self._active_sessions.get(session_id)
        if session and self._is_session_valid(session):
            session.update_activity()
            return session
        return None
    
    def _is_session_valid(self, session: UserSession) -> bool:
        """检查会话是否有效"""
        if not session.last_activity:
            return False
        
        return datetime.utcnow() - session.last_activity < self._session_timeout
    
    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        expired_sessions = []
        
        for session_id, session in self._active_sessions.items():
            if not self._is_session_valid(session):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self._active_sessions[session_id]
        
        if expired_sessions:
            logger.info("清理过期会话", count=len(expired_sessions))
        
        return len(expired_sessions)
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    async def _ensure_api_client(self) -> None:
        """确保API客户端已初始化"""
        if not self._api_client:
            self._api_client = CogneeAPIClient(self.settings)
    
    def get_api_client(self) -> Optional[CogneeAPIClient]:
        """获取API客户端"""
        return self._api_client
    
    # ========================================================================
    # 认证信息管理
    # ========================================================================
    
    def cache_token(self, key: str, token: AuthToken) -> None:
        """缓存令牌"""
        self._token_cache[key] = token
    
    def get_cached_token(self, key: str) -> Optional[AuthToken]:
        """获取缓存的令牌"""
        token = self._token_cache.get(key)
        if token and not token.is_expired():
            return token
        return None
    
    def clear_token_cache(self) -> None:
        """清空令牌缓存"""
        self._token_cache.clear()
    
    # ========================================================================
    # 状态信息
    # ========================================================================
    
    def get_auth_status(self) -> Dict[str, Any]:
        """获取认证状态信息"""
        return {
            "authenticated": self.is_authenticated(),
            "auth_method": self._auth_method.value if self._auth_method else None,
            "user_id": self._current_token.user_id if self._current_token else None,
            "token_expires_in": self._current_token.expires_in_seconds() if self._current_token else None,
            "session_active": self._current_session is not None,
            "permissions": self._current_token.permissions if self._current_token else [],
            "roles": self._current_session.roles if self._current_session else []
        }


# ============================================================================
# 认证装饰器
# ============================================================================

def require_authentication(auth_manager: Optional[AuthenticationManager] = None):
    """认证装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            manager = auth_manager or AuthenticationManager()
            
            if not manager.is_authenticated():
                try:
                    await manager.authenticate()
                except AuthenticationError:
                    raise AuthenticationError("需要认证才能访问此功能")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permission(permission: str, auth_manager: Optional[AuthenticationManager] = None):
    """权限装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            manager = auth_manager or AuthenticationManager()
            manager.require_permission(permission)
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# 全局认证管理器
# ============================================================================

_global_auth_manager: Optional[AuthenticationManager] = None


def get_auth_manager() -> AuthenticationManager:
    """获取全局认证管理器"""
    global _global_auth_manager
    if _global_auth_manager is None:
        _global_auth_manager = AuthenticationManager()
    return _global_auth_manager


async def authenticate_globally() -> AuthToken:
    """全局认证"""
    manager = get_auth_manager()
    return await manager.authenticate()