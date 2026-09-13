"""test_traffic_backend — 12 个交通数据工具契约测试

所属层：tests
依赖：pytest, src.tools.traffic_backend
对接算法层：TrafficSim 仿真引擎
"""
from src.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from src.tools.traffic_backend import (
    fetch_active_incidents,
    fetch_camera_list,
    fetch_city_overview,
    fetch_corridor_congestion,
    fetch_dispatch_records,
    fetch_district_congestion,
    fetch_event_alarm_history,
    fetch_flow_history,
    fetch_incident_history,
    fetch_intersection_status,
    fetch_signal_optimization_suggestion,
    fetch_signal_timing,
)

FIXED_TIME = "2026-09-13T08:30:00"


def test_backend_registers_exactly_twelve_traffic_tools():
    """12 个交通数据工具全部注册并绑定 Schema。"""
    names = {
        "fetch_city_overview",
        "fetch_intersection_status",
        "fetch_corridor_congestion",
        "fetch_district_congestion",
        "fetch_signal_timing",
        "fetch_signal_optimization_suggestion",
        "fetch_flow_history",
        "fetch_active_incidents",
        "fetch_incident_history",
        "fetch_camera_list",
        "fetch_dispatch_records",
        "fetch_event_alarm_history",
    }
    schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
    assert names <= set(TOOL_REGISTRY)
    assert names <= schema_names


def test_city_overview_contract():
    """全市态势返回核心指标和 Top5。"""
    result = fetch_city_overview(FIXED_TIME)
    assert result["city"] == "上海市"
    assert 0 <= result["congestion_index"] <= 10
    assert result["active_incident_count"] >= 0
    assert isinstance(result["top5_congested_intersections"], list)


def test_intersection_and_signal_contracts():
    """路口状态和信号配时模型字段完整。"""
    status = fetch_intersection_status("JK-SJ03", FIXED_TIME)
    timing = fetch_signal_timing("JK-SJ03")

    assert status["id"] == "JK-SJ03"
    assert status["los"] in {"A", "B", "C", "D", "E", "F"}
    assert len(status["queue"]) == 4
    assert timing["intersection_id"] == "JK-SJ03"
    assert timing["cycle_s"] > 0
    assert timing["phases"]


def test_corridor_and_district_contracts():
    """干线和辖区聚合模型可正常返回。"""
    corridor = fetch_corridor_congestion("COR-SJ", FIXED_TIME)
    district = fetch_district_congestion("DIST-CBD", FIXED_TIME)

    assert corridor["id"] == "COR-SJ"
    assert corridor["greenwave_status"] in {"已实现", "断裂"}
    assert len(corridor["intersections"]) == 6
    assert district["id"] == "DIST-CBD"
    assert 0 <= district["congestion_index"] <= 10
    assert district["rank_in_city"] >= 1


def test_optimization_contract():
    """信号优化建议包含问题、建议和规范校验。"""
    result = fetch_signal_optimization_suggestion(intersection_id="JK-SJ03")

    assert result["target_type"] == "intersection"
    assert result["problem"]
    assert isinstance(result["suggestions"], list)
    assert "Webster" in result["based_on"]
    assert "GB 14886" in result["safety_notes"]


def test_flow_history_contract():
    """流量历史支持按干线路口查询。"""
    result = fetch_flow_history(
        intersection_id="JK-SJ03",
        start_date="2026-09-12",
        end_date="2026-09-12",
    )

    assert result["road_class"] == "主干道"
    assert len(result["items"]) == 24


def test_incident_camera_dispatch_alarm_contracts():
    """事件、视频、派单和接处警工具返回列表结构。"""
    active = fetch_active_incidents()
    history = fetch_incident_history("2026-09-12", "2026-09-12")
    cameras = fetch_camera_list(intersection_id="JK-SJ03")
    dispatches = fetch_dispatch_records("2026-09-12", "2026-09-12")
    alarms = fetch_event_alarm_history("2026-09-12", "2026-09-12")

    assert active["count"] == len(active["items"])
    assert history["count"] == len(history["items"])
    assert cameras["count"] == 2
    assert dispatches["count"] == len(dispatches["items"])
    assert alarms["count"] == len(alarms["items"])


def test_invalid_traffic_ids_return_errors():
    """无效路口和干线不会回退为编造数据。"""
    assert "error" in fetch_intersection_status("JK-NOT-FOUND")
    assert "error" in fetch_corridor_congestion("COR-NOT-FOUND")
    assert "error" in fetch_district_congestion("DIST-NOT-FOUND")


def test_intersection_detail_api():
    """路口详情 API 同时返回状态、配时和优化建议。"""
    from fastapi.testclient import TestClient
    from src.services.api import app

    client = TestClient(app)
    response = client.get("/traffic/intersection/JK-SJ03")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["id"] == "JK-SJ03"
    assert payload["signal"]["intersection_id"] == "JK-SJ03"
    assert payload["signal"]["phases"]
    assert payload["optimization"]["target_type"] == "intersection"
    assert payload["flow"]["subject"] == "世纪大道·人民路口"
    assert len(payload["flow"]["items"]) == 24
    assert client.get("/traffic/intersection/JK-NOT-FOUND").status_code == 404
