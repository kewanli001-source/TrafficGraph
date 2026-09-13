"""test_ui_router_skill — 交通路由匹配与跳转推断测试

所属层：tests
依赖：pytest, src.skills.ui_router_skill
对接算法层：N/A
"""
from src.skills.ui_router_skill import RouteRegistry, UIRouterSkill


class TestRouteRegistry:
    """RouteRegistry 交通路由匹配测试。"""

    def test_exact_match(self):
        """完整页面名称精确匹配。"""
        registry = RouteRegistry()
        result = registry.find_route("信号优化")

        assert "error" not in result
        assert result["path"] == "/signal/optimization"
        assert result["name"] == "信号优化"
        assert result["is_restricted"] is False

    def test_fuzzy_match(self):
        """关键词可命中对应页面。"""
        registry = RouteRegistry()
        result = registry.find_route("绿波协调")

        assert "error" not in result
        assert result["path"] == "/signal/greenwave"
        assert result["name"] == "绿波协调"

    def test_restricted_page(self):
        """受限信号页面返回授权说明。"""
        registry = RouteRegistry()
        result = registry.find_route("配时方案编辑")

        assert "error" not in result
        assert result["path"] == "/signal/plan-edit"
        assert result["is_restricted"] is True
        assert "双人复核" in result["restriction_reason"]

    def test_no_match(self):
        """不存在的页面返回 error。"""
        registry = RouteRegistry()
        result = registry.find_route("不存在的页面XYZ123")

        assert "error" in result
        assert "未找到匹配的页面" in result["error"]


def test_navigation_maps_traffic_tool_to_page():
    """路口状态工具自动映射到路口监控页。"""
    actions = UIRouterSkill._infer_navigation(
        [
            (
                "fetch_intersection_status",
                {"id": "JK-SJ03"},
                {"intersection_id": "JK-SJ03"},
            )
        ]
    )

    assert len(actions) == 1
    assert actions[0].route == "/intersection/monitor"
    assert actions[0].name == "路口监控"
    assert actions[0].params["intersection_id"] == "JK-SJ03"


def test_navigation_normalizes_and_deduplicates_explicit_route():
    """显式路由自动补全 / 且重复路由只保留一次。"""
    actions = UIRouterSkill._infer_navigation(
        [
            ("navigate_to_page", {"route": "signal/timing"}, {}),
            ("navigate_to_page", {"route": "/signal/timing"}, {}),
        ]
    )

    assert len(actions) == 1
    assert actions[0].route == "/signal/timing"
    assert actions[0].name == "信号配时"
