"""测试 load_skill 工具的基本行为。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.graph import AgentState, build_graph
from src.agents.lead_agent import LeadAgent
from src.compact import CompactPipelineState
from src.hook import HookManager
from src.skill.skill import _extract_meta_data, load_skill_content
from src.tools import load_skill
from src.tools.load_skill import load_skill as load_skill_tool


def _make_skill_md(name: str, description: str, body: str) -> str:
    """构造带 YAML frontmatter 的 SKILL.md 内容。"""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def test_extract_meta_data_parses_yaml_frontmatter():
    """_extract_meta_data 应正确解析 YAML frontmatter。"""
    content = _make_skill_md("planning", "Plan before coding.", "# Details\n\nMore info.")
    meta, body = _extract_meta_data(content, fallback_name="fallback")
    assert meta["name"] == "planning"
    assert meta["description"] == "Plan before coding."
    assert "# Details" in body


def test_extract_meta_data_uses_fallback_when_no_frontmatter():
    """无 frontmatter 时应使用 fallback 值。"""
    meta, body = _extract_meta_data("# Title\n\nBody", fallback_name="fallback")
    assert meta["name"] == "fallback"
    assert meta["description"] == "No description provided."
    assert "# Title" in body


def test_extract_meta_data_empty_description_fallback():
    """frontmatter 缺少 description 时应提供默认值。"""
    content = "---\nname: demo\n---\n\nBody"
    meta, _ = _extract_meta_data(content, fallback_name="demo")
    assert meta["description"] == "No description provided."


def test_load_skill_content_returns_loaded_skill(tmp_path, monkeypatch):
    """load_skill_content 应返回 LoadedSkill 对象。"""
    skill_dir = tmp_path / ".claude" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        _make_skill_md("demo", "A demo skill.", "# Demo\n\nDetailed content."),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    skill = load_skill_content("demo")
    assert skill is not None
    assert skill["name"] == "demo"
    assert skill["description"] == "A demo skill."
    assert skill["source"] == "project"
    assert skill["path"] == str(skill_dir / "SKILL.md")
    assert "Detailed content." in skill["content"]


def test_load_skill_content_not_found(tmp_path, monkeypatch):
    """skill 不存在时应返回 None。"""
    monkeypatch.chdir(tmp_path)
    assert load_skill_content("missing") is None


def test_load_skill_content_empty_name():
    """空名称应返回 None。"""
    assert load_skill_content("  ") is None


def test_load_skill_tool_invokes_successfully(tmp_path, monkeypatch):
    """load_skill 工具应返回包含 skill 元数据与内容的字符串。"""
    skill_dir = tmp_path / ".claude" / "skills" / "planning"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        _make_skill_md("planning", "Plan before coding.", "# Planning\n\nSteps."),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    result = load_skill_tool.invoke({"name": "planning"})
    assert "Plan before coding." in result
    assert "Source: project" in result
    assert "Steps." in result


def test_load_skill_tool_not_found(tmp_path, monkeypatch):
    """skill 不存在时工具应返回错误信息。"""
    monkeypatch.chdir(tmp_path)
    result = load_skill_tool.invoke({"name": "missing"})
    assert result.startswith("Error: skill 'missing' not found")


def test_load_skill_exported_from_tools():
    """load_skill 必须从 src.tools 包导出。"""
    assert load_skill.name == "load_skill"


def test_load_skill_registered_in_lead_agent():
    """LeadAgent 工具注册表必须包含 load_skill。"""
    agent = LeadAgent()
    assert "load_skill" in agent.tools
    assert agent.tools["load_skill"] is load_skill


def test_load_skill_in_graph_tool_node(tmp_path, monkeypatch):
    """load_skill 应能在 LangGraph 的 tool_node 中被调用并触发回调。"""
    skill_dir = tmp_path / ".claude" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        _make_skill_md("demo", "Demo skill.", "# Demo\n\nDemo skill content."),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    messages = [
        SystemMessage(content="system"),
        HumanMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "load_skill",
                "args": {"name": "demo"},
                "id": "call_1",
            }],
        ),
    ]
    state = AgentState(
        messages=messages,
        model_messages=list(messages),
        step=0,
        compact_state=CompactPipelineState(),
        model_name="gpt-4",
        awaiting_user_input=False,
        pending_question=None,
        pending_question_meta=None,
    )

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "load_skill",
                "args": {"name": "demo"},
                "id": "call_1",
            }],
        ),
        AIMessage(content="done"),
    ]

    handler = MagicMock()
    hook_manager = HookManager()
    hook_manager.register("after_tool", handler)

    graph = build_graph(mock_llm, {"load_skill": load_skill}, max_steps=10, hookManager=hook_manager)
    graph.invoke(state, config={"recursion_limit": 40})

    handler.assert_called_once()
    args = handler.call_args.kwargs
    assert args["name"] == "load_skill"
    assert "Demo skill content." in args["output"]
    assert args["is_error"] is False
