# TrafficGraph 团队协作指南

## 分支

- `main`：稳定可运行版本。
- `feat/traffic-*`：交通工具、图谱、前端或领域功能。
- `fix/traffic-*`：交通数据和交互缺陷修复。

## 提交范围

| 标签 | 范围 |
|------|------|
| `[tools]` | `src/tools/` |
| `[graph]` | `src/graph/` |
| `[schemas]` | `src/schemas/` |
| `[config]` | `config/`、`src/config/` |
| `[frontend]` | `src/frontend/` |
| `[knowledge]` | `src/knowledge/`、`src/pipelines/`、语料 |
| `[test]` | `src/tests/` |
| `[docs]` | README、PRD、AI_CONTEXT、CHANGELOG |

提交示例：

```text
[tools] 增加交通信号优化工具契约
[frontend] 接入交通 SSE 工具轨迹与数据卡片
[knowledge] 扩充事件处置交通语料
```

## 开发约束

1. 不把实时业务数据硬编码到 Prompt。
2. 所有新增命名必须符合交通指挥领域。
3. 工具必须通过 `TOOL_REGISTRY` 和 `TOOL_SCHEMAS` 注册。
4. Prompt 修改与代码修改分开提交。
5. RAG 语料变更后运行 `python -m src.pipelines.rag_ingest --rebuild`。
6. 提交前运行 `python -m pytest src/tests -q`。

## Review 清单

- 工具错误是否被捕获并返回标准 error。
- 是否使用 `area_id` 而不是旧上下文命名。
- 信号建议是否带安全约束。
- 前端是否处理 `text/action/data_card/error`。
- 新交通数据模型是否同步 API、前端和测试。
