"""工具注册表 — 交通指挥数据 + 专业知识库 + 记忆 Tools

所属层：tools
依赖：src.tools.*
对接算法层：TrafficSim 仿真数据（TRAFFIC_BACKEND=sim）/ 预留真实 REST API
"""
from typing import Any, Callable, Dict

from src.config.settings import settings
from src.tools.query_traffic_knowledge import query_traffic_knowledge
from src.tools.traffic_backend import (
    fetch_city_overview,
    fetch_intersection_status,
    fetch_corridor_congestion,
    fetch_district_congestion,
    fetch_signal_timing,
    fetch_signal_optimization_suggestion,
    fetch_flow_history,
    fetch_active_incidents,
    fetch_incident_history,
    fetch_camera_list,
    fetch_dispatch_records,
    fetch_event_alarm_history,
)
from src.tools.export_data import export_data_table
from src.tools.memory_ops import save_memory, search_memory, search_relevant_memory
from src.tools.navigate_to_page import navigate_to_page


def _build_route_description() -> str:
    """从 routes.yaml 构建导航工具的路由说明。"""
    accessible = settings.routes.get("accessible_routes", [])
    restricted = settings.routes.get("restricted_routes", [])

    route_items = [
        f"{route['path']}（{route['name']}）"
        for route in accessible + restricted
        if route.get("path") and route.get("name")
    ]
    if not route_items:
        return "目标路由，必须以 / 开头"

    return "目标路由，必须以 / 开头。可用路由：" + "；".join(route_items)


TOOL_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "query_traffic_knowledge": query_traffic_knowledge,
    "fetch_city_overview": fetch_city_overview,
    "fetch_intersection_status": fetch_intersection_status,
    "fetch_corridor_congestion": fetch_corridor_congestion,
    "fetch_district_congestion": fetch_district_congestion,
    "fetch_signal_timing": fetch_signal_timing,
    "fetch_signal_optimization_suggestion": fetch_signal_optimization_suggestion,
    "fetch_flow_history": fetch_flow_history,
    "fetch_active_incidents": fetch_active_incidents,
    "fetch_incident_history": fetch_incident_history,
    "fetch_camera_list": fetch_camera_list,
    "fetch_dispatch_records": fetch_dispatch_records,
    "fetch_event_alarm_history": fetch_event_alarm_history,
    "export_data_table": export_data_table,
    "navigate_to_page": navigate_to_page,
    "search_memory": search_memory,
    "search_relevant_memory": search_relevant_memory,
    "save_memory": save_memory,
}

TOOL_SCHEMAS = [
    {
        "name": "query_traffic_knowledge",
        "description": "从交通专业知识库检索相关问答，用于回答信号配时原理、绿波/干线协调、交通流理论、事件处置流程、规范标准（GB 14886 等）、指挥调度流程等专业问题",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "用户的交通专业相关问题"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "fetch_city_overview",
        "description": "【全市态势查询首选】获取全市交通态势总览：拥堵指数、较昨日变化、当前峰值等级、全市平均车速、拥堵 Top5 路口、活跃事件数。用户问'现在哪里最堵''全市路况''拥堵指数'等全市性问题时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "数据时刻 ISO8601，默认当前时间"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_intersection_status",
        "description": "获取单路口实时状态：服务水平 LOS、平均饱和度、平均延误、各进口道排队/饱和度/二次排队、当前相位、周期、事件影响。回答'某路口堵不堵''为什么排长队''路口排队情况'时使用。需要具体路口 ID（如 JK-SJ01），不确定时先用 fetch_city_overview 查 Top5 再确认",
        "parameters": {
            "type": "object",
            "properties": {
                "intersection_id": {"type": "string", "description": "路口 ID，如 JK-SJ01"},
                "date": {"type": "string", "description": "数据时刻 ISO8601，默认当前时间"},
            },
            "required": ["intersection_id"],
        },
    },
    {
        "name": "fetch_corridor_congestion",
        "description": "获取干线走廊拥堵与绿波状态：平均车速、饱和度、绿波状态（已实现/断裂）、绿波带宽、各路口相位差与偏差。回答'某条路整体路况''绿波带怎么样''干线协调'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "corridor_id": {"type": "string", "description": "干线 ID，如 COR-SJ（世纪大道）"},
                "date": {"type": "string", "description": "数据时刻 ISO8601，默认当前时间"},
            },
            "required": ["corridor_id"],
        },
    },
    {
        "name": "fetch_district_congestion",
        "description": "获取辖区拥堵指数：指数值、较昨日变化、全市排名、辖区最堵路口。回答'某个区堵不堵''哪个区最堵'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "district_id": {"type": "string", "description": "辖区 ID，如 DIST-CBD（中心商务区）"},
                "date": {"type": "string", "description": "数据时刻 ISO8601，默认当前时间"},
            },
            "required": ["district_id"],
        },
    },
    {
        "name": "fetch_signal_timing",
        "description": "获取路口信号配时方案：当前方案（peak/offpeak/night）、周期、各相位绿灯/黄灯/最小绿灯、相位差、协调组、最近调整时间。回答'配时方案''周期多长''绿灯时间'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "intersection_id": {"type": "string", "description": "路口 ID，如 JK-SJ01"},
                "plan_type": {"type": "string", "description": "方案名：peak(高峰)/offpeak(平峰)/night(夜间)，默认当前时段方案"},
            },
            "required": ["intersection_id"],
        },
    },
    {
        "name": "fetch_signal_optimization_suggestion",
        "description": "【信号优化首选】获取信号优化建议（单路口或干线）：基于 Webster 最优周期与检测器实时数据，给出周期/绿信比/相位差调整建议、预期收益与 GB 14886 规范约束校验。用户问'怎么优化信号''配时要不要调''绿波怎么改善'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "intersection_id": {"type": "string", "description": "路口 ID（单路口优化）"},
                "corridor_id": {"type": "string", "description": "干线 ID（绿波协调优化）"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_flow_history",
        "description": "【数据导出-流量】获取路口/干线逐时流量历史（24h × N 天，含流量/车速/饱和度）。用户问'最近N天流量数据并导出/下载'时用此工具取数，再调 export_data_table 生成 CSV。日期 YYYY-MM-DD，「最近7天」= start_date 今天往前推6天、end_date 今天",
        "parameters": {
            "type": "object",
            "properties": {
                "intersection_id": {"type": "string", "description": "路口 ID（与 corridor_id 二选一）"},
                "corridor_id": {"type": "string", "description": "干线 ID（与 intersection_id 二选一）"},
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD，默认今天往前推6天"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD，默认今天"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_active_incidents",
        "description": "获取当前活跃交通事件列表：类型（事故/抛锚/施工/管制）、位置、占道情况、严重度、开始时间、预计恢复、影响等级。回答'现在有什么事故''哪里在施工''有什么事件'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "严重度过滤：minor(一般)/major(较大)/critical(重大)/construction(施工)，默认全部"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_incident_history",
        "description": "【数据导出-事件】获取历史事件明细（按日期范围，含处置时长与派单号）。用户问'导出本周/最近N天事件记录'时用此工具取数，再调 export_data_table 生成 CSV",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD，默认今天往前推6天"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD，默认今天"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_camera_list",
        "description": "获取摄像头清单（可按路口/干线过滤），含视频流地址、在线状态、预置位。回答'调某路口监控''看看视频画面''有哪些摄像头'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "intersection_id": {"type": "string", "description": "按路口过滤"},
                "corridor_id": {"type": "string", "description": "按干线过滤"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_dispatch_records",
        "description": "获取派单/调度记录：资源类型（警力/拖车/信号/养护）、出动数量、到场耗时、处置结果。回答'事故派了谁''调度记录''处置情况'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD，默认今天往前推6天"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD，默认今天"},
                "incident_id": {"type": "string", "description": "按事件 ID 过滤"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_event_alarm_history",
        "description": "【数据导出-警情】获取接处警记录（110接警/122指令/市民热线/视频识别来源，含处警时长与等级）。用户问'导出本周/最近N天警情记录''接处警数据'时用此工具取数，再调 export_data_table 生成 CSV",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD，默认今天往前推6天"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD，默认今天"},
            },
            "required": [],
        },
    },
    {
        "name": "navigate_to_page",
        "description": "下发页面跳转信号，将用户导航到指定指挥中心页面。在获取监控数据后，根据数据类型跳转到对应的详情页面",
        "parameters": {
            "type": "object",
            "properties": {
                "route": {
                    "type": "string",
                    "description": _build_route_description(),
                },
                "params": {
                    "type": "object",
                    "description": "路由参数，如 {\"intersection_id\": \"JK-SJ01\"}",
                },
            },
            "required": ["route"],
        },
    },
    {
        "name": "search_memory",
        "description": "按显式 scope/entity/namespace 检索当前 Agent 的长期记忆。需要精确读取某个记忆域时使用；询问'记得什么/长期信息/运行约束/辖区事实/事件状态'等概括问题时优先用 search_relevant_memory",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题或关键词"},
                "agent_id": {"type": "string", "description": "Agent ID，如 main_graph/traffic_expert/signal_dispatch/ui_router", "default": "main_graph"},
                "area_id": {"type": "string", "description": "区域/路口上下文 ID；无区域时填 local", "default": "local"},
                "scope": {"type": "string", "description": "记忆范围，如 user_preference/area_fact/session_note", "default": "session_note"},
                "entity_id": {"type": "string", "description": "记忆实体 ID，如 user_001/JK-SJ01/default", "default": "default"},
                "namespace": {"type": "array", "items": {"type": "string"}, "description": "显式 namespace；仅在需要跨 Agent/跨 scope 读取时使用"},
                "memory_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["user_preference", "area_fact", "decision_history", "device_state", "safety_constraint", "session_note"],
                    },
                    "description": "记忆类型过滤",
                },
                "limit": {"type": "integer", "description": "返回条数，1-20", "default": 5},
            },
            "required": [],
        },
    },
    {
        "name": "search_relevant_memory",
        "description": "跨常用长期记忆域聚合检索：用户偏好、辖区事实、运行安全约束、已确认决策、临时设备状态、旧 session_note。用户询问'你知道/你记得/长期信息/运行约束/辖区事实/设备状态'时使用",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题或关键词"},
                "agent_id": {"type": "string", "description": "Agent ID，如 main_graph/traffic_expert/signal_dispatch/ui_router", "default": "main_graph"},
                "area_id": {"type": "string", "description": "区域/路口上下文 ID；无区域时填 local", "default": "local"},
                "thread_id": {"type": "string", "description": "当前会话 thread_id，用于检索用户偏好、决策历史和旧 session_note", "default": "unknown"},
                "limit": {"type": "integer", "description": "最终返回条数，1-20，默认 10", "default": 10},
                "include_expired": {"type": "boolean", "description": "是否包含过期 device_state，默认 false", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "save_memory",
        "description": "显式写入当前 Agent 的长期记忆。只保存稳定偏好、辖区事实、已确认决策或安全约束；临时事件状态/警情/单次调度必须带 ttl_seconds 或 valid_until",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "简洁的记忆正文"},
                "agent_id": {"type": "string", "description": "Agent ID，如 main_graph/traffic_expert/signal_dispatch/ui_router", "default": "main_graph"},
                "area_id": {"type": "string", "description": "区域/路口上下文 ID；无区域时填 local", "default": "local"},
                "scope": {"type": "string", "description": "记忆范围，如 user_preference/area_fact/session_note", "default": "session_note"},
                "entity_id": {"type": "string", "description": "记忆实体 ID，如 user_001/JK-SJ01/default", "default": "default"},
                "namespace": {"type": "array", "items": {"type": "string"}, "description": "显式 namespace；仅在需要写入特定记忆域时使用"},
                "metadata": {
                    "type": "object",
                    "description": "记忆元数据，包含 memory_type/source_thread_id/area_id/agent_id/confidence/valid_until/ttl_seconds/tags",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": ["user_preference", "area_fact", "decision_history", "device_state", "safety_constraint", "session_note"],
                            "default": "session_note",
                        },
                        "source_thread_id": {"type": "string", "description": "来源 thread_id", "default": "unknown"},
                        "area_id": {"type": "string", "description": "区域 ID", "default": "local"},
                        "agent_id": {"type": "string", "description": "Agent ID", "default": "main_graph"},
                        "confidence": {"type": "number", "description": "置信度 0-1", "default": 0.8},
                        "valid_until": {"type": "string", "description": "ISO8601 有效期截止时间"},
                        "ttl_seconds": {"type": "integer", "description": "相对 TTL 秒数；临时状态必填"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
                    },
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "export_data_table",
        "description": "【数据报表-通用】将任意表格数据生成表格、图表和可下载 CSV。用户表达「导出/下载表格或报表」意图时，先用范围查询工具取数，再调本工具。columns 用中文表头+单位，rows 为行数据，charts 可生成柱状图/折线图/环形图。下载按钮自动出现，无需在回答中提供下载链接",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "卡片标题，如 世纪大道近7天流量明细"},
                "columns": {
                    "type": "array",
                    "description": "列定义，每项 {key, label, unit?}。key 为 rows 中字段名，label 为中文表头，unit 为单位（可省）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "行数据字段名（snake_case）"},
                            "label": {"type": "string", "description": "中文表头"},
                            "unit": {"type": "string", "description": "单位（可省）"},
                        },
                        "required": ["key", "label"],
                    },
                },
                "rows": {
                    "type": "array",
                    "description": "行数据列表，每行为 {字段名: 值}",
                    "items": {"type": "object"},
                },
                "filename": {"type": "string", "description": "下载文件名（可省，默认自动生成）"},
                "charts": {
                    "type": "array",
                    "description": "图表定义；每项包含 type(bar/line/donut)、title、x_key、series、unit、orientation",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["bar", "line", "donut"]},
                            "title": {"type": "string"},
                            "x_key": {"type": "string"},
                            "series": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "key": {"type": "string"},
                                        "label": {"type": "string"},
                                        "color": {"type": "string"},
                                    },
                                    "required": ["key", "label"],
                                },
                            },
                            "unit": {"type": "string"},
                            "orientation": {"type": "string", "enum": ["vertical", "horizontal"]},
                        },
                        "required": ["type", "title", "x_key", "series"],
                    },
                },
            },
            "required": ["title", "columns", "rows"],
        },
    },
]
