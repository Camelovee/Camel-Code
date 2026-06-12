"""LangGraph 状态图定义：四层压缩 + ReAct 循环。

Graph 结构：
    compress → llm → should_continue
                        ↓ (有 tool_calls)
                   tool_node ─┘
                        ↓ (无 tool_calls 或达步数上限)
                        END
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, StateGraph

from src.compact import CompactPipelineState, run_compact_pipeline
from src.compact.tool_result_storage import replace_large_tool_result
from src.utils.token_estimator import compute_context_stats


class AgentState(TypedDict):
    """LangGraph 状态定义。"""

    messages: list[BaseMessage]         # 完整消息历史
    model_messages: list[BaseMessage]   # 压缩后的模型可见视图
    step: int                           # 已执行的 LLM 轮数
    compact_state: CompactPipelineState # 跨轮次压缩状态
    model_name: str                     # 模型标识（用于上下文统计）


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
    callbacks=None,
):
    """构建并编译 Agent 状态图。

    Args:
        llm: BaseChatModel 实例
        tools_dict: 工具名称 -> 工具实例 的映射
        max_steps: 每回合最多 LLM 调用轮数

    Returns:
        编译后的 StateGraph 可调用对象
    """
    tools_list = list(tools_dict.values())

    # ── 闭包节点（捕获 llm / tools / callbacks）─────────────────────────────
    def compress_node(state: AgentState) -> dict:
        result = run_compact_pipeline(
            messages=state["messages"],
            model=llm,
            model_name=state["model_name"],
            step=state["step"],
            state=state["compact_state"],
        )

        # 通知 TUI 上下文统计更新
        if callbacks and callbacks.on_context_stats:
            stats_after = compute_context_stats(result.model_messages, state["model_name"])
            callbacks.on_context_stats(stats_after)

        # 通知 TUI 压缩事件
        if callbacks and callbacks.on_compression:
            if result.snip_result and result.snip_result.did_snip:
                callbacks.on_compression("snip", {
                    "tokens_freed": getattr(result.snip_result, "tokens_freed", 0),
                })
            if result.collapse_result and result.collapse_result.collapsed:
                callbacks.on_compression("collapse", {})
            if result.auto_compact_result:
                callbacks.on_compression("auto-compact", {
                    "tokens_before": result.stats_before.get("total_tokens", 0),
                    "tokens_after": result.stats_after.get("total_tokens", 0),
                })

        return {
            "messages": result.messages,
            "model_messages": result.model_messages,
        }

    def llm_node(state: AgentState) -> dict:
        response = llm.bind_tools(tools_list).invoke(state["model_messages"])

        # 通知 TUI 助手消息：区分 thinking 和 text
        if callbacks:
            content = getattr(response, "content", "")
            if isinstance(content, list):
                for block in content:
                    block_type = block.get("type")
                    if block_type == "thinking" and callbacks.on_progress_message:
                        callbacks.on_progress_message(str(block.get("thinking", "")))
                    elif block_type == "text" and callbacks.on_assistant_message:
                        callbacks.on_assistant_message(str(block.get("text", "")))
            elif content and callbacks.on_assistant_message:
                callbacks.on_assistant_message(str(content))

        return {
            "messages": state["messages"] + [response],
            "step": state["step"] + 1,
        }

    def tool_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
            return {"messages": state["messages"]}

        tool_messages: list[ToolMessage] = []
        for tc in last_msg.tool_calls:
            name, args, tool_id = tc["name"], tc["args"], tc["id"]

            # 通知 TUI 工具开始
            if callbacks and callbacks.on_tool_start:
                callbacks.on_tool_start(name, args)

            tool_func = tools_dict.get(name)
            if not tool_func:
                result = f"Tool {name} not found"
            else:
                try:
                    result = str(tool_func.invoke(args))
                except Exception as e:
                    result = f"Error: {e}"

            # 通知 TUI 工具结果
            if callbacks and callbacks.on_tool_result:
                is_error = result.startswith("Error:") or result.startswith("Tool")
                callbacks.on_tool_result(name, result, is_error)

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

        return {"messages": state["messages"] + tool_messages}

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
    builder.add_edge("tool_node", "compress")

    return builder.compile()
