"""load_skill 工具封装。

对外暴露为 LangChain 工具，内部调用 src.skill.skill 核心逻辑。
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from src.skill.skill import load_skill_content


@tool(
    description=(
        "Load a skill by name from the project or user skills directory. "
        "Returns the skill metadata and full Markdown content, or a not-found message."
    )
)
def load_skill(name: str) -> str:
    """按名称加载 skill 元数据及 Markdown 内容。

    Args:
        name: Skill 目录名（大小写敏感）。

    Returns:
        skill 元数据、来源路径与 Markdown 正文，或未找到时的错误信息。
    """
    normalized_name = name.strip()
    if not normalized_name:
        return "Error: skill name cannot be empty"

    skill = load_skill_content(normalized_name, Path.cwd())
    if skill is None:
        return f"Error: skill '{normalized_name}' not found in project or user skills directory"

    return (
        f"# Skill: {skill['name']}\n"
        f"Source: {skill['source']}\n"
        f"Path: {skill['path']}\n"
        f"Description: {skill['description']}\n\n"
        f"{skill['content']}"
    )
