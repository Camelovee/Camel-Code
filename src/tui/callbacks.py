"""回调工厂：将 Agent 事件转换为 Textual 消息。

线程安全：所有回调通过 app.call_from_thread() 投递到 Textual 主消息循环，
确保 UI 更新在主线程执行。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.agents.callbacks import AgentCallbacks
from src.tui.events import (
    AgentEvent,
    AssistantMessageEvent,
    CompressionEvent,
    ContextStatsEvent,
    ProgressMessageEvent,
    ToolResultEvent,
    ToolStartEvent,
)

if TYPE_CHECKING:
    from src.tui.app import CamelTUIApp


def make_callbacks(app: "CamelTUIApp") -> AgentCallbacks:
    """为给定的 TUI App 创建线程安全的 Agent 回调集合。

    Args:
        app: CamelTUIApp 实例

    Returns:
        AgentCallbacks，可直接传给 LeadAgent.run_agent_turn()
    """
    def _post(event: AgentEvent) -> None:
        """将事件投递到 Textual 主线程消息循环。"""
        app.call_from_thread(app.post_message, event)

    return AgentCallbacks(
        on_tool_start=lambda name, inp: _post(ToolStartEvent(name, inp)),
        on_tool_result=lambda name, out, err: _post(ToolResultEvent(name, out, err)),
        on_assistant_message=lambda content: _post(AssistantMessageEvent(content)),
        on_progress_message=lambda content: _post(ProgressMessageEvent(content)),
        on_context_stats=lambda stats: _post(ContextStatsEvent(stats)),
        on_compression=lambda kind, result: _post(CompressionEvent(kind, result)),
    )
