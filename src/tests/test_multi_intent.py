"""test_multi_intent — 交通 Agent 多意图识别与分段报告测试

所属层：tests
依赖：pytest, httpx, unittest.mock
对接算法层：N/A
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.schemas.v3_engine import IntentItem


class TestIntentItem:
    """交通 IntentItem 模型测试。"""

    def test_basic_creation(self):
        """基本字段和默认值正确。"""
        item = IntentItem(id=1, description="JK-SJ03 路况查询")
        assert item.id == 1
        assert item.category == "general"
        assert item.status == "pending"

    def test_traffic_categories(self):
        """支持信号、事件、调度和知识类别。"""
        item = IntentItem(
            id=2,
            description="生成信号优化建议",
            category="signal",
            depends_on=[1],
        )
        assert item.category == "signal"
        assert item.depends_on == [1]

    def test_serialization(self):
        """可序列化为 SSE JSON。"""
        item = IntentItem(id=1, description="查看活跃事件", category="incident")
        payload = json.loads(json.dumps(item.model_dump(), ensure_ascii=False))
        assert payload["category"] == "incident"


class TestAgentStateAndPrompts:
    """AgentState 与交通 Prompt 测试。"""

    def test_state_accepts_traffic_fields(self):
        """State 支持区域、交通知识和信号提示字段。"""
        from src.graph.state import AgentState

        state: AgentState = {
            "user_input": "查看 JK-SJ03 并优化配时",
            "area_id": "DIST-CBD",
            "traffic_knowledge": {
                "query": "配时",
                "results": [],
                "system_types": [],
                "distances": [],
            },
            "signal_dispatch_hint": {"system_suffix": "保留最小绿灯"},
        }
        assert state["area_id"] == "DIST-CBD"
        assert state["signal_dispatch_hint"]["system_suffix"] == "保留最小绿灯"

    def test_prompt_contains_traffic_workflow(self):
        """主 Prompt 包含交通工具与多意图规则。"""
        from src.graph.nodes import _load_prompts

        content = _load_prompts()["cognitive_parser"]["system"]
        assert "fetch_signal_optimization_suggestion" in content
        assert "fetch_active_incidents" in content
        assert "多意图识别" in content
        assert "并行调用多个工具" in content

    def test_interpreter_prompt_contains_safety(self):
        """报告 Prompt 包含信号安全边界。"""
        from src.graph.nodes import _load_prompts

        content = _load_prompts()["interpreter_generator"]["system"]
        assert "GB 14886" in content
        assert "最小绿灯" in content
        assert "多意图分段报告" in content


class TestCognitiveParserMultiIntent:
    """cognitive_parser 多工具与工具回环测试。"""

    def test_multi_tool_calls_build_intent_plan(self):
        """多个交通工具调用自动生成 intent_plan。"""
        from src.graph.nodes import cognitive_parser_node

        response = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "fetch_signal_optimization_suggestion",
                    "args": {"intersection_id": "JK-SJ03"},
                    "id": "tc1",
                },
                {
                    "name": "fetch_active_incidents",
                    "args": {},
                    "id": "tc2",
                },
            ],
        )
        with patch("src.graph.nodes._get_llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = response
            mock_factory.return_value = mock_llm
            result = cognitive_parser_node({"user_input": "优化配时并查看当前事件"})

        assert len(result["intent_plan"]) == 2
        assert result["intent_plan"][0].category == "signal"
        assert result["intent_plan"][1].category == "incident"

    def test_single_tool_call_no_intent_plan(self):
        """单个工具调用不生成多意图计划。"""
        from src.graph.nodes import cognitive_parser_node

        response = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "fetch_intersection_status",
                    "args": {"intersection_id": "JK-SJ03"},
                    "id": "tc1",
                }
            ],
        )
        with patch("src.graph.nodes._get_llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = response
            mock_factory.return_value = mock_llm
            result = cognitive_parser_node({"user_input": "查看 JK-SJ03 路况"})

        assert "intent_plan" not in result

    def test_checkpoint_resume_appends_new_user_input(self):
        """checkpoint 恢复时追加本轮用户输入。"""
        from src.graph.nodes import cognitive_parser_node

        state = {
            "user_input": "现在世纪大道绿波怎么样？",
            "messages": [
                SystemMessage(content="system"),
                HumanMessage(content="先记住中心商务区优先看主干道"),
                AIMessage(content="已记录"),
            ],
        }
        response = AIMessage(content="正在查询", tool_calls=[])
        with patch("src.graph.nodes._get_llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = response
            mock_factory.return_value = mock_llm
            cognitive_parser_node(state)

        invoked = mock_llm.invoke.call_args[0][0]
        assert isinstance(invoked[-1], HumanMessage)
        assert "世纪大道" in invoked[-1].content

    def test_tool_loop_injects_skill_hints(self):
        """工具回环时引用和信号约束会注入 LLM 上下文。"""
        from src.graph.nodes import cognitive_parser_node

        state = {
            "user_input": "优化 JK-SJ03 配时",
            "messages": [
                SystemMessage(content="system"),
                HumanMessage(content="优化 JK-SJ03 配时"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "fetch_signal_optimization_suggestion",
                            "args": {"intersection_id": "JK-SJ03"},
                            "id": "tc1",
                        }
                    ],
                ),
                ToolMessage(content="{}", tool_call_id="tc1"),
            ],
            "traffic_context_hint": {"system_suffix": "必须标注知识库来源"},
            "signal_dispatch_hint": {"system_suffix": "不得低于最小绿灯 15 秒"},
        }
        with patch("src.graph.nodes._get_llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = AIMessage(content="建议如下")
            mock_factory.return_value = mock_llm
            result = cognitive_parser_node(state)

        invoked = mock_llm.invoke.call_args[0][0]
        assert "知识库来源" in invoked[0].content
        assert "最小绿灯 15 秒" in invoked[0].content
        assert result["messages"][0].content == "建议如下"


class TestInterpreterAndSse:
    """报告注入与 SSE intent_plan 测试。"""

    def test_intent_plan_injected_into_interpreter(self):
        """interpreter_generator 注入意图清单。"""
        from src.graph.nodes import interpreter_generator_node

        state = {
            "user_input": "优化配时并查看事件",
            "messages": [
                SystemMessage(content="system"),
                HumanMessage(content="优化配时并查看事件"),
                ToolMessage(content="{}", tool_call_id="tc1"),
            ],
            "intent_plan": [
                IntentItem(id=1, description="信号优化", status="done"),
                IntentItem(id=2, description="事件查询", status="done"),
            ],
        }
        with patch("src.graph.nodes._get_llm") as mock_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = AIMessage(content="报告")
            mock_factory.return_value = mock_llm
            interpreter_generator_node(state)

        system_msg = mock_llm.invoke.call_args[0][0][0]
        assert "信号优化" in system_msg.content
        assert "事件查询" in system_msg.content

    @pytest.mark.asyncio
    async def test_sse_emits_intent_plan(self):
        """/stream 推送 intent_plan 事件。"""
        from httpx import ASGITransport, AsyncClient
        from src.services.api import app

        async def _mock_astream_events(initial_state, config=None, version="v2"):
            yield {
                "event": "on_chain_end",
                "data": {
                    "output": {
                        "intent_plan": [
                            IntentItem(id=1, description="信号优化", category="signal"),
                            IntentItem(id=2, description="事件查询", category="incident"),
                        ]
                    }
                },
            }

        with patch("src.services.api.graph") as mock_graph:
            mock_graph.astream_events = _mock_astream_events
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/stream",
                    json={
                        "user_input": "优化配时并查看事件",
                        "page_context": {
                            "current_route": "/command/dashboard",
                            "area_id": "DIST-CBD",
                        },
                    },
                )

        assert response.status_code == 200
        assert "event: intent_plan" in response.text
        assert '"category": "signal"' in response.text
        assert '"category": "incident"' in response.text
