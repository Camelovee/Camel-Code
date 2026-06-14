"""Agent 循环钩子管理器。

提供发布-订阅式的钩子机制，让 Agent 循环在关键阶段触发外部注册的函数，
从而将 UI 通知、日志、审计等横切关注点与核心图逻辑解耦。
"""
from __future__ import annotations

from typing import Any, Callable


class HookManager:
    """管理 Agent 循环各阶段的钩子函数。"""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """注册一个钩子函数。

        Args:
            name: 钩子点名称，例如 "after_compress"、"before_tool"。
            fn: 触发时调用的函数，接收关键字参数。
        """
        self._hooks.setdefault(name, []).append(fn)

    def call(self, hook_name: str, **kwargs: Any) -> None:
        """触发某个钩子点上的所有函数。"""
        for fn in self._hooks.get(hook_name, []):
            fn(**kwargs)

    def has_hook(self, hook_name: str) -> bool:
        """检查是否存在某个钩子。"""
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0
