"""自动压缩：基于 LLM 的对话摘要。

对应 MiniCode 的 compact.ts 和 auto-compact.ts：
找出保留边界，用摘要替换早期消息。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from .prompts import build_compact_summary_prompt, parse_summary_from_response
from src.utils.token_estimator import estimate_messages_tokens

from .compact_core import (
    MAX_KEEP_TOKENS,
    MIN_KEEP_MESSAGES,
)
from src.utils.token_estimator import compute_context_stats

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


@dataclass
class CompactResult:
    messages: list[BaseMessage]     # 压缩后的消息列表
    summary_content: str            # 生成的摘要内容
    removed_count: int              # 已移除的消息数
    tokens_before: int              # 压缩前 token 数
    tokens_after: int               # 压缩后 token 数


def _message_to_text(msg: BaseMessage) -> str:
    """将消息转换为用于摘要的文本表示。"""
    from langchain_core.messages import AIMessage, ToolMessage

    role = msg.type
    if role == "system":
        return "[System]: (system prompt)"
    elif role == "human":
        return f"[User]: {msg.content}"
    elif role == "ai":
        content = str(msg.content) if msg.content else ""
        if len(content) > 500:
            content = content[:500] + "... (truncated)"
        return f"[Assistant]: {content}"
    elif role == "tool":
        tool_msg = msg
        content = str(tool_msg.content)
        if len(content) > 500:
            content = content[:500] + "... (truncated)"
        name = getattr(tool_msg, "name", "unknown")
        return f"[Tool Result: {name}]: {content}"
    else:
        return f"[{role}]: {str(msg.content)[:500]}"


def _messages_to_text(messages: list[BaseMessage]) -> str:
    return "\n\n".join(_message_to_text(m) for m in messages)


def _find_retention_boundary(messages: list[BaseMessage]) -> int:
    """找出保留边界：该索引之前的消息将被压缩。"""
    token_sum = 0
    boundary = len(messages)

    for i in range(len(messages) - 1, 0, -1):
        msg_tokens = estimate_messages_tokens([messages[i]])
        if token_sum + msg_tokens > MAX_KEEP_TOKENS:
            break
        token_sum += msg_tokens
        boundary = i

    # Ensure at least MIN_KEEP_MESSAGES
    min_boundary = max(1, len(messages) - MIN_KEEP_MESSAGES)
    boundary = min(boundary, min_boundary)

    # If keeping almost everything, enforce minimum
    if boundary <= 1 and len(messages) > MIN_KEEP_MESSAGES + 1:
        boundary = max(1, len(messages) - MIN_KEEP_MESSAGES)

    return boundary


def compact_conversation(
    messages: list[BaseMessage],
    model: BaseChatModel,
) -> CompactResult | None:
    """摘要化历史消息，并用摘要替换它们。"""
    if len(messages) <= 2:
        return None

    tokens_before = estimate_messages_tokens(messages)

    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    if len(non_system) <= MIN_KEEP_MESSAGES:
        return None

    boundary = _find_retention_boundary(messages)
    messages_to_compress = messages[1:boundary]  # Skip system prompt
    messages_to_keep = messages[boundary:]

    if not messages_to_compress:
        return None

    conversation_text = _messages_to_text(messages_to_compress)
    summary_prompt = build_compact_summary_prompt(conversation_text)

    summary_messages = [
        SystemMessage(content="You are a helpful assistant that summarizes conversations concisely."),
        HumanMessage(content=summary_prompt),
    ]

    try:
        response = model.invoke(summary_messages)
        summary_content = parse_summary_from_response(str(response.content))
        if not summary_content:
            return None

        from langchain_core.messages import AIMessage
        summary_msg = AIMessage(
            content=summary_content,
            additional_kwargs={
                "type": "context_summary",
                "compressed_count": len(messages_to_compress),  # 已压缩消息数
                "timestamp": __import__("time").time(),
            },
        )

        new_messages = system_messages + [summary_msg] + messages_to_keep
        tokens_after = estimate_messages_tokens(new_messages)

        return CompactResult(
            messages=new_messages,
            summary_content=summary_content,
            removed_count=len(messages_to_compress),
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )
    except Exception:
        return None


# ── 自动压缩状态 ────────────────────────────────────────────
@dataclass
class AutoCompactState:
    consecutive_failures: int = 0   # 连续失败次数
    disabled: bool = False          # 是否已禁用

    def reset(self) -> None:
        self.consecutive_failures = 0
        self.disabled = False

    def record_failure(self, max_failures: int = 3) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= max_failures:
            self.disabled = True

    def record_success(self) -> None:
        self.consecutive_failures = 0


_MAX_FAILURES = 3


def auto_compact(
    messages: list[BaseMessage],
    model_name: str,
    model: BaseChatModel,
    state: AutoCompactState | None = None,
) -> CompactResult | None:
    """在上下文利用率过高时自动压缩。"""
    if state is None:
        state = AutoCompactState()

    if state.disabled:
        return None

    stats = compute_context_stats(messages, model_name)
    if stats.utilization < 0.85:  # AUTOCOMPACT_UTILIZATION
        return None

    try:
        result = compact_conversation(messages, model)
        if result:
            state.record_success()
            return result
        state.record_failure(_MAX_FAILURES)
        return None
    except Exception:
        state.record_failure(_MAX_FAILURES)
        return None
