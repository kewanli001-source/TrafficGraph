"""base_skill — Skill 抽象基类，统一接口契约与生命周期管理

所属层：skills
依赖：abc, src.graph.state, src.config.settings
对接算法层：N/A

设计参考（2026 行业实践）：
  - Pydantic AI Capabilities：将 tools + instructions + hooks 封装为可复用模块
  - Google ADK Skill Registry：统一接口，按需加载
  - LangGraph State Machine：execute() 返回 AgentState 更新字典，与图调度兼容
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from src.config.settings import settings

logger = logging.getLogger(__name__)

_prompts_cache: Dict[str, Any] = {}


def load_prompts() -> Dict[str, Any]:
    """从 settings.prompts 加载 Prompt 字典（支持多文件，模块级缓存）"""
    global _prompts_cache
    if not _prompts_cache:
        _prompts_cache = settings.prompts or {}
    return _prompts_cache


class BaseSkill(ABC):
    """所有 Skill 的抽象基类。

    强制每个 Skill 声明：
    - 元信息（name / tools / prompt_keys / description）
    - execute() 方法（Skill 核心编排逻辑）
    - 可选生命周期钩子（before_execute / after_execute）

    v3_engine_router 只依赖 BaseSkill 接口调度，不感知具体子类。
    """

    # ── 元信息（子类必须声明）────────────────────────────
    name: str
    tools: List[str]
    prompt_keys: List[str]
    description: str

    # ── 核心方法 ─────────────────────────────────────────
    @abstractmethod
    def execute(
        self,
        tool_results: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Skill 编排逻辑：接收工具调用结果 + 当前状态，返回 AgentState 更新。

        Args:
            tool_results: [(tool_name, result_dict, args_dict), ...]
            state: 当前 AgentState（只读）

        Returns:
            AgentState 更新字典（如 pending_actions / traffic_context_hint 等）
        """

    # ── 生命周期钩子（可选覆盖）────────────────────────
    def before_execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行前预处理（如参数归一化、上下文注入）。默认无操作。"""
        return state

    def after_execute(
        self, state: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行后清理/审计（如日志、指标上报）。默认无操作。"""
        return updates

    # ── 工具集辅助 ─────────────────────────────────────
    def has_tool(self, tool_name: str) -> bool:
        """判断某工具是否属于本 Skill。"""
        return tool_name in self.tools

    def matches_tool_results(
        self, tool_results: List[Tuple[str, Any, Any]]
    ) -> bool:
        """判断本轮工具调用中是否有属于本 Skill 的工具。"""
        return any(name in self.tools for name, _, _ in tool_results)
