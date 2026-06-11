"""Token 估算工具 —— 与压缩策略解耦的基础模块。

提供消息级别的 token 估算、provider 用量合并、以及基础核算数据类。
不涉及任何压缩阈值或策略常量。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

if TYPE_CHECKING:
    from src.models.adapter import create_llm


# ── 基础常量 ───────────────────────────────────────────────────
# 按消息角色估算 token 的字符转换比（字符数 / 比值 = token 数）
# 值越小表示该角色同样字符数消耗更多 token（如 system 比 tool 更"费"token）
CHARS_PER_TOKEN: dict[str, float] = {
    "system": 3.5,          # system prompt：每 3.5 字符 ≈ 1 token
    "human": 3.0,           # user 消息：每 3.0 字符 ≈ 1 token
    "ai": 3.5,              # assistant 回复：每 3.5 字符 ≈ 1 token
    "tool": 2.0,            # tool_result：每 2.0 字符 ≈ 1 token（通常输出最长）
}


# ── 数据类 ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class TokenAccounting:
    """Token 核算结果。"""

    total_tokens: int                   # 总 token 数
    provider_usage_tokens: int          # 模型提供的用量 token 数
    estimated_tokens: int               # 估算 token 数
    source: str                         # 数据来源
    is_exact: bool                      # 是否精确（无估算部分）
    usage_boundary_index: int | None = None  # 用量边界消息索引
    stale: bool = False                 # 是否已过期
    reason: str | None = None           # 说明原因


# ── 基础工具函数 ───────────────────────────────────────────────
def _get_message_role(msg: BaseMessage) -> str:
    """将 LangChain 消息类型映射为角色字符串。"""
    if isinstance(msg, SystemMessage):
        return "system"
    elif isinstance(msg, HumanMessage):
        return "human"
    elif isinstance(msg, AIMessage):
        return "ai"
    elif isinstance(msg, ToolMessage):
        return "tool"
    else:
        return getattr(msg, "type", "unknown")


def _message_content_length(msg: BaseMessage) -> int:
    """估算消息的内容长度。"""
    content = msg.content
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return len(json.dumps(content, default=str))
    return len(str(content))


def estimate_message_tokens(msg: BaseMessage) -> int:
    """估算单条消息的 token 数量。"""
    role = _get_message_role(msg)
    ratio = CHARS_PER_TOKEN.get(role, 3.0)
    length = _message_content_length(msg)
    return max(1, int(length / ratio))


def estimate_messages_tokens(messages: list[BaseMessage]) -> int:
    """估算消息列表的总 token 数量。"""
    return sum(estimate_message_tokens(m) for m in messages)


def _get_usage_metadata(msg: BaseMessage) -> dict | None:
    """从 AIMessage 中提取 usage_metadata。"""
    if isinstance(msg, AIMessage):
        return msg.usage_metadata
    return None


def token_count_with_estimation(messages: list[BaseMessage]) -> TokenAccounting:
    """结合 provider 用量信息与估算值，计算尾部消息的 token 数。"""
    # 从尾部向前扫描，找到最近一条包含 usage 元数据的消息
    for i in range(len(messages) - 1, -1, -1):
        usage = _get_usage_metadata(messages[i])
        if usage and usage.get("total_tokens"):
            total = usage["total_tokens"]
            tail = messages[i + 1:]
            estimated = estimate_messages_tokens(tail)
            return TokenAccounting(
                total_tokens=total + estimated,
                provider_usage_tokens=total,
                estimated_tokens=estimated,
                source="provider_usage_plus_estimate" if estimated > 0 else "provider_usage",
                is_exact=estimated == 0,
                usage_boundary_index=i,
            )

    # 没有 provider 用量信息 —— 退化为纯估算
    estimated = estimate_messages_tokens(messages)
    return TokenAccounting(
        total_tokens=estimated,
        provider_usage_tokens=0,
        estimated_tokens=estimated,
        source="estimate_only",
        is_exact=False,
        reason="no provider usage available",
    )


# ── 上下文统计（依赖压缩阈值，延迟导入避免循环依赖）──────────────
@dataclass(frozen=True)
class ContextStats:
    """上下文统计信息。"""

    estimated_tokens: int           # 估算 token 数
    total_tokens: int               # 总 token 数
    provider_usage_tokens: int      # 模型提供的用量 token 数
    context_window: int             # 模型上下文窗口大小
    effective_input: int            # 实际可用输入长度
    utilization: float              # 利用率（0~1）
    warning_level: str              # 警告级别
    accounting: TokenAccounting     # Token 核算详情


def compute_context_stats(messages: list[BaseMessage], model_name: str = "") -> ContextStats:
    """计算消息列表的上下文统计信息。"""
    # 延迟导入：避免 compact_core ↔ utils/token_estimator 循环依赖
    from src.compact.compact_core import (
        AUTOCOMPACT_UTILIZATION,
        BLOCKED_UTILIZATION,
        MICROCOMPACT_UTILIZATION,
    )
    from src.utils.model_context import get_model_context_window

    window, effective = get_model_context_window(model_name)
    accounting = token_count_with_estimation(messages)
    utilization = min(1.0, accounting.total_tokens / effective) if effective > 0 else 0.0

    if utilization >= BLOCKED_UTILIZATION:
        warning_level = "blocked"
    elif utilization >= AUTOCOMPACT_UTILIZATION:
        warning_level = "critical"
    elif utilization >= MICROCOMPACT_UTILIZATION:
        warning_level = "warning"
    else:
        warning_level = "normal"

    return ContextStats(
        estimated_tokens=accounting.estimated_tokens,
        total_tokens=accounting.total_tokens,
        provider_usage_tokens=accounting.provider_usage_tokens,
        context_window=window,
        effective_input=effective,
        utilization=utilization,
        warning_level=warning_level,
        accounting=accounting,
    )
