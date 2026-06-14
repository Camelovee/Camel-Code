"""LangGraph 状态图定义：四层压缩 + ReAct 循环。

Graph 结构：
    compress → llm → should_continue
                        ↓ (有 tool_calls)
                   tool_node ─┘
                        ↓ (无 tool_calls 或达步数上限或 await_user)
                        END
"""
from __future__ import annotations

import json
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, StateGraph

from src.compact import CompactPipelineState, run_compact_pipeline
from src.compact.tool_result_storage import replace_large_tool_result
from src.hook import HookManager
from src.utils.token_estimator import compute_context_stats


class AgentState(TypedDict):
    """LangGraph 状态定义。"""

    messages: list[BaseMessage]         # 完整消息历史
    model_messages: list[BaseMessage]   # 压缩后的模型可见视图
    step: int                           # 已执行的 LLM 轮数
    compact_state: CompactPipelineState # 跨回合压缩状态
    model_name: str                     # 模型标识（用于上下文统计）
    awaiting_user_input: bool           # 是否正在等待用户回复
    pending_question: str | None        # 待回复的问题内容
    pending_question_meta: dict | None  # 待回复问题的元数据


def _should_continue(state: AgentState, max_steps: int) -> str:
    """条件路由：判断是否继续工具调用循环。"""
    last_msg = state["messages"][-1]
    if state["step"] >= max_steps:
        return END
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return END
    return "tool_node"


def build_graph(
    llm,
    tools_dict: dict,
    max_steps: int = 50,
    hookManager: HookManager | None = None,
):
    """构建并编译 Agent 状态图。

    Args:
        llm: BaseChatModel 实例
        tools_dict: 工具名称 -> 工具实例 的映射
        max_steps: 每回合最多 LLM 调用轮数
        hookManager: 可选的钩子管理器，用于解耦 UI 通知等横切逻辑

    Returns:
        编译后的 StateGraph 可调用对象
    """
    tools_list = list(tools_dict.values())

    # ── 闭包节点（捕获 llm / tools / hookManager）─────────────────────────────
    def compress_node(state: AgentState) -> dict:
        result = run_compact_pipeline(
            messages=state["messages"],
            model=llm,
            model_name=state["model_name"],
            step=state["step"],
            state=state["compact_state"],
        )

        # 触发压缩相关钩子
        if hookManager and hookManager.has_hook("after_compress"):
            stats_after = compute_context_stats(result.model_messages, state["model_name"])
            hookManager.call("after_compress", state=state, result=result, stats=stats_after)

        return {
            "messages": result.messages,
            "model_messages": result.model_messages,
        }

    def llm_node(state: AgentState) -> dict:
        response = llm.bind_tools(tools_list).invoke(state["model_messages"])

        # 触发 LLM 响应钩子
        if hookManager and hookManager.has_hook("after_llm"):
            hookManager.call("after_llm", state=state, response=response)

        return {
            "messages": state["messages"] + [response],
            "step": state["step"] + 1,
        }

    def tool_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
            return {"messages": state["messages"]}

        tool_messages: list[ToolMessage] = []
        extra_messages: list[BaseMessage] = []  # 收集 ask_user 产生的 assistant 消息
        awaiting_user_input = False
        pending_question: str | None = None
        pending_question_meta: dict | None = None

        for tc in last_msg.tool_calls:
            name, args, tool_id = tc["name"], tc["args"], tc["id"]

            # 触发工具开始前钩子
            if hookManager and hookManager.has_hook("before_tool"):
                hookManager.call("before_tool", state=state, name=name, args=args)

            tool_func = tools_dict.get(name)
            if not tool_func:
                result = f"Tool {name} not found"
            else:
                try:
                    result = str(tool_func.invoke(args))
                except Exception as e:
                    result = f"Error: {e}"

            # 检测 ask_user 工具的 await_user 标记
            parsed = None
            if name == "ask_user" and isinstance(result, str):
                try:
                    parsed = json.loads(result)
                except json.JSONDecodeError:
                    pass
            if parsed and parsed.get("await_user") and parsed.get("output"):
                awaiting_user_input = True
                pending_question = parsed["output"]
                pending_question_meta = parsed.get("meta")
                extra_messages.append(AIMessage(content=pending_question))

                # 触发 ask_user 钩子，让 UI 显示问题
                if hookManager and hookManager.has_hook("on_ask_user"):
                    hookManager.call(
                        "on_ask_user",
                        state=state,
                        question=pending_question,
                        meta=pending_question_meta,
                    )

            # 触发工具结果钩子
            if hookManager and hookManager.has_hook("after_tool"):
                is_error = result.startswith("Error:") or result.startswith("Tool not found")
                hookManager.call(
                    "after_tool",
                    state=state,
                    name=name,
                    output=result,
                    is_error=is_error,
                )

            raw_msg = ToolMessage(
                content=str(result),
                tool_call_id=tool_id,
                name=name,
            )
            replacement_state = state["compact_state"].tool_result_replacement
            compacted_msg = replace_large_tool_result(
                raw_msg, state=replacement_state
            )
            tool_messages.append(compacted_msg)

        return {
            "messages": state["messages"] + extra_messages + tool_messages,
            "awaiting_user_input": awaiting_user_input,
            "pending_question": pending_question,
            "pending_question_meta": pending_question_meta,
        }

    def _route_after_tool(state: AgentState) -> str:
        """tool_node 后的条件路由：检测到 await_user 时直接结束回合。"""
        if state.get("awaiting_user_input"):
            return END
        return "compress"

    # ── 组装状态图 ────────────────────────────────────────────
    builder = StateGraph(AgentState)

    builder.add_node("compress", compress_node)
    builder.add_node("llm", llm_node)
    builder.add_node("tool_node", tool_node)

    builder.set_entry_point("compress")
    builder.add_edge("compress", "llm")
    builder.add_conditional_edges(
        "llm",
        lambda s: _should_continue(s, max_steps),
        {
            "tool_node": "tool_node",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "tool_node",
        _route_after_tool,
        {END: END, "compress": "compress"},
    )

    return builder.compile()
