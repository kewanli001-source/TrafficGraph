"""signal_dispatch_skill — 信号优化与调度指挥技能

所属层：skills
依赖：src.tools.traffic_backend, src.config.settings
对接算法层：信号优化建议引擎（TrafficSim Webster 计算）

SOP：
  1. v3_engine_router 执行 fetch_signal_optimization_suggestion / fetch_signal_timing
  2. 本 Skill 读取工具返回的建议内容
  3. 注入调度安全约束 Prompt（最小绿灯 / 行人过街 / 应急优先），由
     interpreter_generator 生成带安全边界的处置建议报告

Prompt keys（src/config/prompts/signal_dispatch.yaml）：
  - signal_dispatch_hint      : 调度建议报告的行文与安全约束指令
  - signal_constraint_hint    : 配时调整必须校验的规范约束（GB 14886）
"""
import logging
from typing import Any, Dict, List, Tuple

from src.skills.base_skill import BaseSkill, load_prompts

logger = logging.getLogger(__name__)


class SignalDispatchSkill(BaseSkill):
    """信号优化与调度指挥技能。

    execute() 在 v3_engine_router_node 执行完信号类工具后调用，
    将优化建议数据与安全约束指令打包为 signal_dispatch_hint，
    注入 interpreter_generator 的 system prompt，确保报告包含
    最小绿灯校验、行人过街约束和应急优先原则。
    """

    name = "signal_dispatch"
    tools = [
        "fetch_signal_optimization_suggestion",
        "fetch_signal_timing",
        "fetch_corridor_congestion",
    ]
    prompt_keys = ["signal_dispatch_hint", "signal_constraint_hint"]
    description = "信号优化与调度指挥（配时建议、绿波协调、应急调度，附安全约束校验）"

    def execute(
        self,
        tool_results: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理信号类工具结果，返回 AgentState 更新（signal_dispatch_hint）。

        Args:
            tool_results: [(tool_name, result_dict, args_dict), ...]
            state: 当前 AgentState（只读）

        Returns:
            AgentState 更新字典，无信号类结果时返回空
        """
        suggestions: List[Dict[str, Any]] = []
        timing_plans: List[Dict[str, Any]] = []
        for name, result, _args in tool_results:
            if "error" in result:
                continue
            if name == "fetch_signal_optimization_suggestion":
                suggestions.append(result)
            elif name in ("fetch_signal_timing", "fetch_corridor_congestion"):
                timing_plans.append(result)

        if not suggestions and not timing_plans:
            return {}

        prompts = load_prompts()
        dispatch_hint = prompts.get("signal_dispatch_hint", {}).get("system", "")
        constraint_hint = prompts.get("signal_constraint_hint", {}).get("system", "")

        # 收集本次建议中涉及的约束校验结果，供报告引用
        constraint_notes: List[str] = []
        for sug in suggestions:
            for item in sug.get("suggestions", []):
                check = item.get("constraint_check", "")
                if check:
                    constraint_notes.append(f"- {item.get('type', '')}: {check}")

        suffix_parts = [p for p in (dispatch_hint, constraint_hint) if p]
        if constraint_notes:
            suffix_parts.append(
                "本次建议的规范校验结果（必须在报告中明确说明）：\n" + "\n".join(constraint_notes)
            )
        system_suffix = "\n\n".join(suffix_parts)

        logger.info(
            f"SignalDispatchSkill 注入调度约束提示（{len(suggestions)} 组建议 / {len(timing_plans)} 份配时）"
        )
        return {
            "signal_dispatch_hint": {
                "system_suffix": system_suffix,
                "suggestion_count": len(suggestions),
                "timing_count": len(timing_plans),
            }
        }
