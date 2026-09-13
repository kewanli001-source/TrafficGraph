"""v3_interpreter_skill — 数据解读与报告生成技能

所属层：skills
依赖：无（纯 LLM 推理，不调用 Tools）
对接算法层：N/A（接收其他 Skill 的工具结果，生成报告）

SOP：
  1. 接收交通数据、知识与调度约束工具结果
  2. 按数据类型选择报告模板
  3. 生成包含三个维度的 Markdown 报告：
     - 当前态势与拥堵原因
     - 信号/调度建议及预期收益
     - 安全边界与规范约束

此 Skill 是 interpreter_generator_node 的业务逻辑抽象，
将 context 拼装逻辑从节点代码移入此处，节点只负责调用。

Prompt keys（src/config/prompts/main_graph.yaml）：
  - interpreter_generator : 报告生成指令（已有）
"""
from typing import Any, Dict, List, Tuple

from src.skills.base_skill import BaseSkill


class V3InterpreterSkill(BaseSkill):
    """数据解读与报告生成技能。

    当前为骨架占位，随 Phase 2-4 推进逐步将
    interpreter_generator_node 中的 context 拼装逻辑迁移至此。
    """

    name = "v3_interpreter"
    tools = []  # 纯 LLM 推理，不调用 Tools
    prompt_keys = ["interpreter_generator"]
    description = "数据解读与报告生成（将工具返回数据转化为 Markdown 报告）"

    def execute(
        self,
        tool_results: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """报告生成编排逻辑。当前返回空更新，等后续迁移 interpreter 逻辑。"""
        return {}
