"""streamlit_app — 智慧交通指挥 Agent Streamlit 演示前端

所属层：frontend
依赖：streamlit, src.graph.builder
对接算法层：N/A（通过 graph 间接调用）
"""
import os
import sys
import uuid
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import streamlit as st

from src.config.settings import settings
from src.graph.builder import build_graph_config, graph


def _build_route_names() -> dict:
    """从 routes.yaml 动态构建路由→名称映射。

    Returns:
        {route_path: display_name, ...}
    """
    route_names = {}
    routes_config = settings.routes
    all_routes = routes_config.get("accessible_routes", []) + routes_config.get("restricted_routes", [])
    for route in all_routes:
        route_names[route["path"]] = route["name"]
    return route_names


# 启动时从 routes.yaml 构建一次
_ROUTE_NAMES = _build_route_names()

# Phase 6 导出文件落盘目录（与 services/api.py 同路径，data/ 已 gitignore）
_EXPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"
_FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def _render_data_card(card: dict) -> None:
    """渲染数据卡片：表格 + 下载按钮（Phase 6 数据导出）。

    Args:
        card: DataCard dict（含 title / table{columns,rows} / download{task_id,filename}）
    """
    import pandas as pd  # streamlit 依赖 pandas，局部导入避免模块加载期开销

    table = card.get("table", {}) or {}
    columns = table.get("columns", []) or []
    rows = table.get("rows", []) or []
    title = card.get("title", "数据导出")
    download = card.get("download", {}) or {}
    task_id = download.get("task_id", "")
    filename = download.get("filename") or f"{task_id}.csv"

    st.markdown(f"**📊 {title}**")
    if rows:
        df = pd.DataFrame(rows)
        if columns:
            # 按 columns 顺序重排列，并用中文 label 重命名表头
            col_keys = [c.get("key") for c in columns if c.get("key") in df.columns]
            if col_keys:
                df = df[col_keys]
            rename = {c.get("key"): c.get("label", c.get("key")) for c in columns if c.get("key") in df.columns}
            df = df.rename(columns=rename)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("（无数据行）")

    csv_path = _EXPORT_DIR / f"{task_id}.csv"
    if csv_path.is_file():
        with open(csv_path, "rb") as f:
            csv_bytes = f.read()
        st.download_button(
            label="⬇️ 下载 CSV",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv",
            key=f"dl_{task_id}",
        )
    else:
        st.warning("导出文件不存在或已过期")

st.set_page_config(page_title="上海市智慧交通指挥演示", layout="wide")
st.title("上海市智慧交通指挥演示")
st.caption("全市态势 · 路口诊断 · 信号优化 · 事件调度 · 基于 LangGraph + DeepSeek")

NODE_STEPS = {
    "cognitive_parser": "意图解析 — 分析问题类型，选择工具",
    "v3_engine_router": "工具调用 — 查询交通数据 / 检索知识库",
    "interpreter_generator": "生成回答 — 综合态势，形成研判",
}

# 初始化对话历史
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4().hex}"

# 侧边栏
with st.sidebar:
    st.header("配置")
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")
    target_date = st.text_input("查询日期", value=current_date)
    st.divider()
    st.markdown("**态势与路口**")
    situation_examples = [
        "现在全市哪里最堵？",
        "中心商务区当前交通态势怎么样？",
        "JK-SJ03 现在堵不堵？各进口道排队情况如何？",
        "世纪大道的绿波协调状态怎么样？",
    ]
    for ex in situation_examples:
        if st.button(ex, use_container_width=True, key=f"sit_{ex[:20]}"):
            st.session_state.pending_input = ex

    st.markdown("**信号与事件**")
    operation_examples = [
        "JK-SJ03 的信号配时方案是多少？",
        "给我一份 JK-BJ03 的信号优化建议，并说明安全约束",
        "现在有哪些交通事件和施工管制？",
        "调出 JK-JF03 附近的视频监控",
    ]
    for ex in operation_examples:
        if st.button(ex, use_container_width=True, key=f"ops_{ex[:20]}"):
            st.session_state.pending_input = ex

    st.markdown("**多意图测试**")
    multi_intent_examples = [
        "查一下全市拥堵 Top5，再看看中心商务区态势",
        "JK-SJ01 当前排队多少？配时方案是否合理？",
        "看看世纪大道绿波状态，顺便查最近的交通事件",
        "查 JK-BJ03 路况，并导出近 7 天流量数据",
    ]
    for ex in multi_intent_examples:
        if st.button(ex, use_container_width=True, key=f"multi_{ex[:20]}"):
            st.session_state.pending_input = ex

    st.markdown("**数据导出测试**")
    export_examples = [
        "导出世纪大道最近7天的流量数据",
        "导出 JK-SJ03 最近24小时流量表格",
        "导出本月交通事件记录",
        "导出本月接处警记录",
        "查一下全市态势，并导出最近7天事件表格",
    ]
    for ex in export_examples:
        if st.button(ex, use_container_width=True, key=f"exp_{ex[:20]}"):
            st.session_state.pending_input = ex

    if st.button("清空对话", type="secondary", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# 显示历史对话（步骤/意图/来源折叠，回答在下）
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            # 1. 思考过程 + 意图识别（折叠）
            has_steps = bool(msg.get("steps"))
            has_intent = bool(msg.get("intent_display"))
            if has_steps or has_intent:
                with st.expander("💭 思考过程 & 意图识别", expanded=False):
                    if has_steps:
                        st.markdown("\n".join(msg["steps"]))
                    if has_intent:
                        st.markdown("**🧩 识别到多个意图：**")
                        for item in msg["intent_display"]:
                            st.markdown(f"- {item}")
            # 2. 工具详情 / RAG 来源（折叠）
            if msg.get("details"):
                with st.expander("📋 工具调用详情 & 知识库来源", expanded=False):
                    for label, data in msg["details"].items():
                        st.subheader(label)
                        st.json(data)
        # 3. 回答内容（含底部跳转链接）
        st.markdown(msg["content"])
        # 4. 数据卡片（Phase 6 导出：表格 + 下载按钮，跨 rerun 持久）
        for card in msg.get("data_cards") or []:
            _render_data_card(card)

# 处理侧边栏示例按钮触发
if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")
else:
    user_input = st.chat_input("输入交通态势、信号、事件或调度问题")

if user_input:
    # 显示用户消息
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 调用 Agent（token 级流式）
    with st.chat_message("assistant"):
        try:
            full_input = f"{user_input}\n[target_date={target_date}]"

            steps_ph = st.empty()           # 最上：ReAct 步骤
            details_ph = st.empty()        # 中间：工具/RAG 详情（在回答上方）
            answer_ph = st.empty()         # 最下：最终回答

            answer_text = ""
            steps = []
            result = {}
            tool_names = []
            seen_nodes = set()
            current_node = None
            tools_have_run = False  # 追踪工具是否已执行，用于控制流式内容路由

            for event in graph.stream(
                {
                    "user_input": full_input,
                    "thread_id": st.session_state.thread_id,
                    "page_context": {
                        "current_route": "/command/dashboard",
                        "area_id": "DIST-CBD",
                    }
                },
                config=build_graph_config(st.session_state.thread_id),
                stream_mode=["updates", "messages"],
            ):
                mode, data = event

                if mode == "messages":
                    chunk, meta = data
                    node = meta.get("langgraph_node", "")

                    # 节点切换时更新步骤
                    if node and node != current_node:
                        current_node = node
                        if node not in seen_nodes:
                            seen_nodes.add(node)
                            if node in NODE_STEPS:
                                label = NODE_STEPS[node]
                                if node == "v3_engine_router" and tool_names:
                                    label += f"（{', '.join(tool_names)}）"
                                steps.append(f"✅ {label}")
                                steps_ph.markdown("\n".join(steps))

                    # 检测工具调用
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        for tc in chunk.tool_call_chunks:
                            if tc.get("name") and tc["name"] not in tool_names:
                                tool_names.append(tc["name"])

                    # 流式文本
                    content = chunk.content if hasattr(chunk, "content") and chunk.content else ""
                    if content:
                        if node == "interpreter_generator":
                            # interpreter 生成的内容直接进入回答区
                            answer_text += content
                            answer_ph.markdown(answer_text + "▌")
                        elif node == "cognitive_parser" and tools_have_run:
                            # 工具已执行，cognitive_parser 基于工具结果生成回答 → 流式输出
                            answer_text += content
                            answer_ph.markdown(answer_text + "▌")

                elif mode == "updates":
                    if not isinstance(data, dict):
                        continue
                    for node_name, update in data.items():
                        if not isinstance(update, dict):
                            continue
                        # 标记工具已执行
                        if node_name == "v3_engine_router":
                            tools_have_run = True
                        # 确保节点出现在步骤中
                        if node_name not in seen_nodes:
                            seen_nodes.add(node_name)
                            if node_name in NODE_STEPS:
                                label = NODE_STEPS[node_name]
                                if node_name == "v3_engine_router" and tool_names:
                                    label += f"（{', '.join(tool_names)}）"
                                steps.append(f"✅ {label}")
                                steps_ph.markdown("\n".join(steps))
                        # 合并结果
                        for k, v in update.items():
                            if k not in ("messages",):
                                result[k] = v

            # ========== 流式结束后的布局：折叠过程信息，突出回答 ==========

            # 1. 解析多意图计划（Phase 7）
            intent_plan = result.get("intent_plan")
            intent_items = []
            if intent_plan:
                for i in intent_plan:
                    if isinstance(i, dict):
                        desc = i.get("description", "")
                        cat = i.get("category", "")
                        status = i.get("status", "")
                    else:
                        desc, cat, status = i.description, i.category, i.status
                    emoji = {
                        "monitor": "📡",
                        "signal": "🚦",
                        "incident": "🚨",
                        "dispatch": "🧭",
                        "knowledge": "📚",
                        "export": "📊",
                        "memory": "🧠",
                    }.get(cat, "📌")
                    intent_items.append(f"{emoji} 意图 {i.id if not isinstance(i, dict) else i.get('id', '?')}: {desc}")

            # 2. 将步骤 + 意图识别折叠（替换流式时的实时显示）
            if steps or intent_items:
                with steps_ph.container():
                    with st.expander("💭 思考过程 & 意图识别", expanded=False):
                        if steps:
                            st.markdown("\n".join(steps))
                        if intent_items:
                            st.markdown("**🧩 识别到多个意图：**")
                            for item in intent_items:
                                st.markdown(f"- {item}")
            else:
                steps_ph.empty()

            # 3. 页面跳转建议（Phase 2，保持可见）
            pending_actions = result.get("pending_actions", [])
            if pending_actions:
                with details_ph.container():
                    st.markdown("**🔗 Agent 建议跳转：**")
                    for action in pending_actions:
                        if isinstance(action, dict):
                            route = action.get("route", "")
                            name = action.get("name", "")
                            params = action.get("params", {})
                        else:
                            route = action.route
                            name = action.name
                            params = action.params or {}

                        # 优先使用 action 自带的 name，其次查路由表
                        route_name = name or _ROUTE_NAMES.get(route, route)

                        params = params or {}
                        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                        st.info(f"🎯 **{route_name}** ({route})\n\n参数: {param_str}")
                    st.markdown("💡 *指挥中心前端会消费 action 事件并执行跳转*")

            # 4. 工具调用详情 / RAG 来源（折叠）
            details = {}
            if result.get("traffic_knowledge"):
                details["📚 交通知识库检索"] = result["traffic_knowledge"]
            if result.get("constraints"):
                details["🎯 调度约束（DispatchConstraint）"] = result["constraints"]

            if details:
                if not pending_actions:
                    # 没有跳转建议时，details_ph 用于工具详情
                    with details_ph.container():
                        with st.expander("📋 工具调用详情 & 知识库来源", expanded=False):
                            for label, data in details.items():
                                st.subheader(label)
                                st.json(data)
                else:
                    # 有跳转建议时，在跳转建议下方显示
                    with st.expander("📋 工具调用详情 & 知识库来源", expanded=False):
                        for label, data in details.items():
                            st.subheader(label)
                            st.json(data)
            elif not pending_actions:
                details_ph.empty()

            # 3. 最终回答
            final = answer_text or result.get("final_report", "（无回答）")

            # 4. 页面跳转链接（直接添加到回答末尾）
            pending_actions = result.get("pending_actions", [])
            if pending_actions:
                links = []
                for action in pending_actions:
                    route = action.route if hasattr(action, "route") else action.get("route", "")
                    action_name = action.name if hasattr(action, "name") else action.get("name", "")
                    name = action_name or _ROUTE_NAMES.get(route, route)
                    full_url = f"{_FRONTEND_BASE_URL}{route}"
                    links.append(f"[{name}]({full_url})")
                final += f"\n\n---\n\n💡 **查看详细数据**：{' · '.join(links)}"

            answer_ph.markdown(final)

            # 5. 数据卡片（Phase 6 导出：表格 + 下载按钮）
            data_cards = result.get("pending_data_cards", []) or []
            for card in data_cards:
                _render_data_card(card)

            if result.get("error"):
                st.warning(f"警告: {result['error']}")

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": final,
                    "details": details,
                    "steps": steps,
                    "intent_display": intent_items if intent_plan else None,
                    "data_cards": data_cards,
                }
            )

        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            st.error(f"运行出错: {e}")
            with st.expander("调试详情"):
                st.code(err_detail)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": f"运行出错: {e}", "details": {}}
            )

        st.rerun()

st.markdown("---")
st.caption("TrafficGraph Demo · TrafficSim 确定性仿真 · 交通知识库 RAG · 多意图识别 + 自动页面跳转")
