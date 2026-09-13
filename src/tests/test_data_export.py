"""test_data_export — 交通数据导出与 CSV 下载测试

所属层：tests
依赖：pytest, fastapi, src.tools.export_data
对接算法层：TrafficSim 仿真数据
"""
import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.skills.ui_router_skill import UIRouterSkill  # noqa: E402
from src.tools.export_data import _EXPORT_DIR, export_data_table  # noqa: E402
from src.tools.traffic_backend import (  # noqa: E402
    fetch_event_alarm_history,
    fetch_flow_history,
    fetch_incident_history,
)


class TestExportDataTable:
    """通用 CSV 导出测试。"""

    def test_normal_export(self):
        """正常导出生成 CSV 和 DataCard。"""
        columns = [
            {"key": "datetime", "label": "时间", "unit": ""},
            {"key": "flow_veh_h", "label": "流量", "unit": "veh/h"},
            {"key": "avg_speed_kmh", "label": "平均车速", "unit": "km/h"},
        ]
        rows = [
            {
                "datetime": "2026-09-13 08:00",
                "flow_veh_h": 1820,
                "avg_speed_kmh": 28.4,
            }
        ]
        card = export_data_table(
            "世纪大道近1日流量",
            columns,
            rows,
            charts=[
                {
                    "type": "line",
                    "title": "流量趋势",
                    "x_key": "datetime",
                    "series": [
                        {
                            "key": "flow_veh_h",
                            "label": "流量",
                            "color": "#36d39e",
                        }
                    ],
                    "unit": "veh/h",
                }
            ],
        )

        assert "error" not in card
        assert card["card_type"] == "table"
        assert card["title"] == "世纪大道近1日流量"
        assert card["charts"][0]["type"] == "line"
        assert card["charts"][0]["series"][0]["key"] == "flow_veh_h"
        assert card["download"]["url"] == f"/export/{card['download']['task_id']}"

        csv_path = _EXPORT_DIR / f"{card['download']['task_id']}.csv"
        content = csv_path.read_text(encoding="utf-8-sig")
        assert "流量 (veh/h)" in content
        assert "平均车速 (km/h)" in content
        assert "2026-09-13 08:00" in content

    def test_empty_rows_keeps_header(self):
        """空 rows 仍生成仅含表头的 CSV。"""
        card = export_data_table(
            "空流量表",
            [{"key": "datetime", "label": "时间", "unit": ""}],
            [],
        )

        assert "error" not in card
        assert card["table"]["rows"] == []
        csv_path = _EXPORT_DIR / f"{card['download']['task_id']}.csv"
        assert csv_path.read_text(encoding="utf-8-sig").strip() == "时间"

    def test_auto_derive_columns_and_filename(self):
        """columns 自动推导，filename 可自定义。"""
        card = export_data_table(
            "自动推导",
            [],
            [{"intersection_id": "JK-SJ03", "queue_m": 180}],
            filename="junction_queue.csv",
        )

        assert [column["key"] for column in card["table"]["columns"]] == [
            "intersection_id",
            "queue_m",
        ]
        assert card["download"]["filename"] == "junction_queue.csv"


class TestTrafficRangeTools:
    """交通范围查询工具测试。"""

    def test_flow_history_requires_subject(self):
        """路口和干线均未提供时返回 error。"""
        result = fetch_flow_history()
        assert "error" in result
        assert "intersection_id" in result["error"]

    def test_flow_history_returns_hourly_items(self):
        """路口流量历史返回 24 小时以上数据。"""
        result = fetch_flow_history(
            intersection_id="JK-SJ03",
            start_date="2026-09-12",
            end_date="2026-09-12",
        )

        assert "error" not in result
        assert result["subject"] == "世纪大道·人民路口"
        assert len(result["items"]) == 24
        assert {"datetime", "flow_veh_h", "avg_speed_kmh", "saturation"} <= set(
            result["items"][0]
        )

    @pytest.mark.parametrize(
        "tool",
        [fetch_flow_history, fetch_incident_history, fetch_event_alarm_history],
    )
    def test_range_tools_reject_bad_dates(self, tool):
        """范围查询工具统一校验 YYYY-MM-DD。"""
        kwargs = {"start_date": "2026/09/01", "end_date": "2026-09-02"}
        if tool is fetch_flow_history:
            kwargs["intersection_id"] = "JK-SJ03"
        result = tool(**kwargs)
        assert "error" in result
        assert "日期格式非法" in result["error"]

    def test_incident_and_alarm_history_return_lists(self):
        """事件和接处警历史返回标准列表结构。"""
        incidents = fetch_incident_history("2026-09-12", "2026-09-12")
        alarms = fetch_event_alarm_history("2026-09-12", "2026-09-12")

        assert "error" not in incidents
        assert "error" not in alarms
        assert incidents["count"] == len(incidents["items"])
        assert alarms["count"] == len(alarms["items"])


class TestInferDataCards:
    """UIRouterSkill DataCard 提取测试。"""

    @staticmethod
    def _card_result(title="交通数据"):
        """生成合法 DataCard 结果。"""
        return export_data_table(
            title,
            [{"key": "datetime", "label": "时间", "unit": ""}],
            [{"datetime": "2026-09-13 08:00"}],
        )

    def test_extracts_datacard(self):
        """成功结果被提取为 DataCard。"""
        card = self._card_result()
        cards = UIRouterSkill._infer_data_cards(
            [("export_data_table", card, {"title": "交通数据"})]
        )
        assert len(cards) == 1
        assert cards[0]["download"]["task_id"] == card["download"]["task_id"]

    def test_skips_error_and_non_export(self):
        """错误结果和非导出工具不会误生成卡片。"""
        flow_result = {
            "subject": "世纪大道·人民路口",
            "items": [{"datetime": "2026-09-13 08:00"}],
        }
        assert UIRouterSkill._infer_data_cards(
            [("export_data_table", {"error": "failed"}, {})]
        ) == []
        assert UIRouterSkill._infer_data_cards(
            [("fetch_flow_history", flow_result, {})]
        ) == []

    def test_execute_returns_actions_and_cards(self):
        """execute 同时返回交通页面动作和数据卡片。"""
        card = self._card_result()
        updates = UIRouterSkill().execute(
            [
                (
                    "fetch_flow_history",
                    {"subject": "世纪大道·人民路口", "items": []},
                    {"intersection_id": "JK-SJ03"},
                ),
                ("export_data_table", card, {}),
            ],
            {},
        )
        assert updates["pending_actions"][0].route == "/analysis/flow"
        assert updates["pending_data_cards"][0]["download"]["task_id"] == card["download"]["task_id"]


class TestExportEndpointAndSse:
    """/export 下载端点和 SSE data_card 测试。"""

    def test_download_csv(self):
        """合法 task_id 可下载 CSV。"""
        from fastapi.testclient import TestClient
        from src.services.api import app

        card = export_data_table(
            "端点测试",
            [{"key": "intersection_id", "label": "路口", "unit": ""}],
            [{"intersection_id": "JK-SJ03"}],
        )
        response = TestClient(app).get(f"/export/{card['download']['task_id']}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "JK-SJ03" in response.text

    def test_report_export_endpoint_returns_charts_and_csv(self):
        """前端报告接口同时返回表格、图表和 CSV 下载信息。"""
        from fastapi.testclient import TestClient
        from src.services.api import app

        response = TestClient(app).post(
            "/report/export",
            json={
                "title": "路口饱和度报告",
                "columns": [
                    {"key": "name", "label": "路口"},
                    {"key": "saturation", "label": "饱和度"},
                ],
                "rows": [
                    {"name": "世纪大道·人民路口", "saturation": 0.92},
                    {"name": "世纪大道·中山路口", "saturation": 0.73},
                ],
                "charts": [
                    {
                        "type": "bar",
                        "title": "路口饱和度",
                        "x_key": "name",
                        "series": [
                            {
                                "key": "saturation",
                                "label": "饱和度",
                                "color": "#36d39e",
                            }
                        ],
                    }
                ],
                "filename": "intersection_saturation.csv",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["table"]["rows"][0]["name"] == "世纪大道·人民路口"
        assert payload["charts"][0]["title"] == "路口饱和度"
        assert payload["download"]["filename"] == "intersection_saturation.csv"

    @pytest.mark.parametrize("task_id", ["00000000000000000000000000000000", "nonexistent123"])
    def test_invalid_or_missing_export_never_returns_200(self, task_id):
        """不存在或非法 task_id 不返回文件。"""
        from fastapi.testclient import TestClient
        from src.services.api import app

        response = TestClient(app).get(f"/export/{task_id}")
        assert response.status_code in (400, 404)

    def test_stream_emits_data_card(self, monkeypatch):
        """SSE 能透传交通数据卡片。"""
        from fastapi.testclient import TestClient
        import src.services.api as api_module

        card = export_data_table(
            "流量导出",
            [{"key": "datetime", "label": "时间", "unit": ""}],
            [{"datetime": "2026-09-13 08:00"}],
        )

        class FakeGraph:
            async def astream_events(self, state, config=None, version="v2"):
                yield {
                    "event": "on_chain_end",
                    "data": {"output": {"pending_data_cards": [card]}},
                    "metadata": {},
                }

        monkeypatch.setattr(api_module, "graph", FakeGraph())
        response = TestClient(api_module.app).post(
            "/stream",
            json={"user_input": "导出最近7天流量数据", "thread_id": "test-traffic-export"},
        )

        assert response.status_code == 200
        assert "event: data_card" in response.text
        assert "流量导出" in response.text
        assert "event: done" in response.text
