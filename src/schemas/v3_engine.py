"""v3_engine — 数据模型定义

所属层：schemas
依赖：pydantic
对接算法层：N/A（数据结构定义）
"""
from typing import List
from pydantic import BaseModel, Field


class IntentItem(BaseModel):
    """单条用户意图（Phase 7: 多意图识别）"""
    id: int = Field(..., description="意图序号（从 1 开始）")
    description: str = Field(..., description="意图描述")
    category: str = Field(default="general", description="意图类别：signal / incident / monitor / dispatch / knowledge / export / memory / general")
    depends_on: List[int] = Field(default_factory=list, description="依赖的意图 ID 列表")
    status: str = Field(default="pending", description="执行状态：pending / running / done / failed")


class DispatchConstraint(BaseModel):
    """指挥调度意图解析结果 — 调度约束边界"""
    time_window: str = ""
    priority_level: str = "Normal"
    optimization_goal: str = "delay"
    extra_constraints: dict = {}


class TrafficKnowledgeResult(BaseModel):
    """交通专业知识库 RAG 检索结果"""
    query: str
    results: List[str]          # Top-K 相关 Q&A 文本
    system_types: List[str]     # 对应的场景类型（signal/corridor/standard/incident/dispatch/general）
    distances: List[float]      # 相似度距离（越小越相关）
    low_confidence: bool = False  # top-1 distance > 阈值时为 True，触发拒答
    source_snippets: List[str] = []  # 检索片段摘要（≤50字），供引用来源标注
