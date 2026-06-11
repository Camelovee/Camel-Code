"""四层压缩管道简单测试。

运行：pytest test/test_compact.py -v
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.compact.auto_compact import AutoCompactState, auto_compact
from src.compact.context_collapse import CollapseOptions, ContextCollapseState, apply_context_collapse
from src.compact.microcompact import CLEAR_MARKER, microcompact
from src.compact.pipeline import CompactPipelineState, run_compact_pipeline
from src.compact.snip_compact import snip_compact

MODEL_NAME = "gpt-4"  # effective_input = 7,000


# ── 辅助函数 ───────────────────────────────────────────────────
def _make_messages(count: int, content_len: int = 1500) -> list:
    """构造 count 轮对话，让利用率超过所有阈值。"""
    msgs = [SystemMessage(content="system prompt")]
    for _ in range(count):
        msgs.append(HumanMessage(content="x" * content_len))
        msgs.append(AIMessage(content="y" * content_len))
    return msgs


def _make_tool_messages(count: int, content_len: int = 1500) -> list:
    """构造包含 ToolMessage 的消息列表。"""
    msgs = [SystemMessage(content="system")]
    for i in range(count):
        msgs.append(HumanMessage(content="u" * content_len))
        msgs.append(ToolMessage(
            content="tool output " * 100,
            tool_call_id=f"id{i}",
            name="bash",
        ))
    return msgs


def _mock_llm(summary: str = "摘要") -> MagicMock:
    """返回一个总是生成固定摘要的 mock LLM。"""
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=f"<summary>{summary}</summary>")
    return mock


# ── Layer 1: Snip Compact ─────────────────────────────────────
class TestSnipCompact:
    def test_snips_when_utilization_high(self):
        """高利用率时裁剪中间区间。"""
        messages = _make_messages(10)  # ~9,300 tokens, util ~1.33
        result = snip_compact(messages, MODEL_NAME)
        print(result)
        assert result.did_snip is True
        assert result.tokens_freed > 0
        assert len(result.messages) < len(messages)

    def test_no_snip_when_utilization_low(self):
        """低利用率时不裁剪。"""
        messages = [SystemMessage(content="s"), HumanMessage(content="hi")]
        result = snip_compact(messages, MODEL_NAME)
        print(result)


# ── Layer 2: Microcompact ─────────────────────────────────────
class TestMicrocompact:
    def test_clears_old_tool_results(self):
        """清除旧工具结果，保留最近 3 个。"""
        messages = _make_tool_messages(6)  # util ~0.94 > 0.50
        result = microcompact(messages, MODEL_NAME)
        tools = [m for m in result if isinstance(m, ToolMessage)]
        assert len(tools) == 6
        assert tools[0].content == CLEAR_MARKER
        assert tools[1].content == CLEAR_MARKER
        assert tools[2].content == CLEAR_MARKER
        assert tools[3].content != CLEAR_MARKER
        assert tools[4].content != CLEAR_MARKER
        assert tools[5].content != CLEAR_MARKER

    def test_no_change_when_few_tools(self):
        """工具结果少时不修改。"""
        messages = _make_tool_messages(2)
        result = microcompact(messages, MODEL_NAME)
        assert result is messages


# ── Layer 3: Context Collapse ─────────────────────────────────
class TestContextCollapse:
    def test_collapses_with_mock_llm(self):
        """高利用率 + mock LLM 时触发折叠。"""
        messages = _make_messages(15)  # ~14,000 tokens, util ~2.0
        mock_model = _mock_llm("区间摘要")

        result = apply_context_collapse(
            messages, MODEL_NAME, mock_model,
            state=ContextCollapseState(),
            options=CollapseOptions(),
        )
        assert result.collapsed is True
        assert len(result.spans) > 0

    def test_no_collapse_when_low_utilization(self):
        """低利用率时不触发。"""
        messages = [SystemMessage(content="s"), HumanMessage(content="hi")]
        result = apply_context_collapse(
            messages, MODEL_NAME, _mock_llm(),
            state=ContextCollapseState(),
            options=CollapseOptions(utilization_threshold=0.99),
        )
        assert result.collapsed is False


# ── Layer 4: Auto Compact ─────────────────────────────────────
class TestAutoCompact:
    @patch("src.compact.auto_compact.MAX_KEEP_TOKENS", 5000)
    def test_compacts_when_critical(self):
        """极高利用率 + mock LLM 时触发全量摘要。"""
        messages = _make_messages(15)  # ~14,000 tokens
        mock_model = _mock_llm("全量摘要")

        result = auto_compact(messages, MODEL_NAME, mock_model, state=AutoCompactState())
        assert result is not None
        assert result.removed_count > 0
        assert result.summary_content

    def test_no_compact_when_normal(self):
        """正常利用率时不触发。"""
        messages = [SystemMessage(content="s"), HumanMessage(content="hi")]
        result = auto_compact(
            messages, MODEL_NAME, _mock_llm(), state=AutoCompactState(),
        )
        assert result is None


# ── Pipeline 集成 ─────────────────────────────────────────────
class TestPipeline:
    @patch("src.compact.auto_compact.MAX_KEEP_TOKENS", 5000)
    def test_runs_all_layers(self):
        """四层管道顺序执行，返回完整结果。"""
        messages = _make_messages(20)
        mock_model = _mock_llm("管道摘要")

        state = CompactPipelineState()
        result = run_compact_pipeline(
            messages=messages,
            model=mock_model,
            model_name=MODEL_NAME,
            step=0,
            state=state,
        )
        assert result is not None
        assert result.messages is not None
        assert result.model_messages is not None
        # 至少有一层触发了压缩
        assert result.snip_result is not None or result.collapse_result is not None
