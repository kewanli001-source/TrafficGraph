"""action_agent — Action Agent 请求、页面上下文与 UI 动作模型

所属层：schemas
依赖：pydantic
对接算法层：N/A
"""
from typing import Optional
from pydantic import BaseModel, Field


class PageContext(BaseModel):
    """前端页面上下文，由前端在每次请求时注入。

    字段会随前端页面分析逐步扩展。params 承载页面级运行时数据
    （如筛选条件、选中的设备 ID），新增字段直接追加，无需破坏现有结构。
    """
    current_route: str = Field(default="/", description="当前页面路由")
    area_id: Optional[str] = Field(default=None, description="当前辖区、路口或线路上下文 ID")
    params: dict = Field(default_factory=dict, description="页面级运行时参数（筛选条件、选中设备等）")
    meta: dict = Field(default_factory=dict, description="扩展元数据，后续前端分析追加字段用此入口")


class ActionAgentInput(BaseModel):
    """POST /stream 请求体。"""
    user_input: str = Field(..., description="用户输入文本")
    page_context: Optional[PageContext] = Field(default=None, description="前端页面上下文")
    thread_id: Optional[str] = Field(default=None, description="会话线程 ID，用于 LangGraph checkpoint 隔离")


class UIAction(BaseModel):
    """前端可消费的 UI 动作信号。

    当前支持页面跳转；后续前端页面分析后，可扩展子页面跳转、
    面包屑导航、高亮组件、打开面板等动作。新增字段直接追加，
    params 承载路由参数，meta 承载 UI 层元数据。
    """
    type: str = Field(default="navigate", description="动作类型：navigate / highlight / open_panel（后续前端分析追加）")
    route: str = Field(..., description="目标路由，子页面用 /parent/child 形式，始终以 / 开头")
    name: str = Field(default="", description="页面名称（如'信号优化'、'路口监控'），从 routes.yaml 自动填充")
    params: dict = Field(default_factory=dict, description="路由参数（如 area_id, intersection_id, corridor_id）")
    meta: dict = Field(default_factory=dict, description="UI 元数据（面包屑、查询参数、高亮目标等，后续前端分析追加）")
