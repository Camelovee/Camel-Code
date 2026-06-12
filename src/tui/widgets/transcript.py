"""Transcript Widget —— 对话历史区域。

ScrollView + Vertical + 消息条目，先保证基础纯文本显示和滚动可用。
"""
from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Markdown, Static


class MessageItem(Horizontal):
    """单条聊天消息：左侧标签 + 右侧内容。"""

    def __init__(
        self, label: str, content: str, classes: str = "", use_markdown: bool = False
    ) -> None:
        super().__init__(classes=classes)
        self._label = label
        self._content = content
        self._use_markdown = use_markdown

    def compose(self):
        """组装标签和内容。"""
        yield Label(self._label, classes="message-label")
        if self._use_markdown:
            yield Markdown(self._content, classes="message-content")
        else:
            yield Static(self._content, classes="message-content")


class Transcript(VerticalScroll):
    """对话历史展示区域。"""


    def __init__(self) -> None:
        super().__init__()
        self._messages = Vertical(id="messages")
        self._next_entry_id: int = 0

    def compose(self):
        """组装滚动容器。"""
        yield self._messages

    def _add_message(
        self, label: str, content: str, classes: str, use_markdown: bool = False
    ) -> None:
        """添加一条消息。"""
        item = MessageItem(
            label=label,
            content=content,
            classes=classes,
            use_markdown=use_markdown,
        )
        self._messages.mount(item)
        self._messages.refresh()
        self.refresh(layout=True)
        self.call_after_refresh(self.scroll_end, animate=False)

    def add_user_message(self, content: str) -> None:
        """添加用户消息到对话历史。"""
        self._add_message("User", content, "user")

    def add_assistant_message(self, content: str) -> None:
        """添加助手回复到对话历史，使用 Markdown 渲染。"""
        self._add_message("Assistant", content, "assistant", use_markdown=True)

    def add_progress_message(self, content: str) -> None:
        """添加中间进度消息。"""
        self._add_message("Thinking", content, "progress")

    def add_tool_start(self, tool_name: str, tool_input: dict) -> int:
        """添加工具开始执行记录，返回 entry_id。"""
        entry_id = self._next_entry_id
        self._next_entry_id += 1
        input_str = self._summarize_tool_input(tool_name, tool_input)
        self._add_message(tool_name, f"● {tool_name}  {input_str}", "tool")
        return entry_id

    def add_tool_result(self, tool_name: str, output: str, is_error: bool) -> None:
        """添加工具执行结果。"""
        status = "✗ 错误" if is_error else "✓ 成功"
        detail = ""
        if is_error:
            preview = output[:200] + "..." if len(output) > 200 else output
            detail = f"\n{preview}"
        self._add_message(tool_name, f"{status}{detail}", "tool")

    def add_compression_info(self, kind: str, result: dict) -> None:
        """添加压缩诊断信息。"""
        if kind == "snip":
            tokens = result.get("tokens_freed", 0)
            self._add_message("Compact", f"[snip] 裁剪完成，释放 ~{tokens} tokens", "progress")
        elif kind == "collapse":
            self._add_message("Compact", "[collapse] 上下文折叠已应用", "progress")
        elif kind == "auto-compact":
            before = result.get("tokens_before", 0)
            after = result.get("tokens_after", 0)
            saved = before - after
            self._add_message("Compact", f"[auto-compact] 自动压缩完成，节省 ~{saved} tokens", "progress")

    def clear(self) -> None:
        """清空对话历史。"""
        self._messages.remove_children()

    def write(self, text: str) -> None:
        """兼容 RichLog.write() 的追加接口。"""
        self._add_message("System", text, "progress")

    @staticmethod
    def _summarize_tool_input(tool_name: str, tool_input: dict) -> str:
        """简要概括工具输入。"""
        if tool_name == "bash":
            cmd = tool_input.get("command", "")
            return cmd[:80] + "..." if len(cmd) > 80 else cmd
        if tool_name in ("read_file", "write_file", "edit_file"):
            path = tool_input.get("path", "")
            return path
        if tool_name == "glob":
            pattern = tool_input.get("pattern", "")
            return pattern
        s = str(tool_input)
        return s[:80] + "..." if len(s) > 80 else s
