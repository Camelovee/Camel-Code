"""Header Widget —— 顶部信息面板。

展示 CamelCode Logo、版本号、模型名、Token 利用率进度条。
"""
from __future__ import annotations

from textual.widgets import Static

from src.tui.colors import CAMEL, ERROR, GOLD, MUTED, SUCCESS, WARNING
from src.utils.token_estimator import ContextStats


# 从 main.py 移植的 Logo
CAMEL_LOGO = r"""
  ╭──╮   ╭──╮
  │ ■│   │■ │
  ╰──┴───┴──╯
 __/       \__
/  o       o  \
\_____■■■_____/
  ││       ││
"""

# CAMEL CODE 像素风文字 Logo
CAMEL_CODE = r"""
 █████    ███   █     █ ██████ ██         █████   █████   ████    ██████
█        █   █  █ █ █ █ █      ██         █      █     █  █    ██ █
█        █████  █  █  █ ██████ ██         █      █     █  █    ██ ██████
█       █     █ █     █ █      ██         █      █     █  █    ██ █
 █████  █     █ █     █ ██████ ██████     █████   █████   ████    ██████
"""



CAMEL_VERSION = "v0.0.1"


class Header(Static):
    """顶部信息面板。"""

    def __init__(self) -> None:
        super().__init__()
        self._model_name: str = ""
        self._stats: ContextStats | None = None

    def set_model_name(self, name: str) -> None:
        """设置当前模型名称。"""
        self._model_name = name
        self.refresh()

    def set_context_stats(self, stats: ContextStats | None) -> None:
        """设置上下文统计信息。"""
        self._stats = stats
        self.refresh()

    def _render_token_bar(self, utilization: float, width: int = 20) -> str:
        """渲染 Token 利用率进度条。"""
        filled = int(width * utilization)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def _get_utilization_color(self, utilization: float) -> str:
        """根据利用率返回对应颜色类名。"""
        if utilization > 0.95:
            return ERROR
        if utilization > 0.80:
            return WARNING
        return SUCCESS

    def _format_token_info(self) -> str:
        """格式化 Token 信息行。"""
        if not self._stats:
            return "Token: -- / --"

        total = self._stats.total_tokens
        window = self._stats.context_window
        util = self._stats.utilization
        bar = self._render_token_bar(util)
        color = self._get_utilization_color(util)

        total_str = f"{total >= 1000 and f'{total//1000}K' or str(total)}"
        window_str = f"{window >= 1000 and f'{window//1000}K' or str(window)}"
        pct = int(util * 100)

        return f"Token: {total_str} / {window_str}  [{color}]{bar}[/]  {pct}%"

    def render(self) -> str:
        """渲染 Header 内容。"""
        logo_lines = [line for line in CAMEL_LOGO.split("\n") if line]
        code_lines = [f"[{GOLD}]{line}[/]" for line in CAMEL_CODE.split("\n") if line]

        # Logo 右侧展示版本、模型信息，最下面是 CAMEL CODE 像素文字
        right_info = [
            f"[{GOLD}]CamelCode[/] [{MUTED}]{CAMEL_VERSION}[/]",
            f"模型: [{CAMEL}]{self._model_name or 'unknown'}[/]",
            self._format_token_info(),
            *code_lines,
        ]

        # 将右侧信息填充到 Logo 高度
        max_lines = max(len(logo_lines), len(right_info))
        logo_lines += [""] * (max_lines - len(logo_lines))
        right_info += [""] * (max_lines - len(right_info))

        # 计算 Logo 最大宽度
        logo_width = max(len(line) for line in logo_lines)

        rows = []
        for logo_line, info_line in zip(logo_lines, right_info):
            padded_logo = logo_line.ljust(logo_width)
            rows.append(f"{padded_logo}    {info_line}")

        return "\n".join(rows)
