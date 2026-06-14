"""测试 grep 工具的基本行为。"""
from __future__ import annotations

from src.agents.lead_agent import LeadAgent
from src.tools.grep_tool import grep


def test_grep_name_and_schema():
    """grep 工具必须正确注册名称和参数 schema。"""
    assert grep.name == "grep"
    schema = grep.args_schema.model_json_schema()
    assert schema["required"] == ["pattern"]
    assert "path" in schema["properties"]
    assert "include" in schema["properties"]


def test_grep_finds_pattern_in_workspace():
    """grep 应能在工作区内找到已知模式。"""
    result = grep.invoke({"pattern": "def build_graph", "include": "*.py"})
    assert "def build_graph(" in result
    assert "match(es)" in result


def test_grep_no_matches():
    """无匹配时应返回提示。"""
    result = grep.invoke({"pattern": "xyz_nonexistent_12345", "path": "src"})
    assert result == "(no matches)"


def test_grep_path_escape_is_blocked():
    """路径逃逸工作区时应被拦截。"""
    result = grep.invoke({"pattern": "foo", "path": "../.."})
    assert result.startswith("Error: Path escapes workspace")


def test_grep_registered_in_lead_agent():
    """LeadAgent 必须包含 grep 工具。"""
    agent = LeadAgent()
    assert "grep" in agent.tools
    assert agent.tools["grep"] is grep
