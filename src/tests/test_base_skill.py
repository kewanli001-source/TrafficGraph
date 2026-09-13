"""test_base_skill — BaseSkill 抽象基类契约测试

所属层：tests
依赖：pytest, unittest.mock
对接算法层：N/A

测试范围：
  - BaseSkill 不可直接实例化（abstract）
  - 子类未实现 execute() 时 TypeError
  - before/after_execute 钩子默认行为
  - has_tool / matches_tool_results 辅助方法
  - get_skill / get_matched_skills 工厂函数
"""
from typing import Any, Dict, List, Tuple

import pytest

from src.skills.base_skill import BaseSkill


# ---------------------------------------------------------------------------
# 测试用子类
# ---------------------------------------------------------------------------


class _ConcreteSkill(BaseSkill):
    """用于测试的具体 Skill 子类"""
    name = "test_skill"
    tools = ["test_tool_a", "test_tool_b"]
    prompt_keys = ["test_prompt"]
    description = "测试用技能"

    def execute(self, tool_results, state):
        return {"test_field": "updated"}


class _EmptySkill(BaseSkill):
    """未实现 execute 的子类"""
    name = "empty"
    tools = []
    prompt_keys = []
    description = "空技能"


# ---------------------------------------------------------------------------
# BaseSkill 抽象契约
# ---------------------------------------------------------------------------


class TestBaseSkillAbstract:
    """BaseSkill 不可直接实例化"""

    def test_cannot_instantiate_base_skill(self):
        """直接实例化 BaseSkill 应抛出 TypeError"""
        with pytest.raises(TypeError):
            BaseSkill()

    def test_subclass_without_execute_raises(self):
        """子类未实现 execute() 时不可实例化"""
        with pytest.raises(TypeError):
            _EmptySkill()


# ---------------------------------------------------------------------------
# 具体子类行为
# ---------------------------------------------------------------------------


class TestConcreteSkill:
    """具体 Skill 子类功能测试"""

    def test_execute_returns_updates(self):
        """execute() 返回 AgentState 更新字典"""
        skill = _ConcreteSkill()
        result = skill.execute([("test_tool_a", {}, {})], {})
        assert result == {"test_field": "updated"}

    def test_has_tool(self):
        """has_tool() 判断工具是否属于本 Skill"""
        skill = _ConcreteSkill()
        assert skill.has_tool("test_tool_a") is True
        assert skill.has_tool("test_tool_b") is True
        assert skill.has_tool("unknown_tool") is False

    def test_matches_tool_results(self):
        """matches_tool_results() 判断本轮工具调用是否匹配"""
        skill = _ConcreteSkill()
        assert skill.matches_tool_results([("test_tool_a", {}, {})]) is True
        assert skill.matches_tool_results([("unknown", {}, {})]) is False
        assert skill.matches_tool_results([]) is False

    def test_before_execute_default(self):
        """before_execute 默认返回原 state"""
        skill = _ConcreteSkill()
        state = {"user_input": "test"}
        assert skill.before_execute(state) is state

    def test_after_execute_default(self):
        """after_execute 默认返回原 updates"""
        skill = _ConcreteSkill()
        updates = {"field": "value"}
        assert skill.after_execute({}, updates) is updates

    def test_meta_attributes(self):
        """元信息属性正确"""
        skill = _ConcreteSkill()
        assert skill.name == "test_skill"
        assert skill.tools == ["test_tool_a", "test_tool_b"]
        assert skill.prompt_keys == ["test_prompt"]
        assert skill.description == "测试用技能"


# ---------------------------------------------------------------------------
# 注册表工厂函数
# ---------------------------------------------------------------------------


class TestSkillRegistry:
    """get_skill / get_matched_skills 工厂函数测试"""

    def test_get_skill_returns_instance(self):
        """get_skill() 返回 BaseSkill 实例"""
        from src.skills import get_skill
        skill = get_skill("traffic_expert")
        assert skill is not None
        assert isinstance(skill, BaseSkill)
        assert skill.name == "traffic_expert"

    def test_get_skill_unknown_returns_none(self):
        """get_skill() 未知名称返回 None"""
        from src.skills import get_skill
        assert get_skill("nonexistent") is None

    def test_get_matched_skills(self):
        """get_matched_skills() 根据工具名返回匹配的 Skill 列表"""
        from src.skills import get_matched_skills
        matched = get_matched_skills(["query_traffic_knowledge"])
        names = [s.name for s in matched]
        assert "traffic_expert" in names

    def test_get_matched_skills_multiple(self):
        """多工具调用匹配多个 Skill"""
        from src.skills import get_matched_skills
        matched = get_matched_skills([
            "query_traffic_knowledge",
            "fetch_signal_optimization_suggestion",
        ])
        names = [s.name for s in matched]
        assert "traffic_expert" in names
        assert "ui_router" in names

    def test_get_matched_skills_no_match(self):
        """无匹配工具时返回空列表"""
        from src.skills import get_matched_skills
        matched = get_matched_skills(["unknown_tool"])
        assert matched == []

    def test_registry_values_are_instances(self):
        """SKILL_REGISTRY 中的值都是 BaseSkill 实例"""
        from src.skills import SKILL_REGISTRY
        for name, skill in SKILL_REGISTRY.items():
            assert isinstance(skill, BaseSkill), f"{name} 不是 BaseSkill 实例"

    def test_all_skills_have_execute(self):
        """所有注册 Skill 都有 execute 方法"""
        from src.skills import SKILL_REGISTRY
        for name, skill in SKILL_REGISTRY.items():
            assert hasattr(skill, "execute"), f"{name} 缺少 execute()"
            assert callable(skill.execute), f"{name}.execute 不可调用"
