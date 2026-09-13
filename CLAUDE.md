# CLAUDE.md — TrafficGraph 工程规范

> TrafficGraph 是上海市智慧交通指挥 Agent。所有运行代码、配置、Prompt、
> Schema、测试和新增文件必须使用交通领域命名。

## 项目定位

- Agent 是交通指挥领域的编排层，负责意图理解、工具调度和研判解释。
- 实时状态来自 `src/tools/traffic_backend.py` 和 `src/sim/`。
- 专业知识来自 `data/traffic_qa_corpus.jsonl` 和本地 ChromaDB。
- Agent 只提供查询、分析和建议，不直接修改信号配时、发布管制或执行调度。

## 架构边界

1. `src/sim/` 负责确定性交通仿真，不依赖 LLM。
2. `src/tools/` 负责原子工具，必须使用强类型 Schema，并捕获异常返回 `{"error": ...}`。
3. `src/graph/` 负责 LangGraph 状态、节点、边和图构建。
4. `src/skills/` 负责组合工具并注入交通专家、信号安全和页面跳转提示。
5. Prompt 统一位于 `src/config/prompts/`，禁止在节点中硬编码 Prompt。
6. 路由统一位于 `config/routes.yaml`，路网统一位于 `config/traffic_network.yaml`。
7. 前后端上下文使用 `area_id`，不使用旧的站点命名。

## 命名规范

- 领域术语：traffic、intersection、corridor、district、signal、incident、dispatch。
- 文件、函数、变量：`snake_case`。
- 类：`PascalCase`。
- 工具：交通数据使用 `fetch_*`，知识检索使用 `query_traffic_knowledge`。
- 新增文件名、类名、函数名、字段名和配置项必须直接表达交通业务含义。

## 代码规范

- 生产 Python 文件必须包含模块 docstring。
- Public 函数必须有类型标注和 Args/Returns/Raises 文档。
- 使用绝对导入：`from src...`。
- Pydantic 模型放在 `src/schemas/`。
- 动态配置与静态 Prompt 分离。

## 测试规范

```powershell
python -m pytest src/tests -q
```

- 新工具必须测试正常输入、边界值和错误输入。
- 修改交通数据模型时必须同步后端工具、前端消费和测试。
- RAG 修改必须验证语料解析、向量器和检索置信度。

## Prompt 规范

- `main_graph.yaml`：主图意图和报告规则。
- `ui_router.yaml`：交通页面跳转。
- `traffic_expert.yaml`：交通知识库问答、拒答和引用。
- `signal_dispatch.yaml`：信号优化和安全约束。
- `_shared.yaml`：共享回答原则。

修改 Prompt 后必须确认 YAML 可加载，并运行 Agent 相关测试。
