"""测试 ask_user 工具返回值。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.graph import AgentState, build_graph
from src.compact import CompactPipelineState
from src.tools.ask_user import ask_user
from src.tools import bash


def test_ask_user_returns_await_flag():
    """ask_user 必须返回 await_user=True 和问题元数据。"""
    raw = ask_user.invoke({"question": "Which color?", "options": ["red", "blue"]})
    result = json.loads(raw)

    assert result["ok"] is True
    assert result["await_user"] is True
    assert result["output"] == "Which color?"
    assert result["meta"]["options"] == ["red", "blue"]
    assert result["meta"]["allow_multiple"] is False
    assert result["meta"]["allow_cancel"] is True


def test_ask_user_text_question():
    """无选项时 options 为 None。"""
    raw = ask_user.invoke({"question": "What is your name?"})
    result = json.loads(raw)

    assert result["await_user"] is True
    assert result["meta"]["options"] is None


def test_ask_user_all_flags():
    """测试所有布尔标志位可正确传递。"""
    raw = ask_user.invoke({"question": "X", "allow_multiple": True, "allow_cancel": False})
    result = json.loads(raw)
    assert result["meta"]["allow_multiple"] is True
    assert result["meta"]["allow_cancel"] is False


def test_ask_user_empty_options():
    """options 为空列表时应保留为空列表，不与 None 混淆。"""
    raw = ask_user.invoke({"question": "X", "options": []})
    result = json.loads(raw)
    assert result["meta"]["options"] == []


def test_tool_node_ends_turn_on_ask_user():
    """tool_node 检测到 ask_user 后应追加 assistant message 并设置 awaiting_user_input。"""
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "ask_user",
                "args": {"question": "Which color?", "options": ["red", "blue"]},
                "id": "call_1",
            }],
        ),
    ]
    state: AgentState = {
        "messages": messages,
        "model_messages": list(messages),
        "step": 0,
        "compact_state": CompactPipelineState(),
        "model_name": "gpt-4",
        "awaiting_user_input": False,
        "pending_question": None,
        "pending_question_meta": None,
    }

    mock_llm = MagicMock()
    # 让 LLM 返回带 tool_calls 的 AIMessage，触发 tool_node
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(
        content="",
        tool_calls=[{
            "name": "ask_user",
            "args": {"question": "Which color?", "options": ["red", "blue"]},
            "id": "call_1",
        }],
    )

    graph = build_graph(mock_llm, {"ask_user": ask_user}, max_steps=10)
    result = graph.invoke(state, config={"recursion_limit": 40})

    assert result["awaiting_user_input"] is True
    assert result["pending_question"] == "Which color?"
    assert result["pending_question_meta"]["options"] == ["red", "blue"]
    # AIMessage 在 ToolMessage 之前（先追加 question，后追加 tool result）
    assert isinstance(result["messages"][-2], AIMessage)
    assert result["messages"][-2].content == "Which color?"


def test_tool_node_does_not_await_for_non_ask_user_tools():
    """非 ask_user 工具不应设置 awaiting_user_input。"""
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
    state: AgentState = {
        "messages": messages,
        "model_messages": list(messages),
        "step": 0,
        "compact_state": CompactPipelineState(),
        "model_name": "gpt-4",
        "awaiting_user_input": False,
        "pending_question": None,
        "pending_question_meta": None,
    }

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="")

    graph = build_graph(mock_llm, {"bash": bash}, max_steps=10)
    result = graph.invoke(state, config={"recursion_limit": 40})

    assert result["awaiting_user_input"] is False
    assert result["pending_question"] is None


def test_tool_node_handles_mixed_tool_calls():
    """同时调用 ask_user 和其他工具时，状态设置正确且消息顺序正确。"""
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "ask_user",
                    "args": {"question": "Which color?", "options": ["red", "blue"]},
                    "id": "call_1",
                },
                {
                    "name": "bash",
                    "args": {"command": "echo hi"},
                    "id": "call_2",
                },
            ],
        ),
    ]
    state: AgentState = {
        "messages": messages,
        "model_messages": list(messages),
        "step": 0,
        "compact_state": CompactPipelineState(),
        "model_name": "gpt-4",
        "awaiting_user_input": False,
        "pending_question": None,
        "pending_question_meta": None,
    }

    mock_llm = MagicMock()
    # 让 LLM 返回带 tool_calls 的 AIMessage，触发 tool_node
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ask_user",
                "args": {"question": "Which color?", "options": ["red", "blue"]},
                "id": "call_1",
            },
            {
                "name": "bash",
                "args": {"command": "echo hi"},
                "id": "call_2",
            },
        ],
    )

    graph = build_graph(mock_llm, {"ask_user": ask_user, "bash": bash}, max_steps=10)
    result = graph.invoke(state, config={"recursion_limit": 40})

    assert result["awaiting_user_input"] is True
    assert result["pending_question"] == "Which color?"
    # 消息顺序：原始消息 + ask_user 的 AIMessage + ask_user 的 ToolMessage + bash 的 ToolMessage
    assert isinstance(result["messages"][-3], AIMessage)
    assert result["messages"][-3].content == "Which color?"
    assert isinstance(result["messages"][-2], ToolMessage)
    assert isinstance(result["messages"][-1], ToolMessage)


def test_tool_node_ignores_ask_user_without_await_flag():
    """ask_user 返回的 JSON 缺少 await_user 字段时不应暂停。"""
    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "ask_user",
                "args": {"question": "Which color?"},
                "id": "call_1",
            }],
        ),
    ]
    state: AgentState = {
        "messages": messages,
        "model_messages": list(messages),
        "step": 0,
        "compact_state": CompactPipelineState(),
        "model_name": "gpt-4",
        "awaiting_user_input": False,
        "pending_question": None,
        "pending_question_meta": None,
    }

    # mock ask_user 返回不含 await_user 的 JSON
    mock_ask_user = MagicMock()
    mock_ask_user.invoke.return_value = '{"ok": true, "output": "Which color?", "meta": {}}'

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.return_value = AIMessage(content="")

    graph = build_graph(mock_llm, {"ask_user": mock_ask_user}, max_steps=10)
    result = graph.invoke(state, config={"recursion_limit": 40})

    assert result["awaiting_user_input"] is False
    assert result["pending_question"] is None
