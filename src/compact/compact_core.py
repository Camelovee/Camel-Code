"""Compact 公共核心：消息分组、保护标记、候选区间查找。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from src.utils.token_estimator import estimate_messages_tokens


PROTECTED_TOOL_NAMES = frozenset([
    "edit_file", "modify_file", "patch_file", "write_file", "apply_patch",
])
ERROR_MARKERS = ["error", "failed", "failure", "exception", "traceback", "permission denied"]

# ── 压缩策略常量 ───────────────────────────────────────────────
# microcompact 清理旧工具结果时替换内容的占位标记
CLEAR_MARKER = "[Output cleared for context space]"

# ── 四层压缩触发阈值（利用率 = 当前 token 数 / 有效输入长度）──
# 第 2 层 microcompact：利用率 ≥ 50% 时开始清理旧工具结果
MICROCOMPACT_UTILIZATION = 0.50
# 第 4 层 auto-compact：利用率 ≥ 85% 时触发 LLM 全量摘要
AUTOCOMPACT_UTILIZATION = 0.85
# 阻塞阈值：利用率 ≥ 95% 时标记为 blocked，可能截断或报错
BLOCKED_UTILIZATION = 0.95

# ── 第 1 层 snip-compact 参数 ──
SNIP_COMPACT_THRESHOLD = 0.70       # 利用率 ≥ 70% 时触发裁剪
SNIP_TARGET_USAGE = 0.60            # 裁剪后目标利用率降至 60%
SNIP_KEEP_RECENT_MESSAGES = 12      # 尾部至少保留 12 条消息不被裁剪
SNIP_MIN_MESSAGES_TO_REMOVE = 6     # 单次至少删除 6 条消息才值得执行
SNIP_MIN_TOKENS_TO_FREE = 2_000     # 单次至少释放 2000 token 才执行

# ── 第 3 层 context-collapse 参数 ──
CONTEXT_COLLAPSE_UTILIZATION = 0.75     # 利用率 ≥ 75% 时触发折叠
CONTEXT_COLLAPSE_TARGET_USAGE = 0.65    # 折叠后目标利用率降至 65%
CONTEXT_COLLAPSE_KEEP_RECENT_MESSAGES = 12  # 尾部至少保留 12 条
CONTEXT_COLLAPSE_MIN_TOKENS_TO_SAVE = 2_000  # 单次至少节省 2000 token
CONTEXT_COLLAPSE_MAX_SPANS_PER_PASS = 2      # 每轮最多折叠 2 个 span
CONTEXT_COLLAPSE_MAX_FAILURES = 3           # 连续失败 3 次后禁用该层

# ── 保留策略 ──
KEEP_RECENT_TOOL_RESULTS = 3        # microcompact 保留最近 3 个工具结果
MIN_KEEP_MESSAGES = 6               # 自动压缩时至少保留 6 条消息
MAX_KEEP_TOKENS = 40_000            # 自动压缩时尾部最多保留 40K token


@dataclass
class MessageGroup:
    start: int                      # 消息起始索引
    end: int                        # 消息结束索引
    messages: list[BaseMessage]     # 消息列表
    tokens: int                     # 估算 token 数
    protected: bool = False         # 是否受保护（不可压缩）
    reason: str | None = None       # 保护原因


@dataclass
class SafeRun:
    groups: list[MessageGroup]      # 消息组列表
    start: int                      # 起始索引
    end: int                        # 结束索引
    messages_count: int             # 消息数量
    tokens: int                     # 总 token 数


def is_boundary_message(msg: BaseMessage) -> bool:
    """判断消息是否为边界消息（System 或摘要/裁剪标记），边界消息不可被折叠。"""
    if isinstance(msg, SystemMessage):
        return True
    if getattr(msg, "type", "") in ("context_summary", "snip_boundary"):
        return True
    if isinstance(msg, AIMessage):
        return msg.additional_kwargs.get("type") in ("context_summary", "snip_boundary")
    return False


def is_protected_tool_name(name: str) -> bool:
    """判断工具名是否为受保护操作（文件写入/编辑类），这类工具的结果不可被折叠。"""
    n = name.strip().lower()
    return n in PROTECTED_TOOL_NAMES or any(k in n for k in ("patch", "write", "edit", "modify"))


def looks_like_error(msg: BaseMessage) -> bool:
    """判断消息内容是否包含错误标记词，错误信息附近的消息应受保护。"""
    return any(m in str(getattr(msg, "content", "")).lower() for m in ERROR_MARKERS)


def _tool_group_is_closed(messages: list[BaseMessage]) -> bool:
    """检查一组消息中的工具调用是否都有对应的 ToolMessage 结果返回。"""
    call_ids = {tc.get("id", "") for msg in messages if isinstance(msg, AIMessage) and msg.tool_calls for tc in msg.tool_calls}
    result_ids = {msg.tool_call_id for msg in messages if isinstance(msg, ToolMessage)}
    if not call_ids and not result_ids:
        return True
    if not call_ids or not result_ids:
        return False
    return call_ids == result_ids


def build_message_groups(messages: list[BaseMessage], closed_check: bool = False) -> list[MessageGroup]:
    """将消息列表按工具调用关系分组。工具调用 AIMessage 与其 ToolMessage 结果聚合为一组。"""
    groups: list[MessageGroup] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if isinstance(msg, AIMessage) and msg.tool_calls:
            paired, cursor = [msg], i + 1
            call_ids = {tc.get("id", "") for tc in msg.tool_calls}
            while cursor < len(messages) and isinstance(messages[cursor], ToolMessage) and messages[cursor].tool_call_id in call_ids:
                paired.append(messages[cursor])
                cursor += 1
            protected = closed_check and not _tool_group_is_closed(paired)
            groups.append(MessageGroup(start=i, end=cursor, messages=paired, tokens=estimate_messages_tokens(paired),
                                       protected=protected, reason="unclosed_tool_group" if protected else None))
            i = cursor
            continue
        if isinstance(msg, ToolMessage):
            groups.append(MessageGroup(start=i, end=i + 1, messages=[msg], tokens=estimate_messages_tokens([msg]),
                                       protected=True, reason="orphan_tool_result"))
            i += 1
            continue
        groups.append(MessageGroup(start=i, end=i + 1, messages=[msg], tokens=estimate_messages_tokens([msg])))
        i += 1
    return groups


def _group_has_protected_tool(group: MessageGroup) -> bool:
    """检查组内是否包含受保护工具（文件写入/编辑类）的调用或结果。"""
    for msg in group.messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            if any(is_protected_tool_name(tc.get("name", "")) for tc in msg.tool_calls):
                return True
        elif isinstance(msg, ToolMessage) and is_protected_tool_name(msg.name or ""):
            return True
    return False


def protect_nearby(groups: list[MessageGroup], index: int, reason: str) -> None:
    """将指定组及其前后各一组标记为保护状态。"""
    for i in range(max(0, index - 1), min(len(groups), index + 2)):
        if not groups[i].protected:
            groups[i].protected = True
            groups[i].reason = reason


def mark_protected_groups(
    groups: list[MessageGroup],
    candidate_start: int,
    candidate_end: int,
    extra_predicate: Callable[[MessageGroup], bool] | None = None,
) -> None:
    """标记不可折叠的消息组：候选范围外、边界消息、含受保护工具、含错误信息。"""
    for g in groups:
        if g.start < candidate_start or g.end > candidate_end:
            g.protected, g.reason = True, "outside_candidate_range"
        elif any(is_boundary_message(m) for m in g.messages):
            g.protected, g.reason = True, "boundary_message"
    for i, g in enumerate(groups):
        if _group_has_protected_tool(g):
            protect_nearby(groups, i, "near_file_edit")
        if any(looks_like_error(m) for m in g.messages):
            protect_nearby(groups, i, "near_important_error")
    if extra_predicate:
        for g in groups:
            if not g.protected and extra_predicate(g):
                g.protected, g.reason = True, "extra_predicate"


def find_safe_runs(groups: list[MessageGroup]) -> list[SafeRun]:
    """从已标记保护状态的分组中提取所有连续的未保护区间（SafeRun）。"""
    runs, current = [], []
    def flush():
        nonlocal current
        if current:
            first, last = current[0], current[-1]
            runs.append(SafeRun(groups=current, start=first.start, end=last.end,
                                messages_count=last.end - first.start, tokens=sum(g.tokens for g in current)))
            current = []
    for g in groups:
        (flush() if g.protected else current.append(g))
    flush()
    return runs


def find_candidate_range(messages: list[BaseMessage], keep_recent: int, min_remove: int) -> tuple[int, int, str]:
    """确定可被折叠的候选区间 [start, end)，保留尾部最近消息和边界消息。"""
    if len(messages) <= keep_recent + min_remove:
        return 0, 0, "too_few_messages"
    keep_start = max(0, len(messages) - keep_recent)
    last_user_index = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), -1)
    end = min(keep_start, last_user_index if last_user_index >= 0 else len(messages))
    if end <= 0:
        return 0, 0, "no_middle_range"
    start = next((i + 1 for i in range(end) if is_boundary_message(messages[i])), 0)
    if end - start < min_remove:
        return start, end, "candidate_range_too_small"
    return start, end, ""
