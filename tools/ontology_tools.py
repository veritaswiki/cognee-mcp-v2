"""
本体支持工具模块
提供本体映射、语义推理、概念层次、关系推理等功能
"""

from typing import Any, Dict, List, Optional
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog

logger = structlog.get_logger(__name__)


class OntologyMappingTool(BaseTool):
    """本体映射工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="ontology_mapping",
            description="将实体映射到本体概念",
            category=ToolCategory.ONTOLOGY,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要映射的实体列表"
                },
                "ontology_namespace": {
                    "type": "string",
                    "description": "本体命名空间",
                    "default": "default"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "confidence_threshold": {
                    "type": "number",
                    "description": "映射置信度阈值",
                    "default": 0.7
                },
                "max_candidates": {
                    "type": "number",
                    "description": "每个实体的最大候选概念数",
                    "default": 5
                }
            },
            required=["entities"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entities = arguments.get("entities", [])
        ontology_namespace = arguments.get("ontology_namespace", "default")
        dataset_id = arguments.get("dataset_id")
        confidence_threshold = arguments.get("confidence_threshold", 0.7)
        max_candidates = arguments.get("max_candidates", 5)
        
        if not entities:
            raise ToolExecutionError(self.metadata.name, "实体列表不能为空")
        
        logger.info("执行本体映射", entity_count=len(entities), namespace=ontology_namespace)
        
        try:
            async with get_authenticated_client() as client:
                mappings = {}
                
                for entity in entities:
                    # 为每个实体查找本体概念候选
                    candidates = await self._find_ontology_candidates(
                        client, dataset_id, entity, ontology_namespace, max_candidates
                    )
                    
                    # 过滤高置信度的候选
                    qualified_candidates = [
                        candidate for candidate in candidates
                        if candidate.get("confidence", 0) >= confidence_threshold
                    ]
                    
                    mappings[entity] = {
                        "candidates": qualified_candidates,
                        "best_match": qualified_candidates[0] if qualified_candidates else None,
                        "total_candidates": len(candidates),
                        "qualified_candidates": len(qualified_candidates)
                    }
                
                return {
                    "success": True,
                    "message": f"成功映射 {len(entities)} 个实体到本体概念",
                    "ontology_namespace": ontology_namespace,
                    "confidence_threshold": confidence_threshold,
                    "mappings": mappings,
                    "summary": {
                        "total_entities": len(entities),
                        "mapped_entities": len([m for m in mappings.values() if m["best_match"]]),
                        "unmapped_entities": len([m for m in mappings.values() if not m["best_match"]])
                    }
                }
        
        except Exception as e:
            logger.error("本体映射失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"本体映射失败: {str(e)}")
    
    async def _find_ontology_candidates(self, client, dataset_id, entity, namespace, max_candidates):
        """为实体查找本体概念候选"""
        # 使用语义相似性查找候选概念
        query = f"""
        MATCH (concept:Concept {{namespace: '{namespace}'}})
        WITH concept, 
             gds.similarity.cosine(concept.embedding, $entity_embedding) as similarity
        WHERE similarity > 0.5
        RETURN concept.uri as concept_uri,
               concept.label as concept_label,
               concept.description as concept_description,
               similarity as confidence
        ORDER BY similarity DESC
        LIMIT {max_candidates}
        """
        
        try:
            # 这里应该获取实体的嵌入向量，简化处理使用文本匹配
            text_similarity_query = f"""
            MATCH (concept:Concept {{namespace: '{namespace}'}})
            WHERE toLower(concept.label) CONTAINS toLower('{entity}') 
               OR toLower(concept.description) CONTAINS toLower('{entity}')
               OR toLower('{entity}') CONTAINS toLower(concept.label)
            WITH concept,
                 CASE 
                   WHEN toLower(concept.label) = toLower('{entity}') THEN 1.0
                   WHEN toLower(concept.label) CONTAINS toLower('{entity}') THEN 0.8
                   WHEN toLower('{entity}') CONTAINS toLower(concept.label) THEN 0.7
                   ELSE 0.6
                 END as confidence
            RETURN concept.uri as concept_uri,
                   concept.label as concept_label,
                   concept.description as concept_description,
                   confidence
            ORDER BY confidence DESC
            LIMIT {max_candidates}
            """
            
            result = await client.query_graph(text_similarity_query, dataset_id)
            
            candidates = []
            if result and 'result_set' in result:
                for row in result['result_set']:
                    if len(row) >= 4:
                        candidates.append({
                            "concept_uri": row[0],
                            "concept_label": row[1],
                            "concept_description": row[2],
                            "confidence": float(row[3])
                        })
            
            return candidates
            
        except Exception:
            # 如果查询失败，返回空列表
            return []


class ConceptHierarchyTool(BaseTool):
    """概念层次工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="concept_hierarchy",
            description="查询和构建概念层次结构",
            category=ToolCategory.ONTOLOGY,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "concept_uri": {
                    "type": "string",
                    "description": "概念URI"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "direction": {
                    "type": "string",
                    "description": "查询方向",
                    "enum": ["up", "down", "both"],
                    "default": "both"
                },
                "max_depth": {
                    "type": "number",
                    "description": "最大层次深度",
                    "default": 5
                },
                "include_siblings": {
                    "type": "boolean",
                    "description": "是否包含兄弟概念",
                    "default": False
                }
            },
            required=["concept_uri"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        concept_uri = arguments.get("concept_uri")
        dataset_id = arguments.get("dataset_id")
        direction = arguments.get("direction", "both")
        max_depth = arguments.get("max_depth", 5)
        include_siblings = arguments.get("include_siblings", False)
        
        logger.info("查询概念层次", concept_uri=concept_uri, direction=direction)
        
        try:
            async with get_authenticated_client() as client:
                hierarchy = {}
                
                # 获取概念信息
                concept_info = await self._get_concept_info(client, dataset_id, concept_uri)
                hierarchy["concept"] = concept_info
                
                if direction in ["up", "both"]:
                    # 获取父概念层次
                    parents = await self._get_parent_hierarchy(client, dataset_id, concept_uri, max_depth)
                    hierarchy["parents"] = parents
                
                if direction in ["down", "both"]:
                    # 获取子概念层次
                    children = await self._get_children_hierarchy(client, dataset_id, concept_uri, max_depth)
                    hierarchy["children"] = children
                
                if include_siblings:
                    # 获取兄弟概念
                    siblings = await self._get_sibling_concepts(client, dataset_id, concept_uri)
                    hierarchy["siblings"] = siblings
                
                return {
                    "success": True,
                    "message": f"成功查询概念 {concept_uri} 的层次结构",
                    "concept_uri": concept_uri,
                    "direction": direction,
                    "max_depth": max_depth,
                    "hierarchy": hierarchy
                }
        
        except Exception as e:
            logger.error("概念层次查询失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"概念层次查询失败: {str(e)}")
    
    async def _get_concept_info(self, client, dataset_id, concept_uri):
        """获取概念基本信息"""
        query = f"""
        MATCH (c:Concept {{uri: '{concept_uri}'}})
        RETURN c.uri as uri, c.label as label, c.description as description,
               c.namespace as namespace
        """
        
        result = await client.query_graph(query, dataset_id)
        
        if result and 'result_set' in result and result['result_set']:
            row = result['result_set'][0]
            return {
                "uri": row[0],
                "label": row[1],
                "description": row[2],
                "namespace": row[3]
            }
        return None
    
    async def _get_parent_hierarchy(self, client, dataset_id, concept_uri, max_depth):
        """获取父概念层次"""
        query = f"""
        MATCH path = (c:Concept {{uri: '{concept_uri}'}})-[:subClassOf*1..{max_depth}]->(parent:Concept)
        RETURN parent.uri as uri, parent.label as label, 
               parent.description as description, length(path) as depth
        ORDER BY depth, parent.label
        """
        
        result = await client.query_graph(query, dataset_id)
        
        parents = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 4:
                    parents.append({
                        "uri": row[0],
                        "label": row[1],
                        "description": row[2],
                        "depth": row[3]
                    })
        
        return parents
    
    async def _get_children_hierarchy(self, client, dataset_id, concept_uri, max_depth):
        """获取子概念层次"""
        query = f"""
        MATCH path = (child:Concept)-[:subClassOf*1..{max_depth}]->(c:Concept {{uri: '{concept_uri}'}})
        RETURN child.uri as uri, child.label as label,
               child.description as description, length(path) as depth
        ORDER BY depth, child.label
        """
        
        result = await client.query_graph(query, dataset_id)
        
        children = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 4:
                    children.append({
                        "uri": row[0],
                        "label": row[1],
                        "description": row[2],
                        "depth": row[3]
                    })
        
        return children
    
    async def _get_sibling_concepts(self, client, dataset_id, concept_uri):
        """获取兄弟概念"""
        query = f"""
        MATCH (c:Concept {{uri: '{concept_uri}'}})-[:subClassOf]->(parent:Concept)
        MATCH (sibling:Concept)-[:subClassOf]->(parent)
        WHERE sibling.uri <> '{concept_uri}'
        RETURN sibling.uri as uri, sibling.label as label,
               sibling.description as description
        ORDER BY sibling.label
        """
        
        result = await client.query_graph(query, dataset_id)
        
        siblings = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    siblings.append({
                        "uri": row[0],
                        "label": row[1],
                        "description": row[2]
                    })
        
        return siblings


class SemanticReasoningTool(BaseTool):
    """语义推理工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="semantic_reasoning",
            description="执行基于本体的语义推理",
            category=ToolCategory.ONTOLOGY,
            requires_auth=True,
            timeout=120.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "reasoning_type": {
                    "type": "string",
                    "description": "推理类型",
                    "enum": ["subsumption", "classification", "consistency", "entailment"],
                    "default": "subsumption"
                },
                "premises": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "推理前提（RDF三元组或概念表达式）"
                },
                "query": {
                    "type": "string",
                    "description": "推理查询"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "ontology_namespace": {
                    "type": "string",
                    "description": "本体命名空间",
                    "default": "default"
                }
            },
            required=["reasoning_type", "premises"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        reasoning_type = arguments.get("reasoning_type", "subsumption")
        premises = arguments.get("premises", [])
        query = arguments.get("query", "")
        dataset_id = arguments.get("dataset_id")
        namespace = arguments.get("ontology_namespace", "default")
        
        if not premises:
            raise ToolExecutionError(self.metadata.name, "推理前提不能为空")
        
        logger.info("执行语义推理", reasoning_type=reasoning_type, premise_count=len(premises))
        
        try:
            async with get_authenticated_client() as client:
                if reasoning_type == "subsumption":
                    result = await self._subsumption_reasoning(client, dataset_id, premises, namespace)
                elif reasoning_type == "classification":
                    result = await self._classification_reasoning(client, dataset_id, premises, namespace)
                elif reasoning_type == "consistency":
                    result = await self._consistency_checking(client, dataset_id, premises, namespace)
                else:  # entailment
                    result = await self._entailment_reasoning(client, dataset_id, premises, query, namespace)
                
                return {
                    "success": True,
                    "message": f"{reasoning_type} 推理完成",
                    "reasoning_type": reasoning_type,
                    "premises": premises,
                    "query": query,
                    "namespace": namespace,
                    "reasoning_result": result
                }
        
        except Exception as e:
            logger.error("语义推理失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"语义推理失败: {str(e)}")
    
    async def _subsumption_reasoning(self, client, dataset_id, premises, namespace):
        """子类推理"""
        # 简化的子类推理实现
        subsumptions = []
        
        for premise in premises:
            # 假设前提格式为 "A subClassOf B"
            if " subClassOf " in premise:
                parts = premise.split(" subClassOf ")
                if len(parts) == 2:
                    subclass, superclass = parts[0].strip(), parts[1].strip()
                    
                    # 查找传递性子类关系
                    query = f"""
                    MATCH path = (sub:Concept {{label: '{subclass}'}})-[:subClassOf*]->(super:Concept {{label: '{superclass}'}})
                    WHERE sub.namespace = '{namespace}' AND super.namespace = '{namespace}'
                    RETURN length(path) as path_length, 
                           [n in nodes(path) | n.label] as concept_path
                    ORDER BY path_length
                    LIMIT 10
                    """
                    
                    result = await client.query_graph(query, dataset_id)
                    
                    paths = []
                    if result and 'result_set' in result:
                        for row in result['result_set']:
                            if len(row) >= 2:
                                paths.append({
                                    "path_length": row[0],
                                    "concept_path": row[1]
                                })
                    
                    subsumptions.append({
                        "subclass": subclass,
                        "superclass": superclass,
                        "is_subclass": len(paths) > 0,
                        "subsumption_paths": paths
                    })
        
        return {"subsumptions": subsumptions}
    
    async def _classification_reasoning(self, client, dataset_id, premises, namespace):
        """分类推理"""
        # 简化的分类推理
        classifications = {}
        
        # 查找所有概念及其最具体的父类
        query = f"""
        MATCH (c:Concept {{namespace: '{namespace}'}})
        OPTIONAL MATCH (c)-[:subClassOf]->(parent:Concept {{namespace: '{namespace}'}})
        WHERE NOT EXISTS {{ (c)-[:subClassOf]->()-[:subClassOf]->(parent) }}
        RETURN c.label as concept, collect(parent.label) as immediate_parents
        """
        
        result = await client.query_graph(query, dataset_id)
        
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 2:
                    concept = row[0]
                    parents = row[1] if row[1] else []
                    classifications[concept] = {
                        "immediate_parents": parents,
                        "classification": "classified" if parents else "unclassified"
                    }
        
        return {"classifications": classifications}
    
    async def _consistency_checking(self, client, dataset_id, premises, namespace):
        """一致性检查"""
        # 简化的一致性检查
        inconsistencies = []
        
        # 检查循环继承
        query = f"""
        MATCH cycle = (c:Concept {{namespace: '{namespace}'}})-[:subClassOf*2..]->(c)
        RETURN [n in nodes(cycle) | n.label] as cycle_concepts
        """
        
        result = await client.query_graph(query, dataset_id)
        
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 1 and row[0]:
                    inconsistencies.append({
                        "type": "circular_inheritance",
                        "concepts": row[0],
                        "description": f"检测到循环继承: {' -> '.join(row[0])}"
                    })
        
        return {
            "is_consistent": len(inconsistencies) == 0,
            "inconsistencies": inconsistencies
        }
    
    async def _entailment_reasoning(self, client, dataset_id, premises, query, namespace):
        """蕴含推理"""
        # 简化的蕴含推理
        entailments = []
        
        # 基于传递性推理
        for premise in premises:
            if " implies " in premise:
                parts = premise.split(" implies ")
                if len(parts) == 2:
                    antecedent, consequent = parts[0].strip(), parts[1].strip()
                    
                    # 检查是否能推出查询
                    if query and antecedent in query:
                        entailments.append({
                            "premise": premise,
                            "entailment": consequent,
                            "matches_query": consequent in query if query else False
                        })
        
        return {"entailments": entailments}


class RelationInferenceTool(BaseTool):
    """关系推理工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="relation_inference",
            description="推理隐含的关系和属性",
            category=ToolCategory.ONTOLOGY,
            requires_auth=True,
            timeout=90.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "source_entity": {
                    "type": "string",
                    "description": "源实体"
                },
                "target_entity": {
                    "type": "string",
                    "description": "目标实体（可选）"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "inference_rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "推理规则列表",
                    "default": ["transitivity", "symmetry", "inheritance"]
                },
                "max_hops": {
                    "type": "number",
                    "description": "最大跳数",
                    "default": 3
                },
                "confidence_threshold": {
                    "type": "number",
                    "description": "推理置信度阈值",
                    "default": 0.5
                }
            },
            required=["source_entity"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        source_entity = arguments.get("source_entity")
        target_entity = arguments.get("target_entity")
        dataset_id = arguments.get("dataset_id")
        inference_rules = arguments.get("inference_rules", ["transitivity", "symmetry", "inheritance"])
        max_hops = arguments.get("max_hops", 3)
        confidence_threshold = arguments.get("confidence_threshold", 0.5)
        
        logger.info("执行关系推理", source=source_entity, target=target_entity, rules=inference_rules)
        
        try:
            async with get_authenticated_client() as client:
                inferred_relations = {}
                
                if "transitivity" in inference_rules:
                    transitive = await self._infer_transitive_relations(
                        client, dataset_id, source_entity, target_entity, max_hops
                    )
                    inferred_relations["transitive"] = transitive
                
                if "symmetry" in inference_rules:
                    symmetric = await self._infer_symmetric_relations(
                        client, dataset_id, source_entity, target_entity
                    )
                    inferred_relations["symmetric"] = symmetric
                
                if "inheritance" in inference_rules:
                    inherited = await self._infer_inherited_relations(
                        client, dataset_id, source_entity, target_entity
                    )
                    inferred_relations["inherited"] = inherited
                
                # 过滤低置信度的推理结果
                filtered_relations = self._filter_by_confidence(inferred_relations, confidence_threshold)
                
                return {
                    "success": True,
                    "message": "关系推理完成",
                    "source_entity": source_entity,
                    "target_entity": target_entity,
                    "inference_rules": inference_rules,
                    "confidence_threshold": confidence_threshold,
                    "inferred_relations": filtered_relations,
                    "summary": {
                        "total_inferences": sum(len(rels) for rels in filtered_relations.values()),
                        "rule_counts": {rule: len(filtered_relations.get(rule, [])) for rule in inference_rules}
                    }
                }
        
        except Exception as e:
            logger.error("关系推理失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"关系推理失败: {str(e)}")
    
    async def _infer_transitive_relations(self, client, dataset_id, source, target, max_hops):
        """推理传递性关系"""
        if target:
            # 查找源到目标的传递路径
            query = f"""
            MATCH path = (s {{name: '{source}'}})-[r*1..{max_hops}]->(t {{name: '{target}'}})
            WHERE all(rel in r WHERE type(rel) IN ['partOf', 'locatedIn', 'subClassOf'])
            RETURN [rel in relationships(path) | type(rel)] as relation_types,
                   length(path) as path_length,
                   1.0 / length(path) as confidence
            ORDER BY path_length
            LIMIT 10
            """
        else:
            # 查找从源出发的所有传递关系
            query = f"""
            MATCH path = (s {{name: '{source}'}})-[r*2..{max_hops}]->(t)
            WHERE all(rel in r WHERE type(rel) IN ['partOf', 'locatedIn', 'subClassOf'])
            AND all(i in range(1, length(r)) WHERE type(r[i-1]) = type(r[i]))
            RETURN t.name as target,
                   type(r[0]) as relation_type,
                   length(path) as path_length,
                   1.0 / length(path) as confidence
            ORDER BY confidence DESC
            LIMIT 20
            """
        
        result = await client.query_graph(query, dataset_id)
        
        transitive_relations = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if target and len(row) >= 3:
                    transitive_relations.append({
                        "relation_types": row[0],
                        "path_length": row[1],
                        "confidence": float(row[2])
                    })
                elif not target and len(row) >= 4:
                    transitive_relations.append({
                        "target": row[0],
                        "relation_type": row[1],
                        "path_length": row[2],
                        "confidence": float(row[3])
                    })
        
        return transitive_relations
    
    async def _infer_symmetric_relations(self, client, dataset_id, source, target):
        """推理对称关系"""
        if target:
            # 检查特定的对称关系
            query = f"""
            MATCH (s {{name: '{source}'}})-[r]->(t {{name: '{target}'}})
            WHERE type(r) IN ['similar', 'adjacent', 'married', 'sibling']
            RETURN type(r) as relation_type, 
                   EXISTS((t)-[:{type(r)}]->(s)) as is_symmetric,
                   0.9 as confidence
            """
        else:
            # 查找所有对称关系
            query = f"""
            MATCH (s {{name: '{source}'}})-[r]->(t)
            WHERE type(r) IN ['similar', 'adjacent', 'married', 'sibling']
            AND EXISTS((t)-[:{type(r)}]->(s))
            RETURN t.name as target,
                   type(r) as relation_type,
                   true as is_symmetric,
                   0.9 as confidence
            """
        
        result = await client.query_graph(query, dataset_id)
        
        symmetric_relations = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if target and len(row) >= 3:
                    symmetric_relations.append({
                        "relation_type": row[0],
                        "is_symmetric": row[1],
                        "confidence": float(row[2])
                    })
                elif not target and len(row) >= 4:
                    symmetric_relations.append({
                        "target": row[0],
                        "relation_type": row[1],
                        "is_symmetric": row[2],
                        "confidence": float(row[3])
                    })
        
        return symmetric_relations
    
    async def _infer_inherited_relations(self, client, dataset_id, source, target):
        """推理继承关系"""
        # 基于类型层次推理继承的属性和关系
        query = f"""
        MATCH (s {{name: '{source}'}})-[:instanceOf]->(type:Concept)
        MATCH (type)-[:subClassOf*0..3]->(supertype:Concept)
        MATCH (supertype)-[r]->(property)
        WHERE type(r) IN ['hasProperty', 'hasAttribute', 'canDo']
        RETURN property.name as inherited_property,
               type(r) as relation_type,
               supertype.label as from_type,
               1.0 / (length(path) + 1) as confidence
        ORDER BY confidence DESC
        LIMIT 15
        """
        
        result = await client.query_graph(query, dataset_id)
        
        inherited_relations = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 4:
                    inherited_relations.append({
                        "inherited_property": row[0],
                        "relation_type": row[1],
                        "from_type": row[2],
                        "confidence": float(row[3])
                    })
        
        return inherited_relations
    
    def _filter_by_confidence(self, relations_dict, threshold):
        """按置信度过滤推理结果"""
        filtered = {}
        
        for rule_type, relations in relations_dict.items():
            filtered_relations = [
                rel for rel in relations 
                if rel.get("confidence", 0) >= threshold
            ]
            filtered[rule_type] = filtered_relations
        
        return filtered


# 自动注册本体工具
def register_ontology_tools():
    """注册所有本体支持工具"""
    tools = [
        OntologyMappingTool,
        ConceptHierarchyTool,
        SemanticReasoningTool,
        RelationInferenceTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("本体支持工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_ontology_tools()