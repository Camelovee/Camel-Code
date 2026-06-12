"""Footer Widget —— 底部状态栏。

展示当前状态、可用工具列表、压缩状态。
"""
from __future__ import annotations

from textual.widgets import Static

from src.tui.colors import CAMEL, SUCCESS, WARNING


class FooterBar(Static):
    """底部状态栏。"""

    def __init__(self) -> None:
        super().__init__()
        self._status: str = "就绪"
        self._is_busy: bool = False
        self._tools: list[str] = []
        self._compression_status: str | None = None

    def set_status(self, status: str, busy: bool = False) -> None:
        """设置状态文字。"""
        self._status = status
        self._is_busy = busy
        self.refresh()

    def set_tools(self, tools: list[str]) -> None:
        """设置可用工具列表。"""
        self._tools = tools
        self.refresh()

    def set_compression_status(self, status: str | None) -> None:
        """设置压缩状态。"""
        self._compression_status = status
        self.refresh()

    def render(self) -> str:
        """渲染 Footer 内容。"""
        status_color = WARNING if self._is_busy else SUCCESS
        status_part = f"[{status_color}]{self._status}[/]"

        tools_part = ""
        if self._tools:
            tools_str = ", ".join(self._tools)
            tools_part = f"  │  工具: {tools_str}"

        compression_part = ""
        if self._compression_status:
            compression_part = f"  │  [{CAMEL}]{self._compression_status}[/]"

        return f"{status_part}{tools_part}{compression_part}"
