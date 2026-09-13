"""traffic_expert_skill — 交通专家问答技能

所属层：skills
依赖：src.tools.query_traffic_knowledge, src.config.settings
对接算法层：N/A（ChromaDB RAG）

SOP：
  1. 调用 query_traffic_knowledge 检索相关 Q&A
  2. 若 low_confidence=True → 触发拒答（traffic_refusal Prompt）
  3. 否则综合检索结果生成回答，末尾附引用来源（traffic_citation_format Prompt）

Prompt keys（src/config/prompts/traffic_expert.yaml）：
  - traffic_expert          : 领域专家角色设定
  - traffic_refusal         : 低置信度拒答指令
  - traffic_citation_format : 引用来源格式要求
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.skills.base_skill import BaseSkill, load_prompts

logger = logging.getLogger(__name__)


class TrafficExpertSkill(BaseSkill):
    """交通专家问答技能。

    execute() 在 v3_engine_router_node 执行完 query_traffic_knowledge 后调用，
    根据检索结果的 low_confidence 标志决定后续行为：
      - low_confidence=True  → 注入拒答 Prompt，截断检索内容
      - low_confidence=False → 注入引用格式 Prompt，传递 source_snippets
    """

    name = "traffic_expert"
    tools = ["query_traffic_knowledge"]
    prompt_keys = ["traffic_expert", "traffic_refusal", "traffic_citation_format"]
    description = "交通专家问答（信号配时、绿波协调、交通流理论、事件处置、规范标准）"

    def execute(
        self,
        tool_results: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 query_traffic_knowledge 工具结果，返回 AgentState 更新。

        根据检索结果的 low_confidence 标志决定后续行为：
          - low_confidence=True  → 注入拒答 Prompt，截断检索内容
          - low_confidence=False → 注入引用格式 Prompt，传递 source_snippets

        Args:
            tool_results: [(tool_name, result_dict, args_dict), ...]
            state: 当前 AgentState（只读）

        Returns:
            AgentState 更新字典（traffic_context_hint）
        """
        # 找到 query_traffic_knowledge 的结果
        knowledge_result: Optional[Dict] = None
        for name, result, _args in tool_results:
            if name == "query_traffic_knowledge" and "error" not in result:
                knowledge_result = result
                break

        if knowledge_result is None:
            return {"traffic_context_hint": {"system_suffix": "", "context_override": None, "low_confidence": False}}

        prompts = load_prompts()
        low_confidence = knowledge_result.get("low_confidence", False)
        source_snippets = knowledge_result.get("source_snippets", [])

        if low_confidence:
            # 拒答模式：注入 traffic_refusal prompt，清空检索内容
            refusal_prompt = prompts.get("traffic_refusal", {}).get("system", "")
            logger.info("交通知识检索低置信度，触发拒答")
            return {
                "traffic_context_hint": {
                    "system_suffix": f"\n\n{refusal_prompt}",
                    "context_override": {"low_confidence": True, "query": knowledge_result.get("query", "")},
                    "low_confidence": True,
                }
            }

        # 正常模式：注入引用格式 prompt + source_snippets
        citation_prompt = prompts.get("traffic_citation_format", {}).get("system", "")
        logger.info(f"交通知识检索正常，{len(knowledge_result.get('results', []))} 条结果，注入引用格式")
        suffix = (
            f"\n\n{citation_prompt}\n\n可用的引用来源摘要：\n" +
            "\n".join(f"- {s}" for s in source_snippets)
            if source_snippets
            else f"\n\n{citation_prompt}"
        )
        return {
            "traffic_context_hint": {
                "system_suffix": suffix,
                "context_override": None,
                "low_confidence": False,
            }
        }
