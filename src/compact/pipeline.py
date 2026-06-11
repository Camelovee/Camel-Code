"""压缩管道：编排四层上下文压缩。

Layer 1 — Snip Compact：   移除安全的中间区间
Layer 2 — Microcompact：      清除旧工具结果内容
Layer 3 — Context Collapse：   用 LLM 摘要替换区间（模型可见）
Layer 4 — Auto Compact：    基于 LLM 的完整对话摘要（仅第 0 步）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage

from .auto_compact import auto_compact, AutoCompactState, CompactResult
from .context_collapse import apply_context_collapse, ContextCollapseState, CollapseResult
from .microcompact import microcompact
from .snip_compact import snip_compact, SnipResult
from src.utils.token_estimator import compute_context_stats
from .tool_result_storage import ReplacementState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


# ── 数据类 ───────────────────────────────────────────────────
@dataclass
class CompactPipelineResult:
    messages: list[BaseMessage]          # 压缩后的完整消息
    model_messages: list[BaseMessage]    # 模型可见视图（含折叠摘要）
    snip_result: SnipResult | None = None              # Layer 1 裁剪结果
    collapse_result: CollapseResult | None = None      # Layer 3 折叠结果
    auto_compact_result: CompactResult | None = None   # Layer 4 摘要结果
    stats_before: dict = field(default_factory=dict)   # 压缩前统计
    stats_after: dict = field(default_factory=dict)    # 压缩后统计


@dataclass
class CompactPipelineState:
    """跨轮次的持久状态。"""
    auto_compact: AutoCompactState = field(default_factory=AutoCompactState)            # Layer 4 状态
    context_collapse: ContextCollapseState = field(default_factory=ContextCollapseState)  # Layer 3 状态
    tool_result_replacement: ReplacementState = field(default_factory=ReplacementState)  # Layer 2 状态
    snipped_this_turn: bool = False                                                      # 本轮是否已执行 snip

    def reset_turn(self) -> None:
        self.snipped_this_turn = False


# ── 管道 ─────────────────────────────────────────────────────
def run_compact_pipeline(
    messages: list[BaseMessage],
    model: BaseChatModel,
    model_name: str = "",
    step: int = 0,
    state: CompactPipelineState | None = None,
) -> CompactPipelineResult:
    """Run the four-layer compression pipeline.

    Returns CompactPipelineResult with both full messages and model-visible view.
    """
    if state is None:
        state = CompactPipelineState()

    original = list(messages)
    stats_before = compute_context_stats(original, model_name)

    # Layer 1: Snip Compact (once per turn)
    snip_result: SnipResult | None = None
    if not state.snipped_this_turn:
        snip_result = snip_compact(original, model_name)
        if snip_result.did_snip:
            original = snip_result.messages
            state.snipped_this_turn = True

    # Layer 2: Microcompact
    original = microcompact(original, model_name)

    # Layer 3: Context Collapse
    collapse_result: CollapseResult | None = None
    if model_name:
        collapse_result = apply_context_collapse(
            original, model_name, model,
            state=state.context_collapse,
        )
        if collapse_result.collapsed:
            state.context_collapse = collapse_result.state
        model_view = collapse_result.messages
    else:
        model_view = list(original)

    # Layer 4: Auto Compact (only on step 0)
    auto_result = None
    if step == 0 and model_name:
        stats = compute_context_stats(model_view, model_name)
        if stats.warning_level in ("critical", "blocked"):
            from .auto_compact import compact_conversation
            auto_result = compact_conversation(model_view, model)
            if auto_result:
                original = auto_result.messages
                model_view = list(original)
                state.auto_compact.reset()
                # Reset collapse state after auto compact
                state.context_collapse = ContextCollapseState()

    stats_after = compute_context_stats(model_view, model_name)

    return CompactPipelineResult(
        messages=original,
        model_messages=model_view,
        snip_result=snip_result,
        collapse_result=collapse_result,
        auto_compact_result=auto_result,
        stats_before={
            "total_tokens": stats_before.total_tokens,
            "utilization": stats_before.utilization,
            "warning_level": stats_before.warning_level,
        },
        stats_after={
            "total_tokens": stats_after.total_tokens,
            "utilization": stats_after.utilization,
            "warning_level": stats_after.warning_level,
        },
    )
