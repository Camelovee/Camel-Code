"""测试 TUI 事件类型。"""
from __future__ import annotations

from src.tui.events import (
    AgentEvent,
    AssistantMessageEvent,
    CompressionEvent,
    ProgressMessageEvent,
    ToolResultEvent,
    ToolStartEvent,
)


def test_agent_event_base():
    e = AgentEvent()
    assert isinstance(e, AgentEvent)


def test_tool_start_event():
    e = ToolStartEvent(tool_name="bash", tool_input={"command": "ls"})
    assert e.tool_name == "bash"
    assert e.tool_input == {"command": "ls"}


def test_tool_result_event():
    e = ToolResultEvent(tool_name="read_file", output="content", is_error=False)
    assert e.is_error is False


def test_assistant_message_event():
    e = AssistantMessageEvent(content="hello")
    assert e.content == "hello"


def test_progress_message_event():
    e = ProgressMessageEvent(content="thinking...")
    assert e.content == "thinking..."


def test_compression_event():
    e = CompressionEvent(kind="snip", result={"tokens_freed": 100})
    assert e.kind == "snip"
