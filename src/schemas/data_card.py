"""data_card — 数据卡片 Pydantic 模型（表格 + 下载信息）

所属层：schemas
依赖：pydantic
对接算法层：N/A

Phase 6 数据导出：export_data_table 工具生成 DataCard，经 SSE event: data_card
下发前端，前端渲染表格 + 下载按钮。DataCard 为通用结构，可承载任意列/行数据，
新增可导出数据类型无需改动本模型。
"""
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class ColumnDef(BaseModel):
    """表格列定义。

    由 LLM 在调用 export_data_table 时给出，决定 CSV 表头与取值字段。
    """

    key: str = Field(..., description="行数据中对应字段名（snake_case，如 total_consumption_kwh）")
    label: str = Field(..., description="表头显示文本（中文，如 平均车速）")
    unit: str = Field(default="", description="单位（如 kWh / ℃），可为空")


class TableData(BaseModel):
    """表格数据：列定义 + 行数据。"""

    columns: List[ColumnDef] = Field(default_factory=list, description="列定义列表")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="行数据，每行为 {key: value}")


class DownloadInfo(BaseModel):
    """下载信息：指向 /export/{task_id} 端点。"""

    format: str = Field(default="csv", description="文件格式：csv")
    filename: str = Field(..., description="下载文件名（如 flow_2026-09-13.csv）")
    url: str = Field(..., description="下载 URL（/export/{task_id}）")
    task_id: str = Field(..., description="导出任务 ID（uuid4）")


class ChartSeries(BaseModel):
    """图表数据系列。"""

    key: str = Field(..., description="行数据中对应字段名")
    label: str = Field(..., description="系列显示名称")
    color: str = Field(default="#159a73", description="系列颜色（十六进制）")


class ChartDefinition(BaseModel):
    """通用图表定义。"""

    type: Literal["bar", "line", "donut"] = Field(default="bar", description="图表类型")
    title: str = Field(..., description="图表标题")
    x_key: str = Field(..., description="横轴或分类字段")
    series: List[ChartSeries] = Field(..., min_length=1, description="数据系列")
    unit: str = Field(default="", description="数值单位")
    orientation: Literal["vertical", "horizontal"] = Field(
        default="vertical",
        description="柱状图方向，折线图和环形图忽略此字段",
    )


class DataCard(BaseModel):
    """数据卡片：前端渲染表格 + 下载按钮。

    同一张卡片可同时承载表格、图表和 CSV 下载。
    """

    card_type: str = Field(default="table", description="卡片类型：table")
    title: str = Field(..., description="卡片标题（如 世纪大道近7天流量明细）")
    table: TableData = Field(..., description="表格数据")
    charts: List[ChartDefinition] = Field(default_factory=list, description="可视化图表定义")
    download: DownloadInfo = Field(..., description="下载信息")


class ReportExportRequest(BaseModel):
    """前端直接生成报告请求。"""

    title: str = Field(..., description="报告标题")
    columns: List[ColumnDef] = Field(default_factory=list, description="表格列定义")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="表格数据")
    charts: List[ChartDefinition] = Field(default_factory=list, description="图表定义")
    filename: str = Field(default="", description="CSV 文件名")
