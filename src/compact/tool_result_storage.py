"""
Tool result storage: persist large outputs to disk and apply budget.

Mirrors MiniCode's tool-result-storage.ts:
- replace_large_tool_result: persist a single oversized result
- apply_tool_result_budget: limit total size of a batch
"""
from __future__ import annotations

import pathlib
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import ToolMessage

if TYPE_CHECKING:
    pass

# ── Constants ──────────────────────────────────────────────────
DEFAULT_MAX_SIZE = 50_000
MAX_BATCH_SIZE = 200_000
PREVIEW_SIZE = 2_000
PERSISTED_TAG = "<persisted-output>"
PERSISTED_CLOSE = "</persisted-output>"

_TOOL_RESULTS_DIR = pathlib.Path(".tool_results")


# ── Data classes ───────────────────────────────────────────────
@dataclass
class ReplacementState:
    seen_ids: set[str] = field(default_factory=set)          # 已处理的 tool_call_id 集合
    replacements: dict[str, str] = field(default_factory=dict)  # tool_call_id → 替换内容映射


def _tool_results_dir() -> pathlib.Path:
    _TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return _TOOL_RESULTS_DIR


def _persist_path(tool_use_id: str) -> pathlib.Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in tool_use_id)
    return _tool_results_dir() / f"{safe}.txt"


def _generate_preview(content: str) -> tuple[str, bool]:
    if len(content) <= PREVIEW_SIZE:
        return content, False
    last_nl = content[:PREVIEW_SIZE].rfind("\n")
    cut = last_nl if last_nl > PREVIEW_SIZE * 0.5 else PREVIEW_SIZE
    return content[:cut], True


def _format_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M chars"
    if n >= 1_000:
        return f"{n // 1_000}K chars"
    return f"{n} chars"


def _persist(content: str, tool_use_id: str) -> tuple[str, int, str] | None:
    path = _persist_path(tool_use_id)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError:
        return None
    preview, has_more = _generate_preview(content)
    return str(path), len(content), preview


def _build_persisted_message(filepath: str, size: int, preview: str) -> str:
    return (
        f"{PERSISTED_TAG}\n"
        f"Output too large ({_format_size(size)}). Full output saved to: {filepath}\n\n"
        f"Preview:\n{preview}\n"
        f"{PERSISTED_CLOSE}"
    )


def is_persisted(content: str) -> bool:
    return content.startswith(PERSISTED_TAG)


def replace_large_tool_result(
    msg: ToolMessage,
    state: ReplacementState | None = None,
    threshold: int = DEFAULT_MAX_SIZE,
) -> ToolMessage:
    """Replace a single oversized tool result with a persisted reference."""
    content = str(msg.content) if msg.content is not None else ""
    tool_use_id = msg.tool_call_id

    if state:
        prev = state.replacements.get(tool_use_id)
        if prev is not None:
            return ToolMessage(content=prev, tool_call_id=tool_use_id, name=msg.name)

    if not content.strip():
        if state:
            state.seen_ids.add(tool_use_id)
        empty_msg = f"({msg.name or 'tool'} completed with no output)"
        return ToolMessage(content=empty_msg, tool_call_id=tool_use_id, name=msg.name)

    if is_persisted(content):
        if state:
            state.seen_ids.add(tool_use_id)
            state.replacements[tool_use_id] = content
        return msg

    if len(content) <= threshold:
        return msg

    persisted = _persist(content, tool_use_id)
    if not persisted:
        return msg

    filepath, size, preview = persisted
    replacement = _build_persisted_message(filepath, size, preview)
    if state:
        state.seen_ids.add(tool_use_id)
        state.replacements[tool_use_id] = replacement

    return ToolMessage(content=replacement, tool_call_id=tool_use_id, name=msg.name)


def apply_tool_result_budget(
    msgs: list[ToolMessage],
    state: ReplacementState,
    limit: int = MAX_BATCH_SIZE,
) -> list[ToolMessage]:
    """Apply size budget to a batch of tool results."""
    if not msgs:
        return msgs

    replacement_map: dict[str, str] = {}
    fresh: list[tuple[str, str, int]] = []  # (tool_use_id, content, size)
    visible_size = 0

    for msg in msgs:
        content = str(msg.content) if msg.content is not None else ""
        tid = msg.tool_call_id

        prev = state.replacements.get(tid)
        if prev is not None:
            replacement_map[tid] = prev
            visible_size += len(prev)
            continue

        if tid in state.seen_ids:
            visible_size += len(content)
            continue

        if not content.strip():
            state.seen_ids.add(tid)
            continue

        if is_persisted(content):
            state.seen_ids.add(tid)
            state.replacements[tid] = content
            replacement_map[tid] = content
            visible_size += len(content)
            continue

        visible_size += len(content)
        fresh.append((tid, content, len(content)))

    fresh.sort(key=lambda x: (-x[2], x[0]))

    for tid, content, size in fresh:
        if visible_size <= limit:
            break
        persisted = _persist(content, tid)
        state.seen_ids.add(tid)
        if not persisted:
            continue
        filepath, psize, preview = persisted
        replacement = _build_persisted_message(filepath, psize, preview)
        replacement_map[tid] = replacement
        state.replacements[tid] = replacement
        visible_size = visible_size - size + len(replacement)

    for tid, _, _ in fresh:
        state.seen_ids.add(tid)

    return [
        ToolMessage(
            content=replacement_map.get(msg.tool_call_id, msg.content),
            tool_call_id=msg.tool_call_id,
            name=msg.name,
        )
        for msg in msgs
    ]
