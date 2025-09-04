"""
异步记忆工具模块
提供记忆管理、上下文保持、记忆检索、记忆更新等功能
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog

logger = structlog.get_logger(__name__)


class MemoryStoreTool(BaseTool):
    """记忆存储工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="memory_store",
            description="存储新的记忆条目",
            category=ToolCategory.MEMORY,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "memory_content": {
                    "type": "string",
                    "description": "记忆内容"
                },
                "memory_type": {
                    "type": "string",
                    "description": "记忆类型",
                    "enum": ["episodic", "semantic", "procedural", "context"],
                    "default": "episodic"
                },
                "importance_score": {
                    "type": "number",
                    "description": "重要性分数 (0-1)",
                    "default": 0.5
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "记忆标签"
                },
                "context_id": {
                    "type": "string",
                    "description": "上下文ID（可选）"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "retention_days": {
                    "type": "number",
                    "description": "记忆保持天数",
                    "default": 30
                }
            },
            required=["memory_content"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        memory_content = arguments.get("memory_content", "").strip()
        memory_type = arguments.get("memory_type", "episodic")
        importance_score = arguments.get("importance_score", 0.5)
        tags = arguments.get("tags", [])
        context_id = arguments.get("context_id")
        dataset_id = arguments.get("dataset_id")
        retention_days = arguments.get("retention_days", 30)
        
        if not memory_content:
            raise ToolExecutionError(self.metadata.name, "记忆内容不能为空")
        
        logger.info("存储记忆", memory_type=memory_type, importance=importance_score, content_length=len(memory_content))
        
        try:
            # 计算过期时间
            expires_at = datetime.now() + timedelta(days=retention_days)
            memory_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # 构建存储记忆的Cypher查询
            store_query = """
            CREATE (m:Memory {
                id: $memory_id,
                content: $content,
                type: $memory_type,
                importance: $importance_score,
                context_id: $context_id,
                created_at: datetime(),
                expires_at: datetime($expires_at),
                access_count: 0,
                last_accessed: datetime()
            })
            """
            
            # 添加标签
            if tags:
                tag_query = """
                WITH m
                UNWIND $tags as tag_name
                MERGE (t:Tag {name: tag_name})
                CREATE (m)-[:TAGGED_WITH]->(t)
                """
                store_query += tag_query
            
            store_query += " RETURN m.id as memory_id"
            
            async with get_authenticated_client() as client:
                result = await client.query_graph(
                    store_query, 
                    dataset_id,
                    parameters={
                        "memory_id": memory_id,
                        "content": memory_content,
                        "memory_type": memory_type,
                        "importance_score": importance_score,
                        "context_id": context_id,
                        "expires_at": expires_at.isoformat(),
                        "tags": tags
                    }
                )
                
                return {
                    "success": True,
                    "message": "记忆存储成功",
                    "memory_id": memory_id,
                    "memory_type": memory_type,
                    "importance_score": importance_score,
                    "tags": tags,
                    "expires_at": expires_at.isoformat(),
                    "retention_days": retention_days
                }
        
        except Exception as e:
            logger.error("记忆存储失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"记忆存储失败: {str(e)}")


class MemoryRetrieveTool(BaseTool):
    """记忆检索工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="memory_retrieve",
            description="检索相关记忆",
            category=ToolCategory.MEMORY,
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
                    "description": "记忆检索查询"
                },
                "memory_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "记忆类型过滤",
                    "default": []
                },
                "context_id": {
                    "type": "string",
                    "description": "上下文ID过滤"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "limit": {
                    "type": "number",
                    "description": "返回结果数量",
                    "default": 10
                },
                "min_importance": {
                    "type": "number",
                    "description": "最低重要性分数",
                    "default": 0.0
                },
                "include_expired": {
                    "type": "boolean",
                    "description": "是否包含过期记忆",
                    "default": False
                }
            },
            required=["query"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = arguments.get("query", "").strip()
        memory_types = arguments.get("memory_types", [])
        context_id = arguments.get("context_id")
        dataset_id = arguments.get("dataset_id")
        limit = arguments.get("limit", 10)
        min_importance = arguments.get("min_importance", 0.0)
        include_expired = arguments.get("include_expired", False)
        
        if not query:
            raise ToolExecutionError(self.metadata.name, "检索查询不能为空")
        
        logger.info("检索记忆", query=query[:50], memory_types=memory_types, limit=limit)
        
        try:
            # 构建记忆检索查询
            cypher_query = """
            MATCH (m:Memory)
            WHERE m.content CONTAINS $query
            AND m.importance >= $min_importance
            """
            
            # 添加类型过滤
            if memory_types:
                cypher_query += " AND m.type IN $memory_types"
            
            # 添加上下文过滤
            if context_id:
                cypher_query += " AND m.context_id = $context_id"
            
            # 添加过期过滤
            if not include_expired:
                cypher_query += " AND (m.expires_at IS NULL OR m.expires_at > datetime())"
            
            # 添加标签匹配
            cypher_query += """
            OPTIONAL MATCH (m)-[:TAGGED_WITH]->(tag:Tag)
            WITH m, collect(tag.name) as tags,
                 CASE 
                   WHEN m.content CONTAINS $query THEN 1.0
                   ELSE 0.5
                 END as relevance_score
            """
            
            cypher_query += """
            SET m.access_count = m.access_count + 1,
                m.last_accessed = datetime()
            RETURN m.id as memory_id,
                   m.content as content,
                   m.type as memory_type,
                   m.importance as importance,
                   m.context_id as context_id,
                   m.created_at as created_at,
                   m.expires_at as expires_at,
                   m.access_count as access_count,
                   tags,
                   relevance_score
            ORDER BY m.importance DESC, relevance_score DESC, m.created_at DESC
            LIMIT $limit
            """
            
            async with get_authenticated_client() as client:
                result = await client.query_graph(
                    cypher_query,
                    dataset_id,
                    parameters={
                        "query": query,
                        "memory_types": memory_types,
                        "context_id": context_id,
                        "min_importance": min_importance,
                        "limit": limit
                    }
                )
                
                memories = []
                if result and 'result_set' in result:
                    for row in result['result_set']:
                        if len(row) >= 10:
                            memories.append({
                                "memory_id": row[0],
                                "content": row[1],
                                "memory_type": row[2],
                                "importance": float(row[3]),
                                "context_id": row[4],
                                "created_at": row[5],
                                "expires_at": row[6],
                                "access_count": int(row[7]),
                                "tags": row[8] if row[8] else [],
                                "relevance_score": float(row[9])
                            })
                
                return {
                    "success": True,
                    "query": query,
                    "memories": memories,
                    "total_found": len(memories),
                    "filters": {
                        "memory_types": memory_types,
                        "context_id": context_id,
                        "min_importance": min_importance,
                        "include_expired": include_expired
                    }
                }
        
        except Exception as e:
            logger.error("记忆检索失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"记忆检索失败: {str(e)}")


class MemoryUpdateTool(BaseTool):
    """记忆更新工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="memory_update",
            description="更新现有记忆",
            category=ToolCategory.MEMORY,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "memory_id": {
                    "type": "string",
                    "description": "记忆ID"
                },
                "new_content": {
                    "type": "string",
                    "description": "新的记忆内容（可选）"
                },
                "importance_adjustment": {
                    "type": "number",
                    "description": "重要性调整值（±）"
                },
                "add_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "添加的标签"
                },
                "remove_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "移除的标签"
                },
                "extend_retention": {
                    "type": "number",
                    "description": "延长保持天数"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                }
            },
            required=["memory_id"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        memory_id = arguments.get("memory_id", "").strip()
        new_content = arguments.get("new_content")
        importance_adjustment = arguments.get("importance_adjustment", 0)
        add_tags = arguments.get("add_tags", [])
        remove_tags = arguments.get("remove_tags", [])
        extend_retention = arguments.get("extend_retention", 0)
        dataset_id = arguments.get("dataset_id")
        
        if not memory_id:
            raise ToolExecutionError(self.metadata.name, "记忆ID不能为空")
        
        logger.info("更新记忆", memory_id=memory_id, has_new_content=bool(new_content))
        
        try:
            # 构建更新查询
            update_parts = []
            parameters = {"memory_id": memory_id}
            
            # 更新内容
            if new_content:
                update_parts.append("m.content = $new_content")
                parameters["new_content"] = new_content
            
            # 调整重要性
            if importance_adjustment != 0:
                update_parts.append("m.importance = CASE WHEN m.importance + $importance_adjustment > 1.0 THEN 1.0 WHEN m.importance + $importance_adjustment < 0.0 THEN 0.0 ELSE m.importance + $importance_adjustment END")
                parameters["importance_adjustment"] = importance_adjustment
            
            # 延长保持期
            if extend_retention > 0:
                update_parts.append("m.expires_at = datetime() + duration({days: $extend_retention})")
                parameters["extend_retention"] = extend_retention
            
            # 更新最后修改时间
            update_parts.append("m.last_modified = datetime()")
            
            cypher_query = f"""
            MATCH (m:Memory {{id: $memory_id}})
            SET {', '.join(update_parts)}
            """
            
            # 添加标签
            if add_tags:
                cypher_query += """
                WITH m
                UNWIND $add_tags as tag_name
                MERGE (t:Tag {name: tag_name})
                MERGE (m)-[:TAGGED_WITH]->(t)
                """
                parameters["add_tags"] = add_tags
            
            # 移除标签
            if remove_tags:
                cypher_query += """
                WITH m
                UNWIND $remove_tags as tag_name
                MATCH (m)-[r:TAGGED_WITH]->(t:Tag {name: tag_name})
                DELETE r
                """
                parameters["remove_tags"] = remove_tags
            
            cypher_query += """
            WITH m
            OPTIONAL MATCH (m)-[:TAGGED_WITH]->(tag:Tag)
            RETURN m.id as memory_id,
                   m.content as content,
                   m.importance as importance,
                   m.expires_at as expires_at,
                   m.last_modified as last_modified,
                   collect(tag.name) as tags
            """
            
            async with get_authenticated_client() as client:
                result = await client.query_graph(cypher_query, dataset_id, parameters=parameters)
                
                if result and 'result_set' in result and result['result_set']:
                    row = result['result_set'][0]
                    updated_memory = {
                        "memory_id": row[0],
                        "content": row[1],
                        "importance": float(row[2]),
                        "expires_at": row[3],
                        "last_modified": row[4],
                        "tags": row[5] if row[5] else []
                    }
                    
                    return {
                        "success": True,
                        "message": "记忆更新成功",
                        "updated_memory": updated_memory,
                        "changes": {
                            "content_updated": bool(new_content),
                            "importance_adjusted": importance_adjustment,
                            "tags_added": len(add_tags),
                            "tags_removed": len(remove_tags),
                            "retention_extended": extend_retention
                        }
                    }
                else:
                    raise ToolExecutionError(self.metadata.name, f"未找到记忆 {memory_id}")
        
        except Exception as e:
            logger.error("记忆更新失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"记忆更新失败: {str(e)}")


class ContextManagerTool(BaseTool):
    """上下文管理工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="context_manager",
            description="管理对话上下文和记忆关联",
            category=ToolCategory.MEMORY,
            requires_auth=True,
            timeout=30.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "action": {
                    "type": "string",
                    "description": "操作类型",
                    "enum": ["create", "update", "get", "close", "list"],
                    "default": "create"
                },
                "context_id": {
                    "type": "string",
                    "description": "上下文ID（create时自动生成）"
                },
                "context_name": {
                    "type": "string",
                    "description": "上下文名称"
                },
                "context_type": {
                    "type": "string",
                    "description": "上下文类型",
                    "enum": ["conversation", "task", "session", "project"],
                    "default": "conversation"
                },
                "metadata": {
                    "type": "object",
                    "description": "上下文元数据"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                }
            },
            required=["action"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        action = arguments.get("action", "create")
        context_id = arguments.get("context_id")
        context_name = arguments.get("context_name", "")
        context_type = arguments.get("context_type", "conversation")
        metadata = arguments.get("metadata", {})
        dataset_id = arguments.get("dataset_id")
        
        logger.info("管理上下文", action=action, context_id=context_id, context_type=context_type)
        
        try:
            async with get_authenticated_client() as client:
                if action == "create":
                    return await self._create_context(client, dataset_id, context_name, context_type, metadata)
                elif action == "update":
                    return await self._update_context(client, dataset_id, context_id, context_name, metadata)
                elif action == "get":
                    return await self._get_context(client, dataset_id, context_id)
                elif action == "close":
                    return await self._close_context(client, dataset_id, context_id)
                else:  # list
                    return await self._list_contexts(client, dataset_id, context_type)
        
        except Exception as e:
            logger.error("上下文管理失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"上下文管理失败: {str(e)}")
    
    async def _create_context(self, client, dataset_id, name, context_type, metadata):
        """创建新上下文"""
        context_id = f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        query = """
        CREATE (c:Context {
            id: $context_id,
            name: $name,
            type: $context_type,
            created_at: datetime(),
            updated_at: datetime(),
            is_active: true,
            memory_count: 0
        })
        """
        
        # 添加元数据
        if metadata:
            for key, value in metadata.items():
                query += f" SET c.{key} = $metadata_{key}"
        
        query += " RETURN c.id as context_id, c.created_at as created_at"
        
        parameters = {
            "context_id": context_id,
            "name": name,
            "context_type": context_type
        }
        
        for key, value in metadata.items():
            parameters[f"metadata_{key}"] = value
        
        result = await client.query_graph(query, dataset_id, parameters=parameters)
        
        return {
            "success": True,
            "message": "上下文创建成功",
            "context_id": context_id,
            "context_name": name,
            "context_type": context_type,
            "metadata": metadata,
            "created_at": result['result_set'][0][1] if result and 'result_set' in result and result['result_set'] else None
        }
    
    async def _update_context(self, client, dataset_id, context_id, name, metadata):
        """更新上下文"""
        if not context_id:
            raise ToolExecutionError(self.metadata.name, "上下文ID不能为空")
        
        update_parts = ["c.updated_at = datetime()"]
        parameters = {"context_id": context_id}
        
        if name:
            update_parts.append("c.name = $name")
            parameters["name"] = name
        
        # 更新元数据
        if metadata:
            for key, value in metadata.items():
                update_parts.append(f"c.{key} = $metadata_{key}")
                parameters[f"metadata_{key}"] = value
        
        query = f"""
        MATCH (c:Context {{id: $context_id}})
        SET {', '.join(update_parts)}
        RETURN c.id as context_id, c.updated_at as updated_at
        """
        
        result = await client.query_graph(query, dataset_id, parameters=parameters)
        
        if result and 'result_set' in result and result['result_set']:
            return {
                "success": True,
                "message": "上下文更新成功",
                "context_id": context_id,
                "updated_at": result['result_set'][0][1]
            }
        else:
            raise ToolExecutionError(self.metadata.name, f"未找到上下文 {context_id}")
    
    async def _get_context(self, client, dataset_id, context_id):
        """获取上下文信息"""
        if not context_id:
            raise ToolExecutionError(self.metadata.name, "上下文ID不能为空")
        
        query = """
        MATCH (c:Context {id: $context_id})
        OPTIONAL MATCH (c)<-[:IN_CONTEXT]-(m:Memory)
        RETURN c.id as context_id,
               c.name as context_name,
               c.type as context_type,
               c.created_at as created_at,
               c.updated_at as updated_at,
               c.is_active as is_active,
               count(m) as memory_count
        """
        
        result = await client.query_graph(query, dataset_id, parameters={"context_id": context_id})
        
        if result and 'result_set' in result and result['result_set']:
            row = result['result_set'][0]
            return {
                "success": True,
                "context": {
                    "context_id": row[0],
                    "context_name": row[1],
                    "context_type": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "is_active": row[5],
                    "memory_count": int(row[6])
                }
            }
        else:
            raise ToolExecutionError(self.metadata.name, f"未找到上下文 {context_id}")
    
    async def _close_context(self, client, dataset_id, context_id):
        """关闭上下文"""
        if not context_id:
            raise ToolExecutionError(self.metadata.name, "上下文ID不能为空")
        
        query = """
        MATCH (c:Context {id: $context_id})
        SET c.is_active = false, c.closed_at = datetime()
        RETURN c.id as context_id, c.closed_at as closed_at
        """
        
        result = await client.query_graph(query, dataset_id, parameters={"context_id": context_id})
        
        if result and 'result_set' in result and result['result_set']:
            return {
                "success": True,
                "message": "上下文已关闭",
                "context_id": context_id,
                "closed_at": result['result_set'][0][1]
            }
        else:
            raise ToolExecutionError(self.metadata.name, f"未找到上下文 {context_id}")
    
    async def _list_contexts(self, client, dataset_id, context_type=None):
        """列出上下文"""
        query = "MATCH (c:Context)"
        
        parameters = {}
        if context_type:
            query += " WHERE c.type = $context_type"
            parameters["context_type"] = context_type
        
        query += """
        OPTIONAL MATCH (c)<-[:IN_CONTEXT]-(m:Memory)
        RETURN c.id as context_id,
               c.name as context_name,
               c.type as context_type,
               c.created_at as created_at,
               c.is_active as is_active,
               count(m) as memory_count
        ORDER BY c.created_at DESC
        LIMIT 20
        """
        
        result = await client.query_graph(query, dataset_id, parameters=parameters)
        
        contexts = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 6:
                    contexts.append({
                        "context_id": row[0],
                        "context_name": row[1],
                        "context_type": row[2],
                        "created_at": row[3],
                        "is_active": row[4],
                        "memory_count": int(row[5])
                    })
        
        return {
            "success": True,
            "contexts": contexts,
            "total_count": len(contexts),
            "filter": {"context_type": context_type} if context_type else None
        }


class MemoryConsolidationTool(BaseTool):
    """记忆整合工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="memory_consolidation",
            description="整合和优化记忆存储",
            category=ToolCategory.MEMORY,
            requires_auth=True,
            timeout=120.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "consolidation_type": {
                    "type": "string",
                    "description": "整合类型",
                    "enum": ["expired_cleanup", "duplicate_merge", "importance_rebalance", "context_clustering"],
                    "default": "expired_cleanup"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "是否只是预览而不实际执行",
                    "default": False
                },
                "batch_size": {
                    "type": "number",
                    "description": "批处理大小",
                    "default": 100
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        consolidation_type = arguments.get("consolidation_type", "expired_cleanup")
        dataset_id = arguments.get("dataset_id")
        dry_run = arguments.get("dry_run", False)
        batch_size = arguments.get("batch_size", 100)
        
        logger.info("执行记忆整合", consolidation_type=consolidation_type, dry_run=dry_run)
        
        try:
            async with get_authenticated_client() as client:
                if consolidation_type == "expired_cleanup":
                    result = await self._cleanup_expired_memories(client, dataset_id, dry_run, batch_size)
                elif consolidation_type == "duplicate_merge":
                    result = await self._merge_duplicate_memories(client, dataset_id, dry_run, batch_size)
                elif consolidation_type == "importance_rebalance":
                    result = await self._rebalance_importance(client, dataset_id, dry_run, batch_size)
                else:  # context_clustering
                    result = await self._cluster_by_context(client, dataset_id, dry_run, batch_size)
                
                return {
                    "success": True,
                    "message": f"{consolidation_type} 整合{'预览' if dry_run else '执行'}完成",
                    "consolidation_type": consolidation_type,
                    "dry_run": dry_run,
                    **result
                }
        
        except Exception as e:
            logger.error("记忆整合失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"记忆整合失败: {str(e)}")
    
    async def _cleanup_expired_memories(self, client, dataset_id, dry_run, batch_size):
        """清理过期记忆"""
        # 查找过期记忆
        find_query = """
        MATCH (m:Memory)
        WHERE m.expires_at < datetime()
        RETURN m.id as memory_id, m.content as content, m.expires_at as expires_at
        LIMIT $batch_size
        """
        
        result = await client.query_graph(find_query, dataset_id, parameters={"batch_size": batch_size})
        
        expired_memories = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    expired_memories.append({
                        "memory_id": row[0],
                        "content": row[1],
                        "expires_at": row[2]
                    })
        
        if not dry_run and expired_memories:
            # 删除过期记忆
            delete_ids = [m["memory_id"] for m in expired_memories]
            delete_query = """
            MATCH (m:Memory)
            WHERE m.id IN $delete_ids
            DETACH DELETE m
            """
            
            await client.query_graph(delete_query, dataset_id, parameters={"delete_ids": delete_ids})
        
        return {
            "expired_memories": expired_memories,
            "total_expired": len(expired_memories),
            "deleted": len(expired_memories) if not dry_run else 0
        }
    
    async def _merge_duplicate_memories(self, client, dataset_id, dry_run, batch_size):
        """合并重复记忆"""
        # 查找相似内容的记忆
        find_query = """
        MATCH (m1:Memory), (m2:Memory)
        WHERE m1.id < m2.id
        AND gds.similarity.cosine(m1.content_vector, m2.content_vector) > 0.9
        RETURN m1.id as memory1_id, m2.id as memory2_id,
               m1.content as content1, m2.content as content2,
               m1.importance as importance1, m2.importance as importance2
        LIMIT $batch_size
        """
        
        # 简化版本：基于内容长度相似性
        simplified_query = """
        MATCH (m1:Memory), (m2:Memory)
        WHERE m1.id < m2.id
        AND size(m1.content) = size(m2.content)
        AND m1.content CONTAINS substring(m2.content, 0, 20)
        RETURN m1.id as memory1_id, m2.id as memory2_id,
               m1.content as content1, m2.content as content2,
               m1.importance as importance1, m2.importance as importance2
        LIMIT $batch_size
        """
        
        result = await client.query_graph(simplified_query, dataset_id, parameters={"batch_size": batch_size})
        
        duplicate_pairs = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 6:
                    duplicate_pairs.append({
                        "memory1_id": row[0],
                        "memory2_id": row[1],
                        "content1": row[2],
                        "content2": row[3],
                        "importance1": float(row[4]),
                        "importance2": float(row[5])
                    })
        
        merged_count = 0
        if not dry_run and duplicate_pairs:
            # 合并重复记忆
            for pair in duplicate_pairs:
                # 保留重要性更高的记忆，删除另一个
                if pair["importance1"] >= pair["importance2"]:
                    keep_id, delete_id = pair["memory1_id"], pair["memory2_id"]
                else:
                    keep_id, delete_id = pair["memory2_id"], pair["memory1_id"]
                
                merge_query = """
                MATCH (keep:Memory {id: $keep_id}), (delete:Memory {id: $delete_id})
                SET keep.importance = keep.importance + delete.importance * 0.1,
                    keep.access_count = keep.access_count + delete.access_count
                WITH delete
                DETACH DELETE delete
                """
                
                await client.query_graph(merge_query, dataset_id, parameters={
                    "keep_id": keep_id,
                    "delete_id": delete_id
                })
                merged_count += 1
        
        return {
            "duplicate_pairs": duplicate_pairs,
            "total_duplicates": len(duplicate_pairs),
            "merged": merged_count
        }
    
    async def _rebalance_importance(self, client, dataset_id, dry_run, batch_size):
        """重新平衡重要性分数"""
        # 计算重要性统计
        stats_query = """
        MATCH (m:Memory)
        RETURN avg(m.importance) as avg_importance,
               stdev(m.importance) as std_importance,
               min(m.importance) as min_importance,
               max(m.importance) as max_importance,
               count(m) as total_memories
        """
        
        result = await client.query_graph(stats_query, dataset_id)
        
        stats = {}
        if result and 'result_set' in result and result['result_set']:
            row = result['result_set'][0]
            stats = {
                "avg_importance": float(row[0]),
                "std_importance": float(row[1]),
                "min_importance": float(row[2]),
                "max_importance": float(row[3]),
                "total_memories": int(row[4])
            }
        
        rebalanced_count = 0
        if not dry_run and stats.get("std_importance", 0) > 0.3:  # 如果标准差过大，进行重新平衡
            # 重新平衡重要性分数
            rebalance_query = """
            MATCH (m:Memory)
            WITH m, m.importance as old_importance,
                 (m.importance - $avg_importance) / $std_importance as z_score
            SET m.importance = CASE 
                WHEN z_score > 2 THEN 0.9
                WHEN z_score < -2 THEN 0.1
                ELSE (z_score + 2) / 4
            END
            RETURN count(m) as rebalanced_count
            """
            
            rebalance_result = await client.query_graph(rebalance_query, dataset_id, parameters={
                "avg_importance": stats["avg_importance"],
                "std_importance": stats["std_importance"]
            })
            
            if rebalance_result and 'result_set' in rebalance_result and rebalance_result['result_set']:
                rebalanced_count = int(rebalance_result['result_set'][0][0])
        
        return {
            "importance_stats": stats,
            "rebalanced": rebalanced_count,
            "needs_rebalancing": stats.get("std_importance", 0) > 0.3
        }
    
    async def _cluster_by_context(self, client, dataset_id, dry_run, batch_size):
        """按上下文聚类"""
        # 查找没有上下文的记忆
        orphan_query = """
        MATCH (m:Memory)
        WHERE m.context_id IS NULL
        RETURN m.id as memory_id, m.content as content, m.created_at as created_at
        ORDER BY m.created_at DESC
        LIMIT $batch_size
        """
        
        result = await client.query_graph(orphan_query, dataset_id, parameters={"batch_size": batch_size})
        
        orphan_memories = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    orphan_memories.append({
                        "memory_id": row[0],
                        "content": row[1],
                        "created_at": row[2]
                    })
        
        clustered_count = 0
        if not dry_run and orphan_memories:
            # 为孤立记忆创建或分配上下文
            for memory in orphan_memories:
                # 简化版本：基于时间戳创建上下文
                context_id = f"auto_ctx_{memory['created_at'][:10]}"  # 按日期分组
                
                assign_query = """
                MATCH (m:Memory {id: $memory_id})
                MERGE (c:Context {id: $context_id, type: 'auto_generated', name: $context_name})
                ON CREATE SET c.created_at = datetime()
                SET m.context_id = $context_id
                MERGE (m)-[:IN_CONTEXT]->(c)
                """
                
                await client.query_graph(assign_query, dataset_id, parameters={
                    "memory_id": memory["memory_id"],
                    "context_id": context_id,
                    "context_name": f"Auto Context {context_id}"
                })
                clustered_count += 1
        
        return {
            "orphan_memories": orphan_memories,
            "total_orphans": len(orphan_memories),
            "clustered": clustered_count
        }


# 自动注册记忆工具
def register_memory_tools():
    """注册所有异步记忆工具"""
    tools = [
        MemoryStoreTool,
        MemoryRetrieveTool,
        MemoryUpdateTool,
        ContextManagerTool,
        MemoryConsolidationTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("异步记忆工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_memory_tools()