# TrafficGraph 智慧交通指挥 Agent 使用说明

本文档用于智慧城市比赛演示、现场启动、开发调试和项目讲解。文中所有密钥、
Token、账号和本地路径均使用占位符，不包含任何真实凭据。

## 1. 项目简介

TrafficGraph 是面向上海市智慧交通指挥场景的 AI Agent 原型系统。

系统以 LangGraph 为编排核心，将自然语言问题转化为交通数据查询、专业知识检索、
信号优化分析、事件处置和报告导出任务，并通过 Web 指挥台展示实时态势、
工具调用过程、分析图表和 CSV 报表。

### 核心目标

1. 让指挥人员通过自然语言快速查询全市和路口态势。
2. 将交通数据、信号配时、事件和调度记录统一到一个中控平台。
3. 通过专业知识库提供可追溯的交通规则和处置建议。
4. 将数据自动整理为表格、图表和可下载报表。
5. 在无真实数据接口时，通过确定性仿真保证比赛现场演示稳定可复现。

## 2. 比赛演示入口

启动后访问：

- Web 指挥台：`http://127.0.0.1:8000/`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

Web 指挥台采用一屏式中控布局，包含：

- 左侧固定导航
- 中间态势或业务工作区
- 右侧固定 Agent Copilot
- 报告抽屉和 CSV 下载入口

## 3. 环境要求

推荐环境：

- Windows 10/11、Linux 或 macOS
- Python 3.11 或更高版本
- 8 GB 以上内存
- 现代浏览器，推荐 Chrome 或 Edge

项目不要求安装 Node.js。前端使用原生 HTML、CSS、JavaScript 和 SVG，
由 FastAPI 直接提供静态资源。

## 4. 获取和进入项目

项目目录：

```powershell
cd C:\Users\54950\Desktop\智慧城市\TrafficGraph
```

如果项目移动到其他目录，请进入实际的 `TrafficGraph` 根目录。

## 5. 安装依赖

### 5.1 创建虚拟环境

```powershell
python -m venv .venv
```

### 5.2 激活虚拟环境

PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果系统禁止执行脚本，可以只使用完整 Python 路径，不激活环境：

```powershell
.\.venv\Scripts\python.exe
```

### 5.3 安装 Python 依赖

```powershell
python -m pip install -r requirements.txt
```

## 6. 配置说明

### 6.1 创建本地配置文件

```powershell
Copy-Item .env.example .env
```

项目中以下文件不会提交到 Git：

- `.env`
- `.claude/settings.local.json`

可以通过以下命令确认：

```powershell
git check-ignore -v .env .claude/settings.local.json
```

### 6.2 仿真数据配置

比赛现场推荐使用确定性仿真：

```env
TRAFFIC_BACKEND=sim
TRAFFIC_SIM_CLOCK=2026-09-13T08:30:00
```

说明：

- `TRAFFIC_BACKEND=sim` 表示使用本地 TrafficSim。
- `TRAFFIC_SIM_CLOCK` 可固定演示时间，保证每次查询结果一致。
- 留空 `TRAFFIC_SIM_CLOCK` 时使用系统当前时间。

### 6.3 RAG 向量配置

离线模式，推荐比赛现场使用：

```env
TRAFFIC_EMBEDDING_BACKEND=hashing
```

需要更高语义检索质量时可选 BGE：

```env
TRAFFIC_EMBEDDING_BACKEND=bge
```

`bge` 模式首次运行需要下载模型。比赛现场网络不稳定时，应使用 `hashing`。

### 6.4 大模型配置

项目支持 OpenAI 协议、DeepSeek 和 Anthropic 兼容协议。

普通 Anthropic 配置示例：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_AUTH_TOKEN=请填写你自己的本地密钥
ANTHROPIC_BASE_URL=请填写服务地址
ANTHROPIC_MODEL=请填写模型名称
API_TIMEOUT_MS=120000
```

OpenAI 协议示例：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=请填写你自己的本地密钥
OPENAI_BASE_URL=请填写兼容服务地址，可留空
OPENAI_MODEL=请填写模型名称
```

DeepSeek 示例：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=请填写你自己的本地密钥
DEEPSEEK_MODEL=请填写模型名称
```

不要在以下位置填写真实密钥：

- README 或其他 Markdown
- 截图
- Git 提交
- 前端代码
- Prompt 配置
- JSONL 语料

如果需要在多台电脑上重复生成本地配置，可使用：

```powershell
.\scripts\setup_local_llm.ps1
```

该脚本从本机已有的 Claude Code 配置读取环境变量，只生成本地 `.env` 和
`.claude/settings.local.json`，不会输出密钥。

### 6.5 前端和 API 配置

```env
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=*
API_KEY=
```

说明：

- `API_KEY` 为空时，本地开发模式不启用 Bearer Token 鉴权。
- 比赛公网部署时应设置 `API_KEY`，并限制 `API_CORS_ORIGINS`。

## 7. 初始化交通知识库

首次运行或修改语料后执行：

```powershell
python -m src.pipelines.rag_ingest --rebuild
```

默认语料：

```text
data/traffic_qa_corpus.jsonl
```

默认向量库：

```text
data/traffic_knowledge/
```

默认集合：

```text
traffic_qa
```

成功时会显示类似：

```text
[rag_ingest] 入库完成，共 57 条。
```

## 8. 启动项目

### 8.1 使用启动脚本

```powershell
python run.py
```

不使用全局 `python` 时：

```powershell
.\.venv\Scripts\python.exe run.py
```

### 8.2 直接使用 Uvicorn

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.services.api:app --host 127.0.0.1 --port 8000
```

### 8.3 生产模式

```powershell
python run.py --prod
```

## 9. 比赛现场推荐演示流程

### 9.1 态势总览

打开：

```text
http://127.0.0.1:8000/
```

讲解内容：

- 城市拥堵指数
- 全市平均车速
- 活跃交通事件
- 当前最拥堵路口
- 上海市干线实时态势
- 路口节点饱和度

### 9.2 路网监控

点击左侧“路网监控”。

演示内容：

- 搜索路口名称或 ID
- 按干线筛选
- 查看 LOS、饱和度、延误、排队和当前相位
- 点击台账行查看路口诊断

推荐提问：

```text
分析 JK-SJ03 当前运行状态，并给出改善建议。
```

### 9.3 信号控制

点击左侧“信号控制”。

演示内容：

- 干线绿波状态
- 绿波带宽
- 路口当前相位
- 周期和相位差
- Webster 优化建议
- 最小绿灯和行人过街安全约束

推荐提问：

```text
给我一份 JK-SJ03 的信号优化建议，并说明安全约束。
```

### 9.4 事件处置

点击左侧“事件处置”。

演示内容：

- 活跃事件队列
- 事件等级和影响范围
- 占道情况
- 预计恢复时间
- 处置资源状态
- 调度时间线

推荐提问：

```text
现在有哪些交通事件和施工管制？
```

### 9.5 Agent Copilot

右侧 Copilot 不需要切换页面即可使用。

Agent 的页面建议不会自动跳转，只会生成“待确认定位”按钮，
避免演示过程中因模型输出导致页面失控。

推荐演示问题：

```text
现在上海市哪里最堵？
```

```text
JK-SJ03 现在堵不堵？
```

```text
世纪大道的绿波协调状态怎么样？
```

```text
导出云山大道最近 7 天的流量数据。
```

### 9.6 表格、图表和 CSV 报表

点击顶部“导出当前视图”。

系统会生成：

- 数据表格
- 柱状图
- 折线图
- 环形图
- CSV 下载

当前支持：

- 全市拥堵 Top5 报告
- 路口实时台账
- 信号配时报告
- 交通事件处置报告

## 10. 系统功能

### 10.1 全市态势

- 拥堵指数
- 平均车速
- 峰值等级
- 拥堵 Top5
- 活跃事件数量

### 10.2 路口运行

- 服务水平 LOS
- 平均饱和度
- 平均延误
- 进口道排队
- 二次排队
- 当前相位
- 事件影响

### 10.3 干线绿波

- 干线平均车速
- 平均饱和度
- 绿波状态
- 绿波带宽
- 相位差偏差

### 10.4 信号优化

- Webster 最优周期
- 绿信比建议
- 相位差调整
- 预期收益
- 安全约束校验

### 10.5 事件与调度

- 事故
- 车辆抛锚
- 道路施工
- 临时管制
- 派单记录
- 接处警记录

### 10.6 交通专业 RAG

- 信号配时原理
- 绿波协调
- 交通流理论
- 事件处置 SOP
- 指挥调度流程
- GB 14886 等规范

## 11. 12 个交通数据工具

| 工具 | 功能 |
|------|------|
| `fetch_city_overview` | 全市交通态势 |
| `fetch_intersection_status` | 单路口实时状态 |
| `fetch_corridor_congestion` | 干线拥堵与绿波 |
| `fetch_district_congestion` | 辖区拥堵指数 |
| `fetch_signal_timing` | 信号配时方案 |
| `fetch_signal_optimization_suggestion` | 信号优化建议 |
| `fetch_flow_history` | 路口或干线流量历史 |
| `fetch_active_incidents` | 当前活跃事件 |
| `fetch_incident_history` | 历史事件 |
| `fetch_camera_list` | 摄像头清单 |
| `fetch_dispatch_records` | 派单和调度记录 |
| `fetch_event_alarm_history` | 接处警记录 |

其他工具：

- `query_traffic_knowledge`
- `navigate_to_page`
- `export_data_table`
- `search_memory`
- `search_relevant_memory`
- `save_memory`

## 12. 技术架构

### 12.1 后端

| 技术 | 用途 |
|------|------|
| Python | 核心开发语言 |
| FastAPI | HTTP API 和 SSE |
| Uvicorn | ASGI 服务 |
| LangGraph | Agent 状态图 |
| LangChain | 模型和工具调用 |
| Pydantic | 强类型数据模型 |
| ChromaDB | 本地向量知识库 |

### 12.2 前端

| 技术 | 用途 |
|------|------|
| HTML5 | 页面结构 |
| CSS Grid/Flex | 一屏式中控布局 |
| JavaScript | 交互、SSE、图表和报表 |
| SVG | 路网拓扑和图表 |
| SSE | Agent 流式事件 |

### 12.3 数据与仿真

TrafficSim 使用确定性规则模拟：

- 早晚高峰需求
- 道路等级差异
- 路口饱和度和排队
- 信号周期和相位
- 事件通行能力折减
- 干线协调相位差

所有随机量由日期、对象和数据类型生成稳定种子，同一天同一场景可重复演示。

### 12.4 记忆与知识

- L1：LangGraph checkpoint，按 `thread_id` 隔离会话。
- L2：长期记忆，按运行环境、区域和 Agent 隔离。
- L3：ChromaDB 交通知识库，支持离线 hashing 和可选 BGE。

## 13. 项目目录

```text
TrafficGraph/
├── config/
│   ├── traffic_network.yaml
│   ├── routes.yaml
│   └── agent_config.yaml
├── data/
│   └── traffic_qa_corpus.jsonl
├── src/
│   ├── config/
│   ├── frontend/web/
│   ├── graph/
│   ├── knowledge/
│   ├── memory/
│   ├── pipelines/
│   ├── schemas/
│   ├── services/
│   ├── sim/
│   ├── skills/
│   ├── tests/
│   └── tools/
├── scripts/
├── run.py
└── requirements.txt
```

## 14. 常见问题

### 14.1 页面能打开但没有数据

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/dashboard
```

### 14.2 Agent 无法调用模型

检查 `.env` 中是否配置了：

- `LLM_PROVIDER`
- 对应供应商密钥
- 模型名称
- 服务地址，如果使用兼容网关

同时确认 `.env` 位于项目根目录。

### 14.3 知识库未初始化

执行：

```powershell
python -m src.pipelines.rag_ingest --rebuild
```

### 14.4 BGE 模型下载失败

切换为：

```env
TRAFFIC_EMBEDDING_BACKEND=hashing
```

然后重新执行语料入库。

### 14.5 端口被占用

修改 `.env`：

```env
API_PORT=8001
```

然后重新启动。

### 14.6 不希望 Agent 自动切换页面

当前设计就是如此。

Agent 的动作只显示为“待确认定位”按钮，不会自动覆盖中控台当前工作区。

## 15. 比赛讲解建议

建议按照以下顺序讲解：

1. 智慧交通痛点：数据分散、查询慢、研判依赖人工。
2. TrafficGraph 定位：一个统一的交通指挥 Agent。
3. 现场演示：态势、路网、信号、事件四个视图。
4. Agent 演示：自然语言查询和工具调用过程。
5. RAG 演示：规范知识和引用来源。
6. 报表演示：表格、图表和 CSV 一键导出。
7. 安全边界：Agent 只分析和建议，不直接控制真实信号。
8. 工程亮点：确定性仿真、本地知识库、SSE、强类型 Schema、离线可运行。

## 16. 测试

运行全部测试：

```powershell
python -m pytest src/tests -q
```

当前预期结果：

```text
103 passed, 1 skipped
```

被跳过的测试需要显式开启本地实时服务测试。

## 17. 安全说明

1. 不提交 `.env`。
2. 不提交 `.claude/settings.local.json`。
3. 不在文档和截图中展示真实 Token。
4. 密钥泄露后立即在服务控制台轮换。
5. 公网部署时启用 API Key 并限制 CORS。
6. 比赛演示优先使用本地仿真和离线知识库。
