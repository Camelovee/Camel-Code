"""微压缩：轻量级、确定性地清理旧的工具调用结果。

对应 MiniCode 的 microcompact.ts：
当上下文利用率超过阈值时，用清除标记替换旧工具结果内容。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, ToolMessage

from .compact_core import (
    CLEAR_MARKER,
    KEEP_RECENT_TOOL_RESULTS,
    MICROCOMPACT_UTILIZATION,
)
from src.utils.token_estimator import compute_context_stats

# 可安全清理的工具名称列表
COMPACTABLE_TOOLS = frozenset([
    "bash",
    "glob",
    "read_file",
    "list_files",
    "web_search",
    "web_fetch",
])


def microcompact(messages: list[BaseMessage], model_name: str = "") -> list[BaseMessage]:
    """用清除标记替换旧的可压缩工具结果。

    如果有变更则返回新的列表，否则返回原列表。
    """
    stats = compute_context_stats(messages, model_name)
    if stats.utilization < MICROCOMPACT_UTILIZATION:
        return messages

    # 找出所有可压缩工具结果的索引
    tool_result_indices: list[int] = []
    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage):
            tool_name = msg.name or ""
            if tool_name in COMPACTABLE_TOOLS:
                tool_result_indices.append(i)

    if len(tool_result_indices) <= KEEP_RECENT_TOOL_RESULTS:
        return messages

    # 标记旧的需要清除的索引 最近的要保留
    keep_from = len(tool_result_indices) - KEEP_RECENT_TOOL_RESULTS
    indices_to_clear = set(tool_result_indices[:keep_from])

    changed = False
    result: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        if i in indices_to_clear and isinstance(msg, ToolMessage):
            if msg.content != CLEAR_MARKER:
                changed = True
                result.append(ToolMessage(
                    content=CLEAR_MARKER,
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                ))
            else:
                result.append(msg)
        else:
            result.append(msg)

    return result if changed else messages
