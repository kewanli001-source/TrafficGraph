"""traffic_backend — 交通指挥数据工具（态势 / 路口 / 干线 / 信号 / 事件 / 调度 / 视频）

所属层：tools
依赖：src.sim, src.schemas.traffic_data
对接算法层：TrafficSim 仿真引擎（TRAFFIC_BACKEND=sim，默认）/ 预留真实 REST API

适配器约定：
  - TRAFFIC_BACKEND 未配置或 = "sim" → 走 TrafficSim 确定性仿真
  - TRAFFIC_BACKEND=real → 调用 TRAFFIC_API_BASE_URL 真实后端；
    真实接入层尚未实现时返回 error（不返回假数据）
"""
import logging
import os
from typing import Any, Dict, List, Optional

from src.sim import get_sim

logger = logging.getLogger(__name__)

TRAFFIC_BACKEND = os.getenv("TRAFFIC_BACKEND", "sim").lower()
TRAFFIC_API_BASE_URL = os.getenv("TRAFFIC_API_BASE_URL")


def _is_sim() -> bool:
    """判断是否使用仿真数据源。"""
    return TRAFFIC_BACKEND != "real"


def _real_unavailable(tool_name: str) -> Dict[str, Any]:
    """真实后端未接入时的统一错误返回。"""
    return {
        "error": (
            f"{tool_name}: 真实后端模式（TRAFFIC_BACKEND=real）尚未接入，"
            f"请配置 TRAFFIC_API_BASE_URL 后实现 REST 适配，或移除该变量使用仿真数据"
        )
    }


def _validate_date(value: Optional[str], tool_name: str) -> Optional[Dict[str, Any]]:
    """日期参数格式校验（YYYY-MM-DD / YYYY-MM-DDTHH:MM:SS）。"""
    if not value:
        return None
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            datetime.strptime(value[:19], fmt)
            return None
        except ValueError:
            continue
    return {"error": f"{tool_name}: 日期格式非法 {value}，应为 YYYY-MM-DD"}


# ── 全市态势 ──────────────────────────────────────

def fetch_city_overview(date: Optional[str] = None) -> Dict[str, Any]:
    """获取全市交通态势总览。

    Args:
        date: 数据时刻（ISO8601），默认当前时间

    Returns:
        CityOverview dict 或 {"error": ...}
    """
    try:
        if not _is_sim():
            return _real_unavailable("fetch_city_overview")
        err = _validate_date(date, "fetch_city_overview")
        if err:
            return err
        from src.schemas.traffic_data import CityOverview
        return CityOverview(**get_sim().city_overview(date)).model_dump()
    except Exception as e:
        logger.error(f"fetch_city_overview 失败: {e}")
        return {"error": f"fetch_city_overview: {e}"}


def fetch_intersection_status(intersection_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """获取单路口实时状态（LOS/饱和度/排队/延误/相位）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_intersection_status")
        if not intersection_id:
            return {"error": "fetch_intersection_status: intersection_id 不能为空，如 JK-SJ01"}
        err = _validate_date(date, "fetch_intersection_status")
        if err:
            return err
        from src.schemas.traffic_data import IntersectionStatus
        return IntersectionStatus(**get_sim().intersection_status(intersection_id, date)).model_dump()
    except Exception as e:
        logger.error(f"fetch_intersection_status 失败: {e}")
        return {"error": f"fetch_intersection_status: {e}"}


def fetch_corridor_congestion(corridor_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """获取干线走廊拥堵与绿波协调状态。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_corridor_congestion")
        if not corridor_id:
            return {"error": "fetch_corridor_congestion: corridor_id 不能为空，如 COR-SJ"}
        err = _validate_date(date, "fetch_corridor_congestion")
        if err:
            return err
        from src.schemas.traffic_data import CorridorCongestion
        return CorridorCongestion(**get_sim().corridor_congestion(corridor_id, date)).model_dump()
    except Exception as e:
        logger.error(f"fetch_corridor_congestion 失败: {e}")
        return {"error": f"fetch_corridor_congestion: {e}"}


def fetch_district_congestion(district_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """获取辖区拥堵指数与排名。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_district_congestion")
        if not district_id:
            return {"error": "fetch_district_congestion: district_id 不能为空，如 DIST-CBD"}
        err = _validate_date(date, "fetch_district_congestion")
        if err:
            return err
        from src.schemas.traffic_data import DistrictCongestion
        return DistrictCongestion(**get_sim().district_congestion(district_id, date)).model_dump()
    except Exception as e:
        logger.error(f"fetch_district_congestion 失败: {e}")
        return {"error": f"fetch_district_congestion: {e}"}


# ── 信号 ──────────────────────────────────────────

def fetch_signal_timing(intersection_id: str, plan_type: Optional[str] = None) -> Dict[str, Any]:
    """获取路口配时方案（周期/相位/绿信比/相位差）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_signal_timing")
        if not intersection_id:
            return {"error": "fetch_signal_timing: intersection_id 不能为空，如 JK-SJ01"}
        from src.schemas.traffic_data import SignalTimingPlan
        return SignalTimingPlan(**get_sim().signal_timing(intersection_id, plan_type)).model_dump()
    except Exception as e:
        logger.error(f"fetch_signal_timing 失败: {e}")
        return {"error": f"fetch_signal_timing: {e}"}


def fetch_signal_optimization_suggestion(
    intersection_id: Optional[str] = None,
    corridor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """获取信号优化建议（Webster 周期校验 + 绿波 offset 重整）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_signal_optimization_suggestion")
        from src.schemas.traffic_data import SignalOptimizationSuggestion
        result = get_sim().signal_optimization_suggestion(intersection_id, corridor_id)
        if "error" in result:
            return result
        return SignalOptimizationSuggestion(**result).model_dump()
    except Exception as e:
        logger.error(f"fetch_signal_optimization_suggestion 失败: {e}")
        return {"error": f"fetch_signal_optimization_suggestion: {e}"}


# ── 流量历史 ──────────────────────────────────────

def fetch_flow_history(
    intersection_id: Optional[str] = None,
    corridor_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """获取路口/干线逐时流量历史（24h × N 天）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_flow_history")
        for label, value in (("start_date", start_date), ("end_date", end_date)):
            err = _validate_date(value, "fetch_flow_history")
            if err:
                return err
        from src.schemas.traffic_data import FlowHistory
        result = get_sim().flow_history(intersection_id, corridor_id, start_date, end_date)
        if "error" in result:
            return result
        return FlowHistory(**result).model_dump()
    except Exception as e:
        logger.error(f"fetch_flow_history 失败: {e}")
        return {"error": f"fetch_flow_history: {e}"}


# ── 事件 ──────────────────────────────────────────

def fetch_active_incidents(severity: Optional[str] = None) -> Dict[str, Any]:
    """获取当前活跃交通事件（事故/抛锚/施工/管制）。

    Args:
        severity: 可选过滤，minor / major / critical / construction

    Returns:
        IncidentList dict 或 {"error": ...}
    """
    try:
        if not _is_sim():
            return _real_unavailable("fetch_active_incidents")
        if severity and severity not in ("minor", "major", "critical", "construction"):
            return {"error": "fetch_active_incidents: severity 可选值 minor/major/critical/construction"}
        from src.schemas.traffic_data import IncidentList
        items = get_sim().active_incidents(severity=severity)
        return IncidentList(items=items, count=len(items)).model_dump()
    except Exception as e:
        logger.error(f"fetch_active_incidents 失败: {e}")
        return {"error": f"fetch_active_incidents: {e}"}


def fetch_incident_history(
    start_date: Optional[str] = None, end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """获取历史事件明细（含处置时长与派单号）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_incident_history")
        for label, value in (("start_date", start_date), ("end_date", end_date)):
            err = _validate_date(value, "fetch_incident_history")
            if err:
                return err
        from src.schemas.traffic_data import IncidentList
        items = get_sim().incident_history(start_date, end_date)
        return IncidentList(items=items, count=len(items)).model_dump()
    except Exception as e:
        logger.error(f"fetch_incident_history 失败: {e}")
        return {"error": f"fetch_incident_history: {e}"}


# ── 视频 ──────────────────────────────────────────

def fetch_camera_list(
    intersection_id: Optional[str] = None, corridor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """获取摄像头清单（可按路口/干线过滤）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_camera_list")
        from src.schemas.traffic_data import CameraList
        items = get_sim().camera_list(intersection_id, corridor_id)
        if items and "error" in items[0]:
            return items[0]
        return CameraList(items=items, count=len(items)).model_dump()
    except Exception as e:
        logger.error(f"fetch_camera_list 失败: {e}")
        return {"error": f"fetch_camera_list: {e}"}


# ── 调度 / 警情 ──────────────────────────────────

def fetch_dispatch_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    incident_id: Optional[str] = None,
) -> Dict[str, Any]:
    """获取派单/调度记录（警力/拖车/信号/养护）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_dispatch_records")
        for label, value in (("start_date", start_date), ("end_date", end_date)):
            err = _validate_date(value, "fetch_dispatch_records")
            if err:
                return err
        from src.schemas.traffic_data import DispatchList
        items = get_sim().dispatch_records(start_date, end_date, incident_id)
        return DispatchList(items=items, count=len(items)).model_dump()
    except Exception as e:
        logger.error(f"fetch_dispatch_records 失败: {e}")
        return {"error": f"fetch_dispatch_records: {e}"}


def fetch_event_alarm_history(
    start_date: Optional[str] = None, end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """获取接处警记录（110/122/市民热线/视频识别来源）。"""
    try:
        if not _is_sim():
            return _real_unavailable("fetch_event_alarm_history")
        for label, value in (("start_date", start_date), ("end_date", end_date)):
            err = _validate_date(value, "fetch_event_alarm_history")
            if err:
                return err
        from src.schemas.traffic_data import AlarmList
        items = get_sim().event_alarm_history(start_date, end_date)
        return AlarmList(items=items, count=len(items)).model_dump()
    except Exception as e:
        logger.error(f"fetch_event_alarm_history 失败: {e}")
        return {"error": f"fetch_event_alarm_history: {e}"}
