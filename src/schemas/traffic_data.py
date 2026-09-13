"""traffic_data — 交通数据工具返回模型

所属层：schemas
依赖：pydantic
对接算法层：TrafficSim 仿真引擎 / 预留真实 API

所有 fetch_* 工具使用强类型返回值：字段可缺省、单位显式标注。
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ── 全市态势 ──────────────────────────────────────

class CongestedIntersection(BaseModel):
    """拥堵 Top 路口条目。"""
    id: str = Field(..., description="路口 ID，如 JK-SJ03")
    name: str = Field(..., description="路口名称")
    saturation: float = Field(..., description="关键流向饱和度 v/c")
    queue_m: int = Field(..., description="最大排队长度（米）")


class CityOverview(BaseModel):
    """全市态势总览。"""
    city: str = Field(..., description="城市名")
    congestion_index: float = Field(..., description="城市拥堵指数（0-10）")
    trend_vs_yesterday: float = Field(..., description="较昨日指数变化")
    peak_level: str = Field(..., description="当前峰值等级（早高峰/晚高峰/平峰/夜间低谷）")
    avg_speed_kmh: float = Field(..., description="全市路网平均车速（km/h）")
    top5_congested_intersections: List[CongestedIntersection] = Field(
        default_factory=list, description="拥堵 Top5 路口")
    active_incident_count: int = Field(..., description="当前活跃事件数")
    timestamp: str = Field(..., description="数据时间戳（ISO8601）")


# ── 路口 ──────────────────────────────────────────

class ApproachStatus(BaseModel):
    """进口道状态。"""
    approach: str = Field(..., description="进口道方向，如 东进口")
    lanes: int = Field(default=3, description="车道数")
    flow_veh_h: int = Field(default=0, description="到达流率（veh/h）")
    capacity_veh_h: int = Field(default=0, description="通行能力（veh/h）")
    saturation: float = Field(..., description="饱和度 v/c")
    queue_m: int = Field(..., description="排队长度（米）")
    avg_delay_s: float = Field(default=0.0, description="平均控制延误（秒）")
    cycle_failures: int = Field(default=0, description="二次排队（周期内未放空）次数")


class IntersectionStatus(BaseModel):
    """单路口实时状态。"""
    id: str = Field(..., description="路口 ID")
    name: str = Field(..., description="路口名称")
    corridor: str = Field(..., description="所属干线")
    district: str = Field(..., description="所属辖区")
    los: str = Field(..., description="服务水平等级（A-F）")
    saturation: float = Field(..., description="平均饱和度 v/c")
    avg_delay_s: float = Field(..., description="平均控制延误（秒）")
    queue: List[ApproachStatus] = Field(default_factory=list, description="各进口道状态")
    current_phase: str = Field(default="", description="当前相位")
    cycle_len_s: int = Field(default=0, description="周期时长（秒）")
    active_plan: str = Field(default="", description="当前配时方案（peak/offpeak/night）")
    incident_effect: Optional[str] = Field(default=None, description="活跃事件影响描述")
    timestamp: str = Field(..., description="数据时间戳")


# ── 干线 / 辖区 ───────────────────────────────────

class CorridorIntersectionState(BaseModel):
    """干线内路口状态条目。"""
    id: str
    name: str
    saturation: float
    speed_kmh: float
    offset_s: int = Field(..., description="当前相位差（秒）")
    offset_deviation_s: float = Field(..., description="与理想绿波相位差偏差（秒）")


class CorridorCongestion(BaseModel):
    """干线走廊拥堵与绿波状态。"""
    id: str
    name: str
    road_class: str
    avg_speed_kmh: float
    saturation: float
    greenwave_status: str = Field(..., description="绿波状态（已实现/断裂）")
    greenwave_bandwidth_s: int = Field(..., description="绿波带宽（秒）")
    mean_offset_deviation_s: float
    intersections: List[CorridorIntersectionState] = Field(default_factory=list)
    timestamp: str


class WorstIntersection(BaseModel):
    """辖区最堵路口。"""
    id: str
    name: str
    saturation: float


class DistrictCongestion(BaseModel):
    """辖区拥堵指数。"""
    id: str
    name: str
    congestion_index: float
    trend_vs_yesterday: float
    rank_in_city: int = Field(..., description="全市辖区拥堵排名（1 = 最堵）")
    worst_intersection: Optional[WorstIntersection] = None
    intersection_count: int = 0
    timestamp: str


# ── 信号 ──────────────────────────────────────────

class SignalPhase(BaseModel):
    """信号相位。"""
    name: str
    green_s: int
    yellow_s: int
    min_green_s: int


class SignalTimingPlan(BaseModel):
    """路口配时方案。"""
    intersection_id: str
    intersection_name: str
    current_plan: str = Field(..., description="方案名（peak/offpeak/night）")
    cycle_s: int
    phases: List[SignalPhase] = Field(default_factory=list)
    offset_s: int = Field(..., description="干线协调相位差（秒）")
    coordination_group: str = Field(..., description="协调组编号")
    last_adjusted: str = Field(..., description="最近调整时间（ISO8601）")


class OptimizationSuggestionItem(BaseModel):
    """单条优化建议。"""
    type: str = Field(..., description="建议类型：cycle / offset / split / phase")
    current: str = Field(..., description="当前值")
    proposed: str = Field(..., description="建议值")
    expected_gain: str = Field(..., description="预期收益")
    constraint_check: str = Field(..., description="规范约束校验结论（GB 14886）")


class SignalOptimizationSuggestion(BaseModel):
    """信号优化建议（单路口或干线）。"""
    target: str = Field(..., description="优化目标（路口/干线名称）")
    target_type: str = Field(..., description="intersection / corridor")
    problem: str = Field(..., description="识别的问题")
    suggestions: List[OptimizationSuggestionItem] = Field(default_factory=list)
    based_on: str = Field(..., description="计算依据（Webster 公式 + 检测器数据）")
    safety_notes: str = Field(..., description="安全约束说明")


# ── 流量历史 ──────────────────────────────────────

class FlowHistoryItem(BaseModel):
    """逐时流量条目。"""
    datetime: str = Field(..., description="时刻，如 2026-09-13 08:00")
    flow_veh_h: int
    avg_speed_kmh: float
    saturation: float


class FlowHistory(BaseModel):
    """流量历史。"""
    subject: str = Field(..., description="路口/干线名称")
    road_class: str
    items: List[FlowHistoryItem] = Field(default_factory=list)


# ── 事件 / 警情 / 调度 ────────────────────────────

class IncidentItem(BaseModel):
    """交通事件。"""
    incident_id: str
    type: str = Field(..., description="事件类型（追尾事故/车辆抛锚/道路施工等）")
    severity: str = Field(..., description="minor / major / critical / construction")
    severity_label: str = Field(..., description="严重度中文（一般/较大/重大/施工）")
    location: str = Field(..., description="发生位置（路口名）")
    intersection_id: str
    lane_block: str = Field(..., description="占道情况")
    start_time: str
    expected_clear: str = Field(..., description="预计恢复时间")
    status: str = Field(..., description="处置中 / 已处置")
    impact_level: str = Field(..., description="影响等级（高/中/低）")
    clearance_minutes: Optional[int] = Field(default=None, description="处置时长（分钟，历史事件）")
    dispatch_id: Optional[str] = Field(default=None, description="关联派单号（历史事件）")


class IncidentList(BaseModel):
    """事件列表。"""
    items: List[IncidentItem] = Field(default_factory=list)
    count: int = 0


class CameraItem(BaseModel):
    """摄像头。"""
    camera_id: str
    name: str
    intersection_id: str
    stream_url: str
    status: str
    ptz_preset: str


class CameraList(BaseModel):
    """摄像头列表。"""
    items: List[CameraItem] = Field(default_factory=list)
    count: int = 0


class DispatchItem(BaseModel):
    """派单/调度记录。"""
    dispatch_id: str
    incident_id: str
    resource_type: str = Field(..., description="资源类型（警力/拖车/信号/养护）")
    units: int = Field(..., description="出动人数/台数")
    dispatched_at: str
    arrived_minutes: int = Field(..., description="到场耗时（分钟）")
    resolved_at: str
    result: str


class DispatchList(BaseModel):
    """派单列表。"""
    items: List[DispatchItem] = Field(default_factory=list)
    count: int = 0


class AlarmItem(BaseModel):
    """接处警记录。"""
    alarm_id: str
    source: str = Field(..., description="来源（110接警/122指令/市民热线/视频识别）")
    type: str
    location: str
    intersection_id: str
    alarm_time: str
    handle_time_minutes: int = Field(..., description="处警时长（分钟）")
    level: str = Field(..., description="警情等级")


class AlarmList(BaseModel):
    """警情列表。"""
    items: List[AlarmItem] = Field(default_factory=list)
    count: int = 0
