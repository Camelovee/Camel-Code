"""测试 Agent 运行期回调机制。"""
from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.callbacks import AgentCallbacks
from src.agents.graph import AgentState, _emit_compression, build_graph
from src.compact import CompactPipelineState
from src.tools import bash


def _make_state(messages: list) -> AgentState:
    """构造最小 AgentState。"""
    return {
        "messages": messages,
        "model_messages": list(messages),
        "step": 0,
        "compact_state": CompactPipelineState(),
        "model_name": "gpt-4",
        "awaiting_user_input": False,
        "pending_question": None,
        "pending_question_meta": None,
    }


def test_graph_triggers_tool_start_callback():
    """tool_node 执行前应触发 on_tool_start 回调。"""
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "bash",
                "args": {"command": "echo hi"},
                "id": "call_1",
            }],
        ),
    ]
    state = _make_state(messages)

    mock_llm = MagicMock()
    # 第一次返回带 tool_calls 进入 tool_node，第二次返回文本结束回合
    mock_llm.bind_tools.return_value.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "bash",
                "args": {"command": "echo hi"},
                "id": "call_1",
            }],
        ),
        AIMessage(content="done"),
    ]

    handler = MagicMock()
    callbacks = AgentCallbacks(on_tool_start=handler)

    graph = build_graph(mock_llm, {"bash": bash}, max_steps=10, callbacks=callbacks)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once_with("bash", {"command": "echo hi"})


def test_graph_triggers_tool_result_callback():
    """tool_node 执行后应触发 on_tool_result 回调。"""
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "bash",
                "args": {"command": "echo hi"},
                "id": "call_1",
            }],
        ),
    ]
    state = _make_state(messages)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "bash",
                "args": {"command": "echo hi"},
                "id": "call_1",
            }],
        ),
        AIMessage(content="done"),
    ]

    handler = MagicMock()
    callbacks = AgentCallbacks(on_tool_result=handler)

    graph = build_graph(mock_llm, {"bash": bash}, max_steps=10, callbacks=callbacks)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once()
    args = handler.call_args[0]
    assert args[0] == "bash"
    assert "hi" in args[1]
    assert args[2] is False


def test_graph_triggers_assistant_message_callback():
    """llm_node 返回文本内容时应触发 on_assistant_message 回调。"""
    messages = [SystemMessage(content="system"), HumanMessage(content="hi")]
    state = _make_state(messages)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="hello")

    handler = MagicMock()
    callbacks = AgentCallbacks(on_assistant_message=handler)

    graph = build_graph(mock_llm, {}, max_steps=10, callbacks=callbacks)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once_with("hello")


def test_graph_triggers_progress_message_callback():
    """llm_node 返回 thinking 块时应触发 on_progress_message 回调。"""
    messages = [SystemMessage(content="system"), HumanMessage(content="hi")]
    state = _make_state(messages)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(
        content=[{"type": "thinking", "thinking": "thinking..."}]
    )

    handler = MagicMock()
    callbacks = AgentCallbacks(on_progress_message=handler)

    graph = build_graph(mock_llm, {}, max_steps=10, callbacks=callbacks)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once_with("thinking...")


def test_graph_triggers_context_stats_callback():
    """compress_node 执行后应触发 on_context_stats 回调。"""
    messages = [SystemMessage(content="system"), HumanMessage(content="hi")]
    state = _make_state(messages)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="done")

    handler = MagicMock()
    callbacks = AgentCallbacks(on_context_stats=handler)

    graph = build_graph(mock_llm, {}, max_steps=10, callbacks=callbacks)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once()
    stats = handler.call_args[0][0]
    assert hasattr(stats, "total_tokens")


def test_emit_compression_distributes_events():
    """_emit_compression 应根据压缩结果分发 on_compression 回调。"""
    handler = MagicMock()
    callbacks = AgentCallbacks(on_compression=handler)

    result = MagicMock()
    result.snip_result = MagicMock()
    result.snip_result.did_snip = True
    result.snip_result.tokens_freed = 50
    result.collapse_result = None
    result.auto_compact_result = None
    result.stats_before = {}
    result.stats_after = {}

    _emit_compression(callbacks, result, {"total_tokens": 100})

    handler.assert_called_once_with("snip", {"tokens_freed": 50})


def test_lead_agent_run_accepts_callbacks():
    """LeadAgent.run_agent_turn 应接受 callbacks 参数并正确传递。"""
    from src.agents.lead_agent import LeadAgent

    agent = LeadAgent()
    handler = MagicMock()
    callbacks = AgentCallbacks(on_assistant_message=handler)

    # mock LLM，让它直接返回文本并结束回合
    agent.llm = MagicMock()
    agent.llm.bind_tools.return_value.invoke.return_value = AIMessage(content="hello")
    # 跳过 run_agent_turn 内部的配置热刷新，避免覆盖 mock LLM
    agent._refresh_llm = lambda: None

    messages = [SystemMessage(content="system"), HumanMessage(content="hi")]
    agent.run_agent_turn(messages, max_steps=5, callbacks=callbacks)

    handler.assert_called_once_with("hello")
    assert messages[-1].content == "hello"
