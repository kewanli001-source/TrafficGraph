"""edges — 决策层 Agent 条件路由

所属层：graph
依赖：langchain_core, src.config.settings
对接算法层：N/A
"""
from langchain_core.messages import AIMessage

from src.config.settings import settings
from src.graph.state import AgentState


def should_continue(state: AgentState) -> str:
    """判断下一步：调用工具 → 继续，否则 → 生成报告。"""
    messages = state.get("messages", [])
    if not messages or state.get("error"):
        return "report"

    last = messages[-1]
    if state.get("messages") and isinstance(last, AIMessage):
        iteration = sum(1 for m in messages if isinstance(m, AIMessage))
        if iteration >= settings.agent.max_iterations:
            return "report"
        if getattr(last, "tool_calls", None):
            return "tools"

    return "report"
