"""test_memory_tools — search_memory/save_memory 工具测试

所属层：tests
依赖：importlib, pathlib, pytest
对接算法层：N/A
"""
import importlib.util
from pathlib import Path

import pytest

from src.config.settings import settings
from src.memory.store import reset_memory_store


def _load_memory_ops():
    """绕过 src.tools.__init__ 加载 memory_ops，避免无 LangChain 环境下测试失败。"""
    module_path = Path(__file__).resolve().parents[1] / "tools" / "memory_ops.py"
    spec = importlib.util.spec_from_file_location("memory_ops_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_MEMORY_OPS = _load_memory_ops()
save_memory = _MEMORY_OPS.save_memory
search_memory = _MEMORY_OPS.search_memory
search_relevant_memory = _MEMORY_OPS.search_relevant_memory


@pytest.fixture(autouse=True)
def clean_memory_store():
    """每个用例清空内存 store。"""
    original_demo_enabled = settings.memory.demo_file_store_enabled
    settings.memory.demo_file_store_enabled = False
    reset_memory_store()
    yield
    settings.memory.demo_file_store_enabled = original_demo_enabled
    reset_memory_store()


def test_save_memory_tool_success():
    """save_memory 正常写入并返回 Pydantic 输出结构的 dict。"""
    result = save_memory(
        content="用户偏好报告先给结论，再给数据依据",
        agent_id="main_graph",
        area_id="DIST-CBD",
        metadata={
            "memory_type": "user_preference",
            "source_thread_id": "thread-1",
            "confidence": 0.85,
            "tags": ["report_style"],
        },
    )

    assert "error" not in result
    assert result["memory"]["content"] == "用户偏好报告先给结论，再给数据依据"
    assert result["namespace"][:4] == ["trafficgraph", "dev", "DIST-CBD", "main_graph"]


def test_search_memory_tool_success():
    """search_memory 能检索同 namespace 下的记忆。"""
    save_memory(
        content="中心商务区属于 DIST-CBD 辖区",
        agent_id="main_graph",
        area_id="DIST-CBD",
        metadata={
            "memory_type": "area_fact",
            "source_thread_id": "thread-1",
            "confidence": 0.9,
            "tags": ["area"],
        },
    )

    result = search_memory(
        query="中心商务区",
        agent_id="main_graph",
        area_id="DIST-CBD",
    )

    assert "error" not in result
    assert len(result["memories"]) == 1
    assert result["memories"][0]["metadata"]["memory_type"] == "area_fact"


def test_save_memory_tool_invalid_temporary_memory():
    """临时记忆缺少 TTL 时返回 error，不抛出异常。"""
    result = save_memory(
        content="JK-SJ03 当前拥堵，事件影响较大",
        agent_id="main_graph",
        area_id="DIST-CBD",
        metadata={
            "memory_type": "device_state",
            "source_thread_id": "thread-1",
        },
    )

    assert result["error"].startswith("memory:")


def test_search_memory_tool_limit_validation():
    """非法 limit 返回 error，不抛出异常。"""
    result = search_memory(limit=0)

    assert result["error"].startswith("memory:")


def test_search_relevant_memory_tool_aggregates_scopes():
    """search_relevant_memory 跨常用 scope 聚合检索。"""
    save_memory(
        content="中心商务区晚高峰以通勤车流为主。",
        agent_id="main_graph",
        area_id="DIST-CBD",
        scope="area",
        entity_id="DIST-CBD",
        metadata={
            "memory_type": "area_fact",
            "source_thread_id": "thread-1",
            "confidence": 0.9,
        },
    )
    save_memory(
        content="重大事件处置必须保留应急通道。",
        agent_id="main_graph",
        area_id="DIST-CBD",
        scope="safety_constraint",
        entity_id="DIST-CBD",
        metadata={
            "memory_type": "safety_constraint",
            "source_thread_id": "thread-1",
            "confidence": 0.9,
        },
    )

    result = search_relevant_memory(
        query="中心商务区有哪些长期信息和运行约束",
        agent_id="main_graph",
        area_id="DIST-CBD",
        thread_id="thread-1",
    )

    contents = [item["content"] for item in result["memories"]]
    assert "中心商务区晚高峰以通勤车流为主。" in contents
    assert "重大事件处置必须保留应急通道。" in contents
