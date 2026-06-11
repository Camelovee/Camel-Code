"""Snip 压缩：移除对话历史中间的一段安全区间。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage

from .compact_core import (
    SafeRun,
    build_message_groups,
    find_candidate_range,
    find_safe_runs,
    mark_protected_groups,
)
from src.utils.model_context import DEFAULT_EFFECTIVE_INPUT
from src.utils.token_estimator import estimate_messages_tokens

from .compact_core import (
    SNIP_COMPACT_THRESHOLD,
    SNIP_KEEP_RECENT_MESSAGES,
    SNIP_MIN_MESSAGES_TO_REMOVE,
    SNIP_MIN_TOKENS_TO_FREE,
    SNIP_TARGET_USAGE,
)
from src.utils.token_estimator import compute_context_stats

if TYPE_CHECKING:
    from src.utils.token_estimator import ContextStats


# ── 数据类 ───────────────────────────────────────────────────
@dataclass
class SnipResult:
    messages: list[BaseMessage]     # 裁剪后的消息列表
    did_snip: bool                  # 是否执行了裁剪
    tokens_before: int              # 裁剪前 token 数
    tokens_after: int               # 裁剪后 token 数
    tokens_freed: int               # 释放的 token 数
    removed_count: int = 0          # 移除的消息数
    reason: str = ""                # 未裁剪原因或裁剪说明


# ── 辅助函数 ─────────────────────────────────────────────────
def _select_deletion(run: SafeRun, desired_tokens_to_free: int) -> tuple[int, int, int, int]:
    """在安全 run 中选择要删除的区间。

    Returns:
        (start, end, tokens, messages_count)
    """
    tokens = 0
    messages_count = 0
    end_group_index = -1

    for i, g in enumerate(run.groups):
        tokens += g.tokens
        messages_count = g.end - run.start
        end_group_index = i
        if tokens >= desired_tokens_to_free and messages_count >= SNIP_MIN_MESSAGES_TO_REMOVE:
            break

    end_group = run.groups[max(0, end_group_index)]
    return run.start, end_group.end, tokens, messages_count


def _build_boundary_message(removed_count: int, tokens_freed: int) -> AIMessage:
    """构建 snip 边界消息。"""
    content = (
        "[已裁剪之前的对话片段]\n\n"
        "为了节省上下文空间，移除了之前对话的中间部分。\n\n"
        f"移除范围：\n"
        f"- 消息数：{removed_count}\n"
        f"- 大约释放 token：{max(0, tokens_freed)}\n\n"
        "最近的对话和当前任务上下文已被保留。"
    )
    return AIMessage(
        content=content,
        additional_kwargs={
            "type": "snip_boundary",
            "removed_count": removed_count,
            "tokens_freed": tokens_freed,
            "timestamp": time.time(),
        },
    )


# ── 主函数 ───────────────────────────────────────────────────
def snip_compact(
    messages: list[BaseMessage],
    model_name: str = "",
) -> SnipResult:
    """从消息中去掉一段安全的中间区间。

    如果执行了裁剪，返回包含新消息列表的 SnipResult。
    """
    tokens_before = estimate_messages_tokens(messages)
    stats = compute_context_stats(messages, model_name)
    effective = stats.effective_input or DEFAULT_EFFECTIVE_INPUT
    utilization = stats.utilization if stats.total_tokens > 0 else tokens_before / effective

    if utilization < SNIP_COMPACT_THRESHOLD:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason="below_threshold",
        )

    start, end, reason = find_candidate_range(
        messages,
        keep_recent=SNIP_KEEP_RECENT_MESSAGES,
        min_remove=SNIP_MIN_MESSAGES_TO_REMOVE,
    )
    if reason:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason=reason,
        )

    groups = build_message_groups(messages)
    mark_protected_groups(groups, start, end)

    safe_runs = sorted(
        [r for r in find_safe_runs(groups)
         if r.messages_count >= SNIP_MIN_MESSAGES_TO_REMOVE
         and r.tokens >= SNIP_MIN_TOKENS_TO_FREE],
        key=lambda r: (-r.tokens, -r.messages_count, r.start),
    )

    if not safe_runs:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason="no_safe_interval",
        )

    best_run = safe_runs[0]
    target_tokens = int(effective * SNIP_TARGET_USAGE)
    desired = max(SNIP_MIN_TOKENS_TO_FREE, stats.total_tokens - target_tokens)
    del_start, del_end, del_tokens, del_count = _select_deletion(best_run, desired)

    if del_count < SNIP_MIN_MESSAGES_TO_REMOVE:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason="below_min_messages",
        )

    boundary_msg = _build_boundary_message(del_count, del_tokens)
    boundary_tokens = estimate_messages_tokens([boundary_msg])
    estimated_freed = max(0, del_tokens - boundary_tokens)

    if estimated_freed < SNIP_MIN_TOKENS_TO_FREE:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason="below_min_tokens",
        )

    new_messages = messages[:del_start] + [boundary_msg] + messages[del_end:]
    tokens_after = estimate_messages_tokens(new_messages)
    tokens_freed = max(0, tokens_before - tokens_after)

    if tokens_after >= tokens_before:
        return SnipResult(
            messages=messages, did_snip=False,
            tokens_before=tokens_before, tokens_after=tokens_before,
            tokens_freed=0, reason="no_token_reduction",
        )

    return SnipResult(
        messages=new_messages,
        did_snip=True,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        tokens_freed=tokens_freed,
        removed_count=del_count,
        reason="snipped_safe_middle_interval",
    )
