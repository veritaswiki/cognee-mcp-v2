"""
时序感知工具模块
提供时间序列数据处理、时间窗口查询、时间线重建等功能
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from core.tool_registry import BaseTool, ToolMetadata, ToolCategory, register_tool_class
from core.api_client import get_authenticated_client
from core.error_handler import handle_errors, ToolExecutionError
from schemas.mcp_models import ToolInputSchema
import structlog

logger = structlog.get_logger(__name__)


class TimeWindowQueryTool(BaseTool):
    """时间窗口查询工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="time_window_query",
            description="在指定时间窗口内查询数据",
            category=ToolCategory.TEMPORAL,
            requires_auth=True,
            timeout=60.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "start_time": {
                    "type": "string",
                    "description": "开始时间 (ISO格式)"
                },
                "end_time": {
                    "type": "string", 
                    "description": "结束时间 (ISO格式)"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "query": {
                    "type": "string",
                    "description": "查询条件（可选）"
                },
                "limit": {
                    "type": "number",
                    "description": "返回结果数量限制",
                    "default": 50
                }
            },
            required=["start_time", "end_time"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start_time = arguments.get("start_time")
        end_time = arguments.get("end_time")
        dataset_id = arguments.get("dataset_id")
        query = arguments.get("query", "")
        limit = arguments.get("limit", 50)
        
        if not start_time or not end_time:
            raise ToolExecutionError(self.metadata.name, "开始时间和结束时间不能为空")
        
        logger.info("执行时间窗口查询", start_time=start_time, end_time=end_time, limit=limit)
        
        try:
            # 构建时间查询的Cypher语句
            time_filter = f"n.timestamp >= datetime('{start_time}') AND n.timestamp <= datetime('{end_time}')"
            
            if query:
                cypher_query = f"MATCH (n) WHERE {time_filter} AND ({query}) RETURN n LIMIT {limit}"
            else:
                cypher_query = f"MATCH (n) WHERE {time_filter} RETURN n LIMIT {limit}"
            
            async with get_authenticated_client() as client:
                result = await client.query_graph(cypher_query, dataset_id)
                
                return {
                    "success": True,
                    "message": "时间窗口查询执行成功",
                    "time_window": {
                        "start_time": start_time,
                        "end_time": end_time
                    },
                    "query": cypher_query,
                    "result": result,
                    "limit": limit
                }
        
        except Exception as e:
            logger.error("时间窗口查询失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"时间窗口查询失败: {str(e)}")


class TimelineReconstructTool(BaseTool):
    """时间线重建工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="timeline_reconstruct",
            description="重建实体的时间线序列",
            category=ToolCategory.TEMPORAL,
            requires_auth=True,
            timeout=90.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "entity_id": {
                    "type": "string",
                    "description": "实体ID或实体查询条件"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "granularity": {
                    "type": "string",
                    "description": "时间粒度",
                    "enum": ["hour", "day", "week", "month"],
                    "default": "day"
                },
                "max_events": {
                    "type": "number",
                    "description": "最大事件数量",
                    "default": 100
                }
            },
            required=["entity_id"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entity_id = arguments.get("entity_id")
        dataset_id = arguments.get("dataset_id")
        granularity = arguments.get("granularity", "day")
        max_events = arguments.get("max_events", 100)
        
        logger.info("重建时间线", entity_id=entity_id, granularity=granularity)
        
        try:
            # 构建时间线查询
            timeline_query = f"""
            MATCH (entity {{id: '{entity_id}'}})-[r]->(event)
            WHERE event.timestamp IS NOT NULL
            RETURN event.timestamp as timestamp, event, type(r) as relation_type
            ORDER BY event.timestamp ASC
            LIMIT {max_events}
            """
            
            async with get_authenticated_client() as client:
                result = await client.query_graph(timeline_query, dataset_id)
                
                # 处理时间线数据
                timeline_events = []
                if result and 'result_set' in result:
                    for row in result['result_set']:
                        if len(row) >= 3:
                            timeline_events.append({
                                "timestamp": row[0],
                                "event": row[1],
                                "relation_type": row[2]
                            })
                
                # 按粒度分组
                grouped_timeline = self._group_by_granularity(timeline_events, granularity)
                
                return {
                    "success": True,
                    "message": f"成功重建 {entity_id} 的时间线",
                    "entity_id": entity_id,
                    "granularity": granularity,
                    "total_events": len(timeline_events),
                    "timeline": grouped_timeline,
                    "raw_events": timeline_events
                }
        
        except Exception as e:
            logger.error("时间线重建失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"时间线重建失败: {str(e)}")
    
    def _group_by_granularity(self, events: List[Dict], granularity: str) -> Dict[str, List]:
        """按时间粒度分组事件"""
        grouped = {}
        
        for event in events:
            try:
                timestamp = datetime.fromisoformat(event["timestamp"])
                
                if granularity == "hour":
                    key = timestamp.strftime("%Y-%m-%d %H:00")
                elif granularity == "day":
                    key = timestamp.strftime("%Y-%m-%d")
                elif granularity == "week":
                    # 获取这周的开始日期
                    start_of_week = timestamp - timedelta(days=timestamp.weekday())
                    key = start_of_week.strftime("%Y-W%U")
                elif granularity == "month":
                    key = timestamp.strftime("%Y-%m")
                else:
                    key = timestamp.strftime("%Y-%m-%d")
                
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(event)
                
            except Exception:
                # 如果时间解析失败，跳过这个事件
                continue
        
        return grouped


class TemporalPatternTool(BaseTool):
    """时序模式分析工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="temporal_pattern_analysis",
            description="分析时间序列数据中的模式和趋势",
            category=ToolCategory.TEMPORAL,
            requires_auth=True,
            timeout=120.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "pattern_type": {
                    "type": "string",
                    "description": "模式类型",
                    "enum": ["frequency", "sequence", "cluster", "anomaly"],
                    "default": "frequency"
                },
                "time_unit": {
                    "type": "string",
                    "description": "时间单位",
                    "enum": ["hour", "day", "week", "month"],
                    "default": "day"
                },
                "lookback_days": {
                    "type": "number",
                    "description": "回看天数",
                    "default": 30
                }
            }
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dataset_id = arguments.get("dataset_id")
        pattern_type = arguments.get("pattern_type", "frequency")
        time_unit = arguments.get("time_unit", "day")
        lookback_days = arguments.get("lookback_days", 30)
        
        logger.info("分析时序模式", pattern_type=pattern_type, time_unit=time_unit, lookback_days=lookback_days)
        
        try:
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)
            
            async with get_authenticated_client() as client:
                if pattern_type == "frequency":
                    # 频率分析
                    result = await self._analyze_frequency_pattern(client, dataset_id, start_time, end_time, time_unit)
                elif pattern_type == "sequence":
                    # 序列分析
                    result = await self._analyze_sequence_pattern(client, dataset_id, start_time, end_time)
                elif pattern_type == "cluster":
                    # 聚类分析
                    result = await self._analyze_cluster_pattern(client, dataset_id, start_time, end_time)
                else:
                    # 异常检测
                    result = await self._analyze_anomaly_pattern(client, dataset_id, start_time, end_time)
                
                return {
                    "success": True,
                    "message": f"{pattern_type} 时序模式分析完成",
                    "pattern_type": pattern_type,
                    "time_unit": time_unit,
                    "analysis_period": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "lookback_days": lookback_days
                    },
                    "patterns": result
                }
        
        except Exception as e:
            logger.error("时序模式分析失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"时序模式分析失败: {str(e)}")
    
    async def _analyze_frequency_pattern(self, client, dataset_id, start_time, end_time, time_unit):
        """分析频率模式"""
        query = f"""
        MATCH (n)
        WHERE n.timestamp >= datetime('{start_time.isoformat()}') 
        AND n.timestamp <= datetime('{end_time.isoformat()}')
        RETURN date.truncate('{time_unit}', n.timestamp) as period, count(n) as frequency
        ORDER BY period
        """
        
        result = await client.query_graph(query, dataset_id)
        
        frequency_data = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 2:
                    frequency_data.append({
                        "period": row[0],
                        "frequency": row[1]
                    })
        
        return {"frequency_analysis": frequency_data}
    
    async def _analyze_sequence_pattern(self, client, dataset_id, start_time, end_time):
        """分析序列模式"""
        query = f"""
        MATCH path = (a)-[r1]->(b)-[r2]->(c)
        WHERE a.timestamp >= datetime('{start_time.isoformat()}')
        AND c.timestamp <= datetime('{end_time.isoformat()}')
        AND a.timestamp < b.timestamp < c.timestamp
        RETURN type(r1) + '->' + type(r2) as sequence_pattern, count(path) as frequency
        ORDER BY frequency DESC
        LIMIT 20
        """
        
        result = await client.query_graph(query, dataset_id)
        
        sequence_patterns = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 2:
                    sequence_patterns.append({
                        "pattern": row[0],
                        "frequency": row[1]
                    })
        
        return {"sequence_patterns": sequence_patterns}
    
    async def _analyze_cluster_pattern(self, client, dataset_id, start_time, end_time):
        """分析聚类模式"""
        query = f"""
        MATCH (n)
        WHERE n.timestamp >= datetime('{start_time.isoformat()}')
        AND n.timestamp <= datetime('{end_time.isoformat()}')
        WITH date.truncate('day', n.timestamp) as day, 
             duration.inSeconds(n.timestamp, datetime({{epochSeconds: 0}})).hours % 24 as hour
        RETURN day, hour, count(n) as activity
        ORDER BY day, hour
        """
        
        result = await client.query_graph(query, dataset_id)
        
        cluster_data = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    cluster_data.append({
                        "day": row[0],
                        "hour": row[1],
                        "activity": row[2]
                    })
        
        return {"activity_clusters": cluster_data}
    
    async def _analyze_anomaly_pattern(self, client, dataset_id, start_time, end_time):
        """分析异常模式"""
        # 简单的异常检测：找到活动量异常高或异常低的时间段
        query = f"""
        MATCH (n)
        WHERE n.timestamp >= datetime('{start_time.isoformat()}')
        AND n.timestamp <= datetime('{end_time.isoformat()}')
        WITH date.truncate('day', n.timestamp) as day, count(n) as daily_count
        WITH collect(daily_count) as counts, avg(daily_count) as avg_count, 
             stdev(daily_count) as std_count
        UNWIND range(0, size(counts)-1) as i
        WITH counts[i] as count, avg_count, std_count, 
             abs(counts[i] - avg_count) / std_count as z_score
        WHERE z_score > 2.0  // 异常阈值
        RETURN count, z_score
        ORDER BY z_score DESC
        LIMIT 10
        """
        
        result = await client.query_graph(query, dataset_id)
        
        anomalies = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 2:
                    anomalies.append({
                        "count": row[0],
                        "z_score": row[1]
                    })
        
        return {"anomalies": anomalies}


class EventSequenceTool(BaseTool):
    """事件序列分析工具"""
    
    def __init__(self):
        metadata = ToolMetadata(
            name="event_sequence_analysis",
            description="分析事件序列和因果关系",
            category=ToolCategory.TEMPORAL,
            requires_auth=True,
            timeout=90.0
        )
        super().__init__(metadata)
    
    def get_input_schema(self) -> ToolInputSchema:
        return ToolInputSchema(
            type="object",
            properties={
                "seed_event": {
                    "type": "string",
                    "description": "种子事件ID或查询条件"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "数据集ID（可选）"
                },
                "max_depth": {
                    "type": "number",
                    "description": "最大搜索深度",
                    "default": 5
                },
                "time_window_hours": {
                    "type": "number",
                    "description": "时间窗口（小时）",
                    "default": 24
                },
                "direction": {
                    "type": "string",
                    "description": "分析方向",
                    "enum": ["forward", "backward", "both"],
                    "default": "forward"
                }
            },
            required=["seed_event"]
        )
    
    @handle_errors(reraise=False)
    async def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        seed_event = arguments.get("seed_event")
        dataset_id = arguments.get("dataset_id")
        max_depth = arguments.get("max_depth", 5)
        time_window_hours = arguments.get("time_window_hours", 24)
        direction = arguments.get("direction", "forward")
        
        logger.info("分析事件序列", seed_event=seed_event, direction=direction, max_depth=max_depth)
        
        try:
            async with get_authenticated_client() as client:
                sequences = {}
                
                if direction in ["forward", "both"]:
                    forward_seq = await self._trace_forward_sequence(
                        client, dataset_id, seed_event, max_depth, time_window_hours
                    )
                    sequences["forward"] = forward_seq
                
                if direction in ["backward", "both"]:
                    backward_seq = await self._trace_backward_sequence(
                        client, dataset_id, seed_event, max_depth, time_window_hours
                    )
                    sequences["backward"] = backward_seq
                
                return {
                    "success": True,
                    "message": "事件序列分析完成",
                    "seed_event": seed_event,
                    "direction": direction,
                    "max_depth": max_depth,
                    "time_window_hours": time_window_hours,
                    "event_sequences": sequences
                }
        
        except Exception as e:
            logger.error("事件序列分析失败", error=str(e))
            raise ToolExecutionError(self.metadata.name, f"事件序列分析失败: {str(e)}")
    
    async def _trace_forward_sequence(self, client, dataset_id, seed_event, max_depth, time_window_hours):
        """追踪前向事件序列"""
        query = f"""
        MATCH path = (seed {{id: '{seed_event}'}})-[r*1..{max_depth}]->(event)
        WHERE event.timestamp > seed.timestamp
        AND duration.inHours(seed.timestamp, event.timestamp).hours <= {time_window_hours}
        RETURN nodes(path) as sequence, relationships(path) as relations,
               length(path) as depth
        ORDER BY depth, event.timestamp
        LIMIT 50
        """
        
        result = await client.query_graph(query, dataset_id)
        
        sequences = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    sequences.append({
                        "sequence": row[0],
                        "relations": row[1],
                        "depth": row[2]
                    })
        
        return sequences
    
    async def _trace_backward_sequence(self, client, dataset_id, seed_event, max_depth, time_window_hours):
        """追踪后向事件序列"""
        query = f"""
        MATCH path = (event)-[r*1..{max_depth}]->(seed {{id: '{seed_event}'}})
        WHERE event.timestamp < seed.timestamp
        AND duration.inHours(event.timestamp, seed.timestamp).hours <= {time_window_hours}
        RETURN nodes(path) as sequence, relationships(path) as relations,
               length(path) as depth
        ORDER BY depth, event.timestamp DESC
        LIMIT 50
        """
        
        result = await client.query_graph(query, dataset_id)
        
        sequences = []
        if result and 'result_set' in result:
            for row in result['result_set']:
                if len(row) >= 3:
                    sequences.append({
                        "sequence": row[0],
                        "relations": row[1],
                        "depth": row[2]
                    })
        
        return sequences


# 自动注册时序工具
def register_temporal_tools():
    """注册所有时序感知工具"""
    tools = [
        TimeWindowQueryTool,
        TimelineReconstructTool,
        TemporalPatternTool,
        EventSequenceTool
    ]
    
    for tool_class in tools:
        register_tool_class(tool_class)
    
    logger.info("时序感知工具注册完成", tool_count=len(tools))


# 模块导入时自动注册
register_temporal_tools()