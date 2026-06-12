"""Agent → TUI 事件类型定义。

所有事件均为 Message 子类，由 Agent 回调创建，
通过 Textual 的 post_message 投递到 UI 线程。
"""
from __future__ import annotations

from typing import Literal

from textual.message import Message

from src.utils.token_estimator import ContextStats


class AgentEvent(Message):
    """Agent → TUI 事件基类。"""

    def __init__(self) -> None:
        super().__init__()


class ToolStartEvent(AgentEvent):
    """工具开始执行。"""

    def __init__(self, tool_name: str, tool_input: dict) -> None:
        self.tool_name = tool_name
        self.tool_input = tool_input
        super().__init__()


class ToolResultEvent(AgentEvent):
    """工具执行完成。"""

    def __init__(self, tool_name: str, output: str, is_error: bool) -> None:
        self.tool_name = tool_name
        self.output = output
        self.is_error = is_error
        super().__init__()


class AssistantMessageEvent(AgentEvent):
    """助手产生最终回复。"""

    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class ProgressMessageEvent(AgentEvent):
    """助手产生中间进度消息。"""

    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class ContextStatsEvent(AgentEvent):
    """上下文统计信息更新。"""

    def __init__(self, stats: ContextStats) -> None:
        self.stats = stats
        super().__init__()


class CompressionEvent(AgentEvent):
    """压缩管道执行事件。"""

    def __init__(
        self,
        kind: Literal["snip", "collapse", "auto-compact"],
        result: dict,
    ) -> None:
        self.kind = kind
        self.result = result
        super().__init__()
