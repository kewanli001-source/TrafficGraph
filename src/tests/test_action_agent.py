"""test_action_agent — FastAPI /stream 交通 Agent 集成测试

所属层：tests
依赖：fastapi, httpx, pytest, unittest.mock
对接算法层：N/A（Mock graph.astream_events）
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.schemas.action_agent import UIAction
from src.services.api import app

TEST_ROUTE = "/signal/optimization"
TEST_AREA = "DIST-CBD"


def _make_action() -> UIAction:
    """构造信号优化页面跳转动作。"""
    return UIAction(
        route=TEST_ROUTE,
        name="信号优化",
        params={"intersection_id": "JK-SJ03", "area_id": TEST_AREA},
    )


async def _mock_astream_events(initial_state, config=None, version="v2"):
    """模拟交通 Agent 的 SSE 事件序列。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage

    yield {
        "event": "on_chat_model_stream",
        "metadata": {"langgraph_node": "cognitive_parser"},
        "data": {"chunk": AIMessageChunk(content="正在查询信号配时")},
    }

    mock_output = MagicMock()
    mock_output.tool_calls = [
        {
            "name": "fetch_signal_optimization_suggestion",
            "args": {"intersection_id": "JK-SJ03"},
            "id": "call_01",
        }
    ]
    yield {
        "event": "on_chat_model_end",
        "metadata": {"langgraph_node": "cognitive_parser"},
        "data": {"output": mock_output},
    }

    tool_msg = ToolMessage(
        content=json.dumps(
            {
                "target_type": "intersection",
                "target": "世纪大道·人民路口（JK-SJ03）",
                "suggestions": [{"type": "split", "expected_gain": "排队缩短 15%"}],
            },
            ensure_ascii=False,
        ),
        tool_call_id="call_01",
    )
    yield {
        "event": "on_chain_stream",
        "metadata": {"langgraph_node": "v3_engine_router"},
        "data": {"chunk": {"messages": [tool_msg]}},
    }
    yield {
        "event": "on_chat_model_stream",
        "metadata": {"langgraph_node": "cognitive_parser"},
        "data": {"chunk": AIMessageChunk(content="建议调整 JK-SJ03 的绿信比。")},
    }
    yield {
        "event": "on_chain_end",
        "data": {"output": {"pending_actions": [_make_action()]}},
    }


@pytest.mark.asyncio
async def test_stream_contains_traffic_events():
    """验证 SSE 包含思考、工具、文本、动作和完成事件。"""
    with patch("src.services.api.graph") as mock_graph:
        mock_graph.astream_events = _mock_astream_events

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/stream",
                json={
                    "user_input": "JK-SJ03 的信号配时需要优化吗？",
                    "page_context": {
                        "current_route": "/command/dashboard",
                        "area_id": TEST_AREA,
                    },
                },
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    event_types = [
        line.removeprefix("event: ").strip()
        for line in body.splitlines()
        if line.startswith("event:")
    ]
    for expected in ("thinking", "tool_call", "tool_result", "text", "action", "done"):
        assert expected in event_types

    tool_data = [
        line.removeprefix("data: ").strip()
        for index, line in enumerate(body.splitlines())
        if index > 0 and body.splitlines()[index - 1].strip() == "event: tool_call"
    ]
    assert json.loads(tool_data[0])["name"] == "fetch_signal_optimization_suggestion"

    action_data = [
        line.removeprefix("data: ").strip()
        for index, line in enumerate(body.splitlines())
        if index > 0 and body.splitlines()[index - 1].strip() == "event: action"
    ]
    assert json.loads(action_data[0])["route"] == TEST_ROUTE


@pytest.mark.asyncio
async def test_page_context_area_injected_into_system_prompt():
    """验证 area_id 和当前路由被注入 cognitive_parser。"""
    captured_messages = []

    async def _capture_astream_events(initial_state, config=None, version="v2"):
        from langchain_core.messages import AIMessage
        from src.graph.nodes import cognitive_parser_node
        from src.schemas.action_agent import PageContext

        state = {
            "user_input": "查询 JK-SJ03 路况",
            "page_context": PageContext(
                current_route="/intersection/monitor",
                area_id=TEST_AREA,
            ),
        }
        with patch("src.graph.nodes._get_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = AIMessage(content="ok", tool_calls=[])
            mock_llm_factory.return_value = mock_llm
            result = cognitive_parser_node(state)
            captured_messages.extend(result.get("messages", []))
        yield {"event": "on_chain_end", "data": {"output": {}}}

    with patch("src.services.api.graph") as mock_graph:
        mock_graph.astream_events = _capture_astream_events

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/stream",
                json={
                    "user_input": "查询 JK-SJ03 路况",
                    "page_context": {
                        "current_route": "/intersection/monitor",
                        "area_id": TEST_AREA,
                    },
                },
            )

    system_msg = next(
        message
        for message in captured_messages
        if hasattr(message, "type") and message.type == "system"
    )
    assert "/intersection/monitor" in system_msg.content
    assert TEST_AREA in system_msg.content


@pytest.mark.asyncio
async def test_page_context_allows_missing_area():
    """PageContext.area_id 为 None 时正常注入“未指定”。"""
    from langchain_core.messages import AIMessage
    from src.graph.nodes import cognitive_parser_node
    from src.schemas.action_agent import PageContext

    with patch("src.graph.nodes._get_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="ok", tool_calls=[])
        mock_llm_factory.return_value = mock_llm
        result = cognitive_parser_node(
            {
                "user_input": "现在哪里最堵？",
                "page_context": PageContext(current_route="/command/dashboard", area_id=None),
            }
        )

    system_msg = next(
        message
        for message in result["messages"]
        if hasattr(message, "type") and message.type == "system"
    )
    assert "未指定" in system_msg.content


@pytest.mark.asyncio
async def test_stream_passes_thread_and_area_to_graph():
    """验证 thread_id 和区域上下文传入 LangGraph。"""
    captured = {}

    async def _capture(initial_state, config=None, version="v2"):
        captured["initial_state"] = initial_state
        captured["config"] = config
        yield {"event": "on_chain_end", "data": {"output": {}}}

    with patch("src.services.api.graph") as mock_graph:
        mock_graph.astream_events = _capture

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/stream",
                json={
                    "user_input": "查看全市态势",
                    "thread_id": "thread-traffic-01",
                    "page_context": {
                        "current_route": "/command/dashboard",
                        "area_id": TEST_AREA,
                    },
                },
            )

    assert response.status_code == 200
    assert captured["initial_state"]["thread_id"] == "thread-traffic-01"
    assert captured["initial_state"]["area_id"] == TEST_AREA
    assert captured["config"]["configurable"]["thread_id"] == "thread-traffic-01"


def test_ui_action_name_and_params():
    """UIAction 支持交通页面名称和业务参数。"""
    action = UIAction(
        route="/intersection/monitor",
        name="路口监控",
        params={"intersection_id": "JK-SJ03"},
    )
    assert action.name == "路口监控"
    assert action.params["intersection_id"] == "JK-SJ03"
