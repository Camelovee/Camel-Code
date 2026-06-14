"""测试系统 prompt 构建。"""
from __future__ import annotations

from pathlib import Path

from src.prompts import get_system_prompt


def _make_skill_md(name: str, description: str, body: str = "") -> str:
    """构造带 YAML frontmatter 的 SKILL.md 内容。"""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def test_system_prompt_includes_skills(tmp_path, monkeypatch):
    """系统 prompt 应包含发现的 skills 列表。"""
    skill_dir = tmp_path / ".claude" / "skills" / "planning"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        _make_skill_md("planning", "Plan before coding."),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    prompt = get_system_prompt(str(tmp_path))

    assert "You are camel-code" in prompt
    assert "Available skills:" in prompt
    assert "- planning: Plan before coding." in prompt
    assert "call load_skill before following it" in prompt


def test_system_prompt_no_skills(tmp_path, monkeypatch):
    """无 skills 时系统 prompt 应显示 none discovered。"""
    monkeypatch.chdir(tmp_path)
    prompt = get_system_prompt(str(tmp_path))

    assert "Available skills:\n- none discovered" in prompt


def test_system_prompt_uses_cwd(tmp_path, monkeypatch):
    """系统 prompt 应包含当前工作目录。"""
    monkeypatch.chdir(tmp_path)
    prompt = get_system_prompt(str(tmp_path))

    assert f"Current cwd: {tmp_path}" in prompt
