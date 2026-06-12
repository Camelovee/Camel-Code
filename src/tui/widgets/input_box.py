"""InputBox Widget —— 用户输入区域。

hint 在输入框上方动态显示斜杠命令提示。
"""
from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Static

# 内置斜杠命令
SLASH_COMMANDS = [
    "/help",
    "/tools",
    "/clear",
    "/snip",
    "/compact",
    "/collapse",
    "/model",
    "/quit",
    "/exit",
]


class InputBox(Vertical):
    """用户输入区域。hint 在输入框上方动态提示。"""

    class Submitted(Message):
        """用户提交输入时发送的消息。"""

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(self) -> None:
        super().__init__()
        self._hint = Static("", classes="hint")
        self._prompt = Static(">", classes="prompt")
        self._input = Input(placeholder="输入消息，/help 查看命令，Ctrl+C 退出...")

    def compose(self):
        """组装子组件：hint 在上，prompt + Input 在下。"""
        yield self._hint
        with Horizontal():
            yield self._prompt
            yield self._input

    def on_mount(self) -> None:
        """挂载后聚焦输入框。"""
        self._input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """输入变化时更新命令提示。"""
        value = event.value
        if value.startswith("/"):
            matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(value)]
            if matches and value not in matches:
                self._hint.update(f"命令: {', '.join(matches[:5])}")
            else:
                self._hint.update("")
        else:
            self._hint.update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """输入提交时发送 Submitted 消息。"""
        event.stop()
        value = self._input.value.strip()
        if value:
            self.post_message(self.Submitted(value))
            self._input.value = ""
            self._hint.update("")

    def focus_input(self) -> None:
        """聚焦输入框。"""
        self._input.focus()
