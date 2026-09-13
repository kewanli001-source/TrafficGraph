"""skills — 业务技能注册表

所属层：skills（Tools 之上的业务推理层）
依赖：src.skills.*
对接算法层：N/A（由各 Skill 内部编排 Tools）

Skills 与 Tools 的分工：
  Tools = 原子执行层（确定性函数，强类型 I/O，不含 Prompt）
  Skills = 业务推理层（专属 Prompt + SOP 流程 + Tools 编排）

cognitive_parser 通过 SKILL_REGISTRY 获取技能描述，
决定激活哪个 Skill，再由 Skill 内部编排具体 Tools。
v3_engine_router 通过 get_matched_skills() 统一调度，不依赖具体子类。
"""
from typing import Dict, Optional

from src.skills.base_skill import BaseSkill
from src.skills.traffic_expert_skill import TrafficExpertSkill
from src.skills.signal_dispatch_skill import SignalDispatchSkill
from src.skills.ui_router_skill import UIRouterSkill
from src.skills.v3_interpreter_skill import V3InterpreterSkill

# 技能注册表：key = 技能名，value = 技能实例
SKILL_REGISTRY: Dict[str, BaseSkill] = {
    "traffic_expert": TrafficExpertSkill(),
    "signal_dispatch": SignalDispatchSkill(),
    "ui_router": UIRouterSkill(),
    "v3_interpreter": V3InterpreterSkill(),
}

# 供 cognitive_parser 注入 system prompt 的技能描述菜单
SKILL_DESCRIPTIONS = {
    "traffic_expert": "交通专家问答（信号配时、绿波协调、交通流理论、事件处置、规范标准）",
    "signal_dispatch": "信号优化与调度指挥（配时建议、绿波协调、应急调度，附安全约束校验）",
    "ui_router": "指挥中心页面查询与跳转（实时路况、事件、信号，下发页面跳转信号）",
    "v3_interpreter": "数据解读与报告生成（将工具返回数据转化为 Markdown 报告）",
}


def get_skill(name: str) -> Optional[BaseSkill]:
    """工厂函数：按名称获取 Skill 实例。

    Args:
        name: 技能名（对应 SKILL_REGISTRY 的 key）

    Returns:
        BaseSkill 实例，不存在时返回 None
    """
    return SKILL_REGISTRY.get(name)


def get_matched_skills(tool_names: list) -> list:
    """根据本轮工具调用，返回匹配的 Skill 实例列表。

    Args:
        tool_names: 本轮 LLM 调用的工具名列表

    Returns:
        匹配的 BaseSkill 实例列表
    """
    matched = []
    for skill in SKILL_REGISTRY.values():
        if any(skill.has_tool(t) for t in tool_names):
            matched.append(skill)
    return matched
