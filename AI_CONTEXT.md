# AI_CONTEXT — TrafficGraph 项目状态

**当前阶段**：交通领域替换、13 个交通工具链、交通 RAG、Web 指挥台和测试迁移均已完成。

**最后更新**：2026-09-13

## 1. 项目定位

TrafficGraph 是上海市智慧交通指挥 Agent，使用 LangGraph 完成：

1. 自然语言意图识别。
2. 交通数据、知识检索和页面跳转工具调度。
3. 多意图执行与研判报告生成。
4. 通过 SSE 向 Web 控制台下发文本、工具状态、跳转动作和数据卡片。

## 2. 运行入口

- Web 指挥台：`http://127.0.0.1:8000/`
- OpenAPI：`http://127.0.0.1:8000/docs`
- 同步调用：`POST /invoke`
- 流式调用：`POST /stream`
- 态势快照：`GET /dashboard`
- CSV 下载：`GET /export/{task_id}`

## 3. 核心目录

| 路径 | 职责 |
|------|------|
| `config/traffic_network.yaml` | 上海市路网、信号模板、摄像头和事件脚本 |
| `config/routes.yaml` | 指挥中心页面和工具关联 |
| `src/sim/` | TrafficSim 路网加载与确定性仿真 |
| `src/tools/traffic_backend.py` | 12 个交通数据工具适配器 |
| `src/tools/query_traffic_knowledge.py` | 交通知识库检索 |
| `src/knowledge/` | 离线 hashing / 可选 BGE 向量器 |
| `src/graph/` | AgentState、LangGraph 节点、条件和构建 |
| `src/skills/` | 交通专家、信号调度、UI Router、报告生成 |
| `src/frontend/web/` | 高级 Web 指挥台 |
| `src/frontend/streamlit_app.py` | 可选 Streamlit 演示 |
| `data/traffic_qa_corpus.jsonl` | 交通专业 Q&A 语料 |

## 4. 工具注册表

交通数据工具：

| 工具 | 用途 |
|------|------|
| `fetch_city_overview` | 全市态势与拥堵 Top5 |
| `fetch_intersection_status` | 单路口运行状态 |
| `fetch_corridor_congestion` | 干线拥堵与绿波 |
| `fetch_district_congestion` | 辖区指数与排名 |
| `fetch_signal_timing` | 路口配时方案 |
| `fetch_signal_optimization_suggestion` | Webster 优化建议 |
| `fetch_flow_history` | 路口/干线逐时流量 |
| `fetch_active_incidents` | 活跃事件 |
| `fetch_incident_history` | 历史事件 |
| `fetch_camera_list` | 摄像头清单 |
| `fetch_dispatch_records` | 派单与调度记录 |
| `fetch_event_alarm_history` | 接处警记录 |

其他工具：

- `query_traffic_knowledge`
- `navigate_to_page`
- `export_data_table`
- `search_memory`
- `search_relevant_memory`
- `save_memory`

## 5. 记忆与知识

- L1：LangGraph checkpoint，按 `thread_id` 隔离。
- L2：长期记忆，按 `trafficgraph/env/area_id/agent_id/scope/entity_id` 隔离。
- L3：ChromaDB `traffic_qa`，默认离线 hashing，支持 BGE。
- 临时设备/事件状态必须带 TTL 或 `valid_until`。

## 6. 最近变更

| 日期 | 摘要 |
|------|------|
| 2026-09-13 | 完成交通领域全量替换，删除旧业务模块 |
| 2026-09-13 | 完成 12 个交通数据工具、共享 Schema 和 TrafficSim |
| 2026-09-13 | 完成交通 Prompt、`area_id`、记忆和 API 迁移 |
| 2026-09-13 | 新增高级 Web 指挥台与 `/dashboard` 聚合接口 |
| 2026-09-13 | 新增 57 条交通语料、离线向量器和 RAG 入库 |
| 2026-09-13 | 测试迁移完成：`98 passed, 1 skipped` |
