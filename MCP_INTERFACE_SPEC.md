# TrafficGraph 数据接口规范

> 当前版本使用本地 Python Tools 调用 TrafficSim；真实部署可将同一工具契约
> 映射为 REST 或 MCP Server。

## 1. 统一约定

- 所有工具返回 JSON 对象。
- 成功结果符合 `src/schemas/traffic_data.py`。
- 失败返回 `{"error": "<tool_name>: <message>"}`。
- 日期参数使用 `YYYY-MM-DD`，时刻参数使用 ISO8601。
- 区域上下文使用 `area_id`。
- Agent 只消费工具结果，不在节点内复制仿真或业务计算。

## 2. 数据工具

| 工具 | 关键输入 | 返回模型 |
|------|----------|----------|
| `fetch_city_overview` | `date?` | `CityOverview` |
| `fetch_intersection_status` | `intersection_id, date?` | `IntersectionStatus` |
| `fetch_corridor_congestion` | `corridor_id, date?` | `CorridorCongestion` |
| `fetch_district_congestion` | `district_id, date?` | `DistrictCongestion` |
| `fetch_signal_timing` | `intersection_id, plan_type?` | `SignalTimingPlan` |
| `fetch_signal_optimization_suggestion` | `intersection_id? / corridor_id?` | `SignalOptimizationSuggestion` |
| `fetch_flow_history` | `intersection_id? / corridor_id?, start_date?, end_date?` | `FlowHistory` |
| `fetch_active_incidents` | `severity?` | `IncidentList` |
| `fetch_incident_history` | `start_date?, end_date?` | `IncidentList` |
| `fetch_camera_list` | `intersection_id? / corridor_id?` | `CameraList` |
| `fetch_dispatch_records` | `start_date?, end_date?, incident_id?` | `DispatchList` |
| `fetch_event_alarm_history` | `start_date?, end_date?` | `AlarmList` |

## 3. 知识、导航与导出

| 工具 | 关键输入 | 返回 |
|------|----------|------|
| `query_traffic_knowledge` | `question` | `TrafficKnowledgeResult` |
| `navigate_to_page` | `route, params?` | `UIAction` |
| `export_data_table` | `title, columns, rows, filename?` | `DataCard` |
| `search_memory` | `query, area_id, scope, entity_id` | `MemorySearchResult` |
| `search_relevant_memory` | `query, area_id, thread_id` | `MemorySearchResult` |
| `save_memory` | `content, area_id, metadata` | `MemoryWriteResult` |

## 4. TrafficSim 适配器

默认：

```env
TRAFFIC_BACKEND=sim
```

真实后端：

```env
TRAFFIC_BACKEND=real
TRAFFIC_API_BASE_URL=https://your-traffic-api.example.com
```

真实适配层未实现时返回明确错误，不回退到随机假数据。

## 5. SSE 契约

`POST /stream` 事件：

- `thinking`
- `tool_call`
- `tool_result`
- `rag_sources`
- `intent_plan`
- `text`
- `action`
- `data_card`
- `error`
- `done`

## 6. 安全约束

- 信号建议必须包含 Webster 依据和 GB 14886 安全校验。
- 优化建议不得压缩黄灯和清空时间。
- 事件处置、应急接管、强制诱导和配时编辑属于受限操作。
