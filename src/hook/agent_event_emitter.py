"""Agent 事件发射器 —— 把底层 HookManager 转换成高层事件供外部订阅。

TUI 等外部系统不需要直接操作 HookManager，只需调用 LeadAgent 提供的
on_xxx 方法注册回调。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .hook_manager import HookManager

if TYPE_CHECKING:
    from src.utils.token_estimator import ContextStats


class AgentEventEmitter:
    """基于 HookManager 构建的高层事件发射器。"""

    def __init__(self, hookManager: HookManager) -> None:
        self._hookManager = hookManager
        self._tool_start_handlers: list[Callable[[str, dict], None]] = []
        self._tool_result_handlers: list[Callable[[str, str, bool], None]] = []
        self._assistant_handlers: list[Callable[[str], None]] = []
        self._progress_handlers: list[Callable[[str], None]] = []
        self._context_stats_handlers: list[Callable[["ContextStats"], None]] = []
        self._compression_handlers: list[Callable[[str, dict], None]] = []

        self._llm_hook_installed = False
        self._compress_hook_installed = False

    # ── 工具事件 ────────────────────────────────────────────────

    def on_tool_start(self, handler: Callable[[str, dict], None]) -> None:
        """订阅工具开始事件。"""
        if not self._tool_start_handlers:
            self._hookManager.register("before_tool", self._dispatch_tool_start)
        self._tool_start_handlers.append(handler)

    def _dispatch_tool_start(self, *, state, name: str, args: dict) -> None:
        for h in self._tool_start_handlers:
            h(name, args)

    def on_tool_result(self, handler: Callable[[str, str, bool], None]) -> None:
        """订阅工具结果事件。"""
        if not self._tool_result_handlers:
            self._hookManager.register("after_tool", self._dispatch_tool_result)
        self._tool_result_handlers.append(handler)

    def _dispatch_tool_result(
        self, *, state, name: str, output: str, is_error: bool
    ) -> None:
        for h in self._tool_result_handlers:
            h(name, output, is_error)

    # ── LLM 消息事件 ─────────────────────────────────────────────

    def on_assistant_message(self, handler: Callable[[str], None]) -> None:
        """订阅助手消息事件。"""
        self._assistant_handlers.append(handler)
        self._ensure_llm_hook()

    def on_progress_message(self, handler: Callable[[str], None]) -> None:
        """订阅进度消息事件（如 thinking 块）。"""
        self._progress_handlers.append(handler)
        self._ensure_llm_hook()

    def _ensure_llm_hook(self) -> None:
        if self._llm_hook_installed:
            return
        self._llm_hook_installed = True
        self._hookManager.register("after_llm", self._dispatch_llm_response)
        self._hookManager.register("on_ask_user", self._dispatch_ask_user)

    def _dispatch_llm_response(self, *, state, response) -> None:
        content = getattr(response, "content", "")
        if isinstance(content, list):
            for block in content:
                block_type = block.get("type")
                if block_type == "thinking":
                    self._emit_progress(str(block.get("thinking", "")))
                elif block_type == "text":
                    text = str(block.get("text", ""))
                    if text:
                        self._emit_assistant(text)
        elif content:
            self._emit_assistant(str(content))

    def _dispatch_ask_user(self, *, state, question: str, meta: dict | None) -> None:
        self._emit_assistant(question)

    def _emit_assistant(self, content: str) -> None:
        for h in self._assistant_handlers:
            h(content)

    def _emit_progress(self, content: str) -> None:
        for h in self._progress_handlers:
            h(content)

    # ── 压缩事件 ─────────────────────────────────────────────────

    def on_context_stats(self, handler: Callable[["ContextStats"], None]) -> None:
        """订阅上下文统计更新事件。"""
        self._context_stats_handlers.append(handler)
        self._ensure_compress_hook()

    def on_compression(self, handler: Callable[[str, dict], None]) -> None:
        """订阅压缩事件（snip / collapse / auto-compact）。"""
        self._compression_handlers.append(handler)
        self._ensure_compress_hook()

    def _ensure_compress_hook(self) -> None:
        if self._compress_hook_installed:
            return
        self._compress_hook_installed = True
        self._hookManager.register("after_compress", self._dispatch_compress)

    def _dispatch_compress(self, *, state, result, stats) -> None:
        for h in self._context_stats_handlers:
            h(stats)

        if result.snip_result and result.snip_result.did_snip:
            self._emit_compression(
                "snip",
                {"tokens_freed": getattr(result.snip_result, "tokens_freed", 0)},
            )
        if result.collapse_result and result.collapse_result.collapsed:
            self._emit_compression("collapse", {})
        if result.auto_compact_result:
            self._emit_compression(
                "auto-compact",
                {
                    "tokens_before": result.stats_before.get("total_tokens", 0),
                    "tokens_after": result.stats_after.get("total_tokens", 0),
                },
            )

    def _emit_compression(self, kind: str, data: dict) -> None:
        for h in self._compression_handlers:
            h(kind, data)
