"""测试 LeadAgent 高层事件订阅接口。"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.lead_agent import LeadAgent


def test_agent_emits_tool_start_event():
    """on_tool_start 注册的 handler 应在工具开始前被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_tool_start(handler)

    agent.hookManager.call("before_tool", state={}, name="bash", args={"command": "ls"})

    handler.assert_called_once_with("bash", {"command": "ls"})


def test_agent_emits_tool_result_event():
    """on_tool_result 注册的 handler 应在工具结束后被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_tool_result(handler)

    agent.hookManager.call(
        "after_tool", state={}, name="bash", output="hello", is_error=False
    )

    handler.assert_called_once_with("bash", "hello", False)


def test_agent_emits_assistant_message():
    """on_assistant_message 注册的 handler 应在 LLM 返回文本时被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_assistant_message(handler)

    response = MagicMock()
    response.content = "hello"
    agent.hookManager.call("after_llm", state={}, response=response)

    handler.assert_called_once_with("hello")


def test_agent_emits_progress_message():
    """on_progress_message 注册的 handler 应在 LLM 返回 thinking 块时被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_progress_message(handler)

    response = MagicMock()
    response.content = [{"type": "thinking", "thinking": "thinking..."}]
    agent.hookManager.call("after_llm", state={}, response=response)

    handler.assert_called_once_with("thinking...")


def test_agent_emits_context_stats():
    """on_context_stats 注册的 handler 应在压缩后被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_context_stats(handler)

    result = MagicMock()
    result.snip_result = None
    result.collapse_result = None
    result.auto_compact_result = None
    stats = {"total_tokens": 100}
    agent.hookManager.call("after_compress", state={}, result=result, stats=stats)

    handler.assert_called_once_with(stats)


def test_agent_emits_compression_event():
    """on_compression 注册的 handler 应在压缩事件触发时被调用。"""
    agent = LeadAgent()
    handler = MagicMock()
    agent.on_compression(handler)

    result = MagicMock()
    result.snip_result = MagicMock()
    result.snip_result.did_snip = True
    result.snip_result.tokens_freed = 50
    result.collapse_result = None
    result.auto_compact_result = None
    result.stats_before = {}
    result.stats_after = {}
    agent.hookManager.call("after_compress", state={}, result=result, stats={})

    handler.assert_called_once_with("snip", {"tokens_freed": 50})
