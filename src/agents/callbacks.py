"""Agent 图执行过程中的回调接口定义。

将 Graph 节点需要触发的事件抽象为类型化的回调集合，
替代原有的通用 HookManager，使 Agent 与 TUI 的交互更直接。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.utils.token_estimator import ContextStats


@dataclass
class AgentCallbacks:
    """Agent 状态图在执行关键节点时调用的回调集合。

    所有回调均为可选；未注册时对应节点不执行任何通知逻辑。
    """

    on_tool_start: Callable[[str, dict], None] | None = None
    on_tool_result: Callable[[str, str, bool], None] | None = None
    on_assistant_message: Callable[[str], None] | None = None
    on_progress_message: Callable[[str], None] | None = None
    on_context_stats: Callable[[ContextStats], None] | None = None
    on_compression: Callable[[str, dict], None] | None = None
