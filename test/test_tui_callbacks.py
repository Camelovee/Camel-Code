"""测试 TUI 回调工厂。"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.tui.callbacks import make_callbacks
from src.tui.events import AssistantMessageEvent, ToolStartEvent


def test_make_callbacks_posts_tool_start():
    app = MagicMock()
    callbacks = make_callbacks(app)
    callbacks.on_tool_start("bash", {"command": "ls"})

    app.post_message.assert_called_once()
    event = app.post_message.call_args[0][0]
    assert isinstance(event, ToolStartEvent)
    assert event.tool_name == "bash"


def test_make_callbacks_posts_assistant_message():
    app = MagicMock()
    callbacks = make_callbacks(app)
    callbacks.on_assistant_message("hello")

    event = app.post_message.call_args[0][0]
    assert isinstance(event, AssistantMessageEvent)
    assert event.content == "hello"
