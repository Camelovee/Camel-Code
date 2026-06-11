"""Context Collapse：将一段消息区间折叠为 LLM 生成的摘要，仅替换模型可见视图。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from .compact_core import (
    SafeRun,
    build_message_groups,
    find_candidate_range,
    find_safe_runs,
    mark_protected_groups,
)
from .prompts import (
    build_context_collapse_summary_prompt,
    parse_summary_from_response,
)
from src.utils.token_estimator import estimate_messages_tokens

from .compact_core import (
    CONTEXT_COLLAPSE_KEEP_RECENT_MESSAGES,
    CONTEXT_COLLAPSE_MAX_FAILURES,
    CONTEXT_COLLAPSE_MAX_SPANS_PER_PASS,
    CONTEXT_COLLAPSE_MIN_TOKENS_TO_SAVE,
    CONTEXT_COLLAPSE_TARGET_USAGE,
    CONTEXT_COLLAPSE_UTILIZATION,
)
from src.utils.token_estimator import compute_context_stats

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


# ── Data classes ───────────────────────────────────────────────
@dataclass
class CollapseSpan:
    id: str                         # Span 唯一标识
    start_message_id: str           # 起始消息 ID
    end_message_id: str             # 结束消息 ID
    message_ids: list[str]          # 被折叠的消息 ID 列表
    summary: str                    # 摘要内容
    tokens_before: int              # 折叠前 token 数
    tokens_after: int               # 折叠后 token 数
    status: str = "staged"          # 状态（'staged' | 'committed'）
    created_at: float = field(default_factory=time.time)  # 创建时间戳
    reason: str = "context_pressure"  # 折叠原因


@dataclass
class ContextCollapseState:
    spans: list[CollapseSpan] = field(default_factory=list)  # 已折叠的区间列表
    enabled: bool = True                # 是否启用折叠
    consecutive_failures: int = 0       # 连续失败次数


@dataclass
class CollapseResult:
    messages: list[BaseMessage]         # 投影后的消息视图（模型可见）
    state: ContextCollapseState         # 折叠状态
    collapsed: bool                     # 是否发生了折叠
    span: CollapseSpan | None = None    # 本次折叠的单个区间
    spans: list[CollapseSpan] = field(default_factory=list)  # 所有已提交区间


@dataclass
class CollapseOptions:
    """折叠操作的参数配置。"""
    keep_recent: int = CONTEXT_COLLAPSE_KEEP_RECENT_MESSAGES
    min_tokens: int = CONTEXT_COLLAPSE_MIN_TOKENS_TO_SAVE
    target_usage: float = CONTEXT_COLLAPSE_TARGET_USAGE
    utilization_threshold: float = CONTEXT_COLLAPSE_UTILIZATION
    max_spans_per_pass: int = CONTEXT_COLLAPSE_MAX_SPANS_PER_PASS
    max_failures: int = CONTEXT_COLLAPSE_MAX_FAILURES
    current_tokens: int | None = None
    effective_input: int | None = None


@dataclass
class CollapseCandidate:
    """折叠候选区间的结构化描述。"""
    start_index: int              # 起始消息索引
    end_index: int                # 结束消息索引（不含）
    start_message_id: str         # 起始消息 ID
    end_message_id: str           # 结束消息 ID
    message_ids: list[str]        # 区间内所有消息 ID
    messages: list[BaseMessage]   # 区间内消息对象
    tokens_before: int            # 折叠前 token 数
    estimated_tokens_after: int   # 估算折叠后 token 数
    estimated_tokens_to_save: int # 估算节省 token 数


# ── Helpers ────────────────────────────────────────────────────
def _message_id(msg: BaseMessage, index: int) -> str:
    """获取消息唯一标识（优先使用 msg.id，否则用索引生成）。"""
    return getattr(msg, "id", None) or f"message-{index}"


def _estimate_summary_tokens(tokens_before: int) -> int:
    """估算折叠后摘要消息的 token 数（按原始 token 的 15% 估算，最低 128）。"""
    return max(128, int(tokens_before * 0.15))


def _build_summary_content(span: CollapseSpan) -> str:
    """构建 CollapseSpan 的摘要文本内容。"""
    return (
        "[Collapsed context summary]\n"
        f"This summary replaces messages {span.start_message_id} through {span.end_message_id} "
        "in the model-visible context only.\n"
        "The original transcript is preserved in the session/UI.\n\n"
        f"{span.summary}"
    )


def _build_summary_message(span: CollapseSpan) -> AIMessage:
    """将 CollapseSpan 包装为 AIMessage（带 context_summary 标记）。"""
    return AIMessage(
        content=_build_summary_content(span),
        additional_kwargs={
            "type": "context_summary",
            "compressed_count": len(span.message_ids),
            "timestamp": span.created_at,
        },
    )


def _committed_collapsed_ids(state: ContextCollapseState) -> set[str]:
    """收集所有已提交（committed）或已暂存（staged）折叠区间中的消息 ID 集合。"""
    ids = set()
    for span in state.spans:
        if span.status not in ("committed", "staged"):
            continue
        for mid in span.message_ids:
            ids.add(mid)
    return ids


def _desired_tokens_to_save(options: CollapseOptions) -> int:
    """计算期望节省的 token 数：当前 token 数 - 目标利用率下的 token 数。"""
    if (
        options.current_tokens is not None
        and options.effective_input is not None
        and options.effective_input > 0
    ):
        return max(
            options.min_tokens,
            int(options.current_tokens - options.effective_input * options.target_usage),
        )
    return options.min_tokens


def _fail(
    current_projected: list[BaseMessage],
    state: ContextCollapseState,
    max_failures: int,
) -> CollapseResult:
    """折叠失败处理：递增失败计数，若超过上限则禁用该层。"""
    failures = state.consecutive_failures + 1
    return CollapseResult(
        messages=current_projected,
        state=ContextCollapseState(
            spans=list(state.spans),
            enabled=state.enabled and failures < max_failures,
            consecutive_failures=failures,
        ),
        collapsed=False,
    )


def _build_candidate_from_run(
    messages: list[BaseMessage],
    run: SafeRun,
    options: CollapseOptions,
) -> CollapseCandidate | None:
    """从 SafeRun 中构建候选区间。"""
    desired = _desired_tokens_to_save(options)
    tokens = 0

    for i, g in enumerate(run.groups):
        tokens += g.tokens
        est_after = _estimate_summary_tokens(tokens)
        est_save = max(0, tokens - est_after)
        if est_save >= desired:
            selected = run.groups[:i + 1]
            first, last = selected[0], selected[-1]
            selected_msgs = messages[first.start:last.end]
            msg_ids = [_message_id(m, first.start + j) for j, m in enumerate(selected_msgs)]
            return CollapseCandidate(
                start_index=first.start,
                end_index=last.end,
                start_message_id=msg_ids[0],
                end_message_id=msg_ids[-1],
                message_ids=msg_ids,
                messages=selected_msgs,
                tokens_before=tokens,
                estimated_tokens_after=est_after,
                estimated_tokens_to_save=est_save,
            )

    # 即使没达到 desired，检查整个 run
    if run.tokens >= options.min_tokens:
        first, last = run.groups[0], run.groups[-1]
        selected_msgs = messages[first.start:last.end]
        msg_ids = [_message_id(m, first.start + j) for j, m in enumerate(selected_msgs)]
        est_after = _estimate_summary_tokens(run.tokens)
        est_save = max(0, run.tokens - est_after)
        if est_save >= options.min_tokens:
            return CollapseCandidate(
                start_index=first.start,
                end_index=last.end,
                start_message_id=msg_ids[0],
                end_message_id=msg_ids[-1],
                message_ids=msg_ids,
                messages=selected_msgs,
                tokens_before=run.tokens,
                estimated_tokens_after=est_after,
                estimated_tokens_to_save=est_save,
            )

    return None


# ── Projection ─────────────────────────────────────────────────
def project_collapsed_view(
    messages: list[BaseMessage],
    state: ContextCollapseState,
) -> list[BaseMessage]:
    """
    把"已折叠的旧消息"替换成"摘要消息"，
    让模型只看到摘要而非完整历史，
    同时保证被替换的消息仍然存在于原始列表中且连续不重叠
    """
    if not state.enabled or not state.spans:
        return messages
    
    projections: list[tuple[int, int, AIMessage]] = [] # start end context压缩后的AIMessage
    for span in state.spans:
        if span.status != "committed" or not span.message_ids:
            continue

        # 区间验证：对每个已提交的 span，验证其消息是否仍然存在于当前消息列表中，且是连续的
        index_by_id = {_message_id(m, i): i for i, m in enumerate(messages)}
        indices = [] # 存储所有span里的消息的idx
        for mid in span.message_ids:
            idx = index_by_id.get(mid)
            if idx is None:
                break
            indices.append(idx)

        if len(indices) != len(span.message_ids):
            continue
        # 验证连续性
        if not all(indices[i] == indices[i - 1] + 1 for i in range(1, len(indices))):
            continue

        start, end = indices[0], indices[-1] + 1
        if _message_id(messages[start], start) != span.start_message_id:
            continue
        if _message_id(messages[end - 1], end - 1) != span.end_message_id:
            continue

        projections.append((start, end, _build_summary_message(span)))

    projections.sort(key=lambda x: x[0])

    if not projections:
        return messages

    result: list[BaseMessage] = []
    occupied = set()
    cursor = 0

    # 无重叠替换 按起始位置排序后，逐个替换为 AIMessage 类型的摘要消息
    for start, end, summary_msg in projections:
        overlaps = any(i in occupied for i in range(start, end))
        if overlaps:
            continue

        while cursor < start:
            result.append(messages[cursor])
            cursor += 1

        result.append(summary_msg)
        for i in range(start, end):
            occupied.add(i)
        cursor = end

    while cursor < len(messages):
        result.append(messages[cursor])
        cursor += 1

    return result


# ── Candidate finding ──────────────────────────────────────────
def find_collapse_candidate(
    messages: list[BaseMessage],
    state: ContextCollapseState,
    options: CollapseOptions | None = None,
) -> CollapseCandidate | None:
    """找到候选去 context collapsing 的消息"""
    if not messages:
        return None

    if options is None:
        options = CollapseOptions()

    start, end, reason = find_candidate_range(
        messages, keep_recent=options.keep_recent, min_remove=1,
    )
    if reason:
        return None

    collapsed_ids = _committed_collapsed_ids(state)

    def extra_predicate(g) -> bool:
        return any(
            _message_id(m, g.start + j) in collapsed_ids
            for j, m in enumerate(g.messages)
        )

    groups = build_message_groups(messages, closed_check=True)
    mark_protected_groups(groups, start, end, extra_predicate=extra_predicate)

    for run in find_safe_runs(groups):
        candidate = _build_candidate_from_run(messages, run, options)
        if candidate:
            return candidate

    return None


# ── Main function ──────────────────────────────────────────────
def apply_context_collapse(
    messages: list[BaseMessage],
    model_name: str,
    model: BaseChatModel,
    state: ContextCollapseState | None = None,
    options: CollapseOptions | None = None,
) -> CollapseResult:
    """
    如果utilization超过阀值出发context collapse
    """
    if state is None:
        state = ContextCollapseState()
    if options is None:
        options = CollapseOptions()

    if not state.enabled:
        return CollapseResult(messages=messages, state=state, collapsed=False)

    current_projected = project_collapsed_view(messages, state)
    stats = compute_context_stats(current_projected, model_name)
    if stats.utilization < options.utilization_threshold:
        return CollapseResult(messages=current_projected, state=state, collapsed=False)

    planned_spans: list[CollapseSpan] = []
    max_spans = max(1, options.max_spans_per_pass)

    for pass_num in range(max_spans):
        selection_state = ContextCollapseState(
            spans=list(state.spans) + planned_spans,
            enabled=True,
        )
        projected = project_collapsed_view(messages, selection_state)
        stats = compute_context_stats(projected, model_name)

        if planned_spans and stats.utilization <= options.target_usage:
            break

        candidate = find_collapse_candidate(
            messages,
            selection_state,
            CollapseOptions(
                keep_recent=options.keep_recent,
                min_tokens=options.min_tokens,
                current_tokens=stats.total_tokens,
                effective_input=stats.effective_input,
                target_usage=options.target_usage,
            ),
        )
        if not candidate:
            break

        summary_prompt = build_context_collapse_summary_prompt(
            "\n\n".join(
                f"[{m.type}]: {str(m.content)[:800]}"
                for m in candidate.messages
            ),
        )
        summary_request = [
            SystemMessage(content="You are a precise assistant that summarizes older coding-session context without inventing details."),
            HumanMessage(content=summary_prompt),
        ]

        try:
            response = model.invoke(summary_request)
            content = str(response.content).strip()
            if not content:
                return _fail(current_projected, state, options.max_failures)

            summary = parse_summary_from_response(content)
            if not summary:
                return _fail(current_projected, state, options.max_failures)

            now = time.time()
            draft = CollapseSpan(
                id=f"collapse-{now}-{pass_num}-{candidate.start_message_id}",
                start_message_id=candidate.start_message_id,
                end_message_id=candidate.end_message_id,
                message_ids=candidate.message_ids,
                summary=summary,
                tokens_before=candidate.tokens_before,
                tokens_after=0,
                status="staged",
                created_at=now,
            )
            summary_tokens = estimate_messages_tokens([_build_summary_message(draft)])
            tokens_save = max(0, candidate.tokens_before - summary_tokens)
            if tokens_save < options.min_tokens:
                if planned_spans:
                    break
                return _fail(current_projected, state, options.max_failures)

            draft.tokens_after = summary_tokens
            planned_spans.append(draft)
        except Exception:
            return _fail(current_projected, state, options.max_failures)

    if not planned_spans:
        return CollapseResult(messages=current_projected, state=state, collapsed=False)

    # Commit spans
    committed = [
        CollapseSpan(
            id=s.id,
            start_message_id=s.start_message_id,
            end_message_id=s.end_message_id,
            message_ids=s.message_ids,
            summary=s.summary,
            tokens_before=s.tokens_before,
            tokens_after=s.tokens_after,
            status="committed",
            created_at=s.created_at,
            reason=s.reason,
        )
        for s in planned_spans
    ]

    next_state = ContextCollapseState(
        spans=list(state.spans) + committed,
        enabled=True,
        consecutive_failures=0,
    )

    return CollapseResult(
        messages=project_collapsed_view(messages, next_state),
        state=next_state,
        collapsed=True,
        span=committed[0] if committed else None,
        spans=committed,
    )
