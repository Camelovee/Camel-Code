"""CamelCode 钩子框架 —— 挂在循环上，不写进循环里。"""
from __future__ import annotations

from .agent_event_emitter import AgentEventEmitter
from .hook_manager import HookManager

__all__ = ["AgentEventEmitter", "HookManager"]
