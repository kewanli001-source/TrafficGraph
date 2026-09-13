# TrafficGraph

TrafficGraph 是上海市智慧交通指挥 Agent。它基于 LangGraph 完成意图理解、
工具调度和研判报告生成，内置 12 个交通数据工具、TrafficSim 确定性仿真引擎、
交通知识库 RAG、长期记忆和面向指挥中心的 Web 控制台。

完整的比赛启动、配置、演示和技术说明见：
[`docs/COMPETITION_GUIDE.md`](docs/COMPETITION_GUIDE.md)。

完整的项目架构、功能、接口和配置见：
[`项目说明书.md`](项目说明书.md)。

## 功能

- 全市态势：拥堵指数、平均车速、峰值等级、拥堵 Top5、活跃事件
- 路口诊断：LOS、饱和度、排队、延误、当前相位和事件影响
- 信号协同：配时查询、Webster 周期建议、绿信比和绿波相位差优化
- 事件处置：事故、抛锚、施工、临时管制、派单与接处警记录
- 数据研判：路口/干线逐时流量历史、表格与图表报告、CSV 下载
- 专业知识：交通工程、信号控制、GB 14886 和处置 SOP 的交通知识库 RAG
- 指挥 Web 控制台：实时路网态势、事件台、信号与辖区面板、SSE Agent Copilot

## 环境要求

- Python 3.11 或更高版本
- Windows、Linux 或 macOS
- 可选：DeepSeek、OpenAI 或 Anthropic API Key，用于 Agent 对话

仪表盘、交通数据工具、RAG 检索和导出功能不依赖大模型 Key。

## 快速运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

如果本机已有 Claude Code 的 `~/.claude/settings.json`，可只在本机生成本地
Agent 配置，不把 Token 写入仓库：

```powershell
.\scripts\setup_local_llm.ps1
```

`.env` 与 `.claude/settings.local.json` 均已加入 `.gitignore`。不要提交、截图
或粘贴其中的密钥；密钥一旦对外暴露，应立即在服务控制台轮换。

编辑 `.env`，至少确认：

```env
TRAFFIC_BACKEND=sim
TRAFFIC_EMBEDDING_BACKEND=hashing
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的密钥
```

初始化交通知识库：

```powershell
python -m src.pipelines.rag_ingest --rebuild
```

启动 Web 指挥台和 API：

```powershell
python run.py
```

打开：

- Web 指挥台：`http://127.0.0.1:8000/`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

生产模式：

```powershell
python run.py --prod
```

可选 Streamlit 演示前端：

```powershell
streamlit run src/frontend/streamlit_app.py
```

## Agent API

同步调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/invoke `
  -ContentType "application/json" `
  -Body '{"user_input":"现在全市哪里最堵？","page_context":{"current_route":"/command/dashboard","area_id":"DIST-CBD"}}'
```

流式 SSE：

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/stream `
  -H "Content-Type: application/json" `
  -d "{\"user_input\":\"分析 JK-SJ03 并给出配时建议\",\"page_context\":{\"current_route\":\"/intersection/monitor\",\"area_id\":\"DIST-CBD\"}}"
```

SSE 事件包括 `thinking`、`tool_call`、`tool_result`、`rag_sources`、
`intent_plan`、`text`、`action`、`data_card`、`error` 和 `done`。
当前工作区可点击“导出当前视图”生成表格、柱状图/折线图/环形图和 CSV。

## 交通数据源

### 仿真模式

默认 `TRAFFIC_BACKEND=sim`，使用 `config/traffic_network.yaml` 和
`src/sim/` 生成确定性仿真数据。可通过 `TRAFFIC_SIM_CLOCK` 固定演示时间。

### 真实后端模式

设置：

```env
TRAFFIC_BACKEND=real
TRAFFIC_API_BASE_URL=https://your-traffic-api.example.com
```

`src/tools/traffic_backend.py` 会切换到真实 REST 适配器。真实接口未实现前，
工具会明确返回错误，不会伪造实时数据。

## RAG 向量后端

默认使用完全离线的确定性 hashing 向量器：

```env
TRAFFIC_EMBEDDING_BACKEND=hashing
```

语料文件为 `data/traffic_qa_corpus.jsonl`，入库目录为
`data/traffic_knowledge/`，集合名为 `traffic_qa`。

如需 BGE 检索质量：

```env
TRAFFIC_EMBEDDING_BACKEND=bge
```

该模式首次运行需要下载 `BAAI/bge-small-zh-v1.5`，网络不可用时应保持
`hashing`。

## 项目结构

```text
TrafficGraph/
├── config/
│   ├── traffic_network.yaml     # 上海市路网、信号方案、事件脚本
│   ├── routes.yaml              # 指挥中心前端路由注册表
│   └── agent_config.yaml        # 模型、记忆、RAG 和 API 配置
├── data/
│   └── traffic_qa_corpus.jsonl  # 交通专业知识语料
├── src/
│   ├── config/prompts/          # 主图、路由、交通专家、信号调度 Prompt
│   ├── frontend/
│   │   ├── web/                 # 高级指挥 Web 控制台
│   │   └── streamlit_app.py     # 可选 Streamlit 演示
│   ├── graph/                   # LangGraph 状态、节点、路由和构建
│   ├── knowledge/               # 离线/BGE 向量器适配
│   ├── memory/                  # L2 长期记忆
│   ├── pipelines/rag_ingest.py  # 交通语料入库
│   ├── schemas/                 # Agent、交通数据和记忆模型
│   ├── sim/                     # TrafficSim 路网模型与仿真引擎
│   ├── skills/                  # 交通专家、信号调度、UI Router
│   ├── tests/                   # 单元测试与集成测试
│   └── tools/                   # 12 个交通数据工具、RAG、导出、记忆
└── run.py                       # API + Web 控制台启动入口
```

## 测试

```powershell
python -m pytest src/tests -q
```

当前测试覆盖交通数据工具、路由、记忆隔离、多意图、SSE 动作、CSV 导出、
离线向量器和交通语料解析。

## 安全边界

- Agent 只能查询、分析和建议，不能直接修改信号配时、发布管制或强制诱导。
- 配时建议必须保留最小绿灯、行人过街、黄灯清空和协调组同步约束。
- 受限页面和应急操作需要具备权限的值班人员审批。
