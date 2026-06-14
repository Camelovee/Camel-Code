"""Skill 加载与发现核心逻辑。

参考 MiniCode src/skills.ts 的 loadSkill / discoverSkills 实现，
支持从项目级与用户级 .claude/skills 目录加载 SKILL.md。

SKILL.md 格式：
    ---
    name: skill-name
    description: 一句话描述
    ---

    后续为详细说明的 Markdown 内容。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .schema import LoadedSkill, SkillMetaData, SkillSummary


class SkillNotFoundError(Exception):
    """未找到指定 skill 时抛出。"""


class SkillFormatError(Exception):
    """SKILL.md 格式错误时抛出。"""


def _split_frontmatter(content: str) -> tuple[str | None, str]:
    """分离 YAML frontmatter 与 Markdown 正文。

    Returns:
        (frontmatter_text, markdown_body)。无 frontmatter 时 frontmatter_text 为 None。
    """
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None, normalized.strip("\n")

    end_index = normalized.find("\n---\n", 4)
    if end_index == -1:
        return None, normalized.strip("\n")

    frontmatter = normalized[4:end_index]
    body = normalized[end_index + 5 :]
    return frontmatter, body.strip("\n")


def _extract_meta_data(content: str, fallback_name: str = "") -> tuple[SkillMetaData, str]:
    """解析 SKILL.md 的 YAML frontmatter。

    Args:
        content: SKILL.md 完整内容。
        fallback_name: frontmatter 缺少 name 时的默认值。

    Returns:
        (metadata, markdown_body)。metadata 至少包含 name 与 description。
    """
    frontmatter_text, body = _split_frontmatter(content)

    if frontmatter_text is None:
        meta: SkillMetaData = {
            "name": fallback_name,
            "description": "No description provided.",
        }
    else:
        try:
            parsed = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise SkillFormatError(f"Invalid YAML frontmatter: {e}") from e

        if not isinstance(parsed, dict):
            raise SkillFormatError("YAML frontmatter must be a mapping")

        meta = SkillMetaData(
            name=parsed.get("name", fallback_name) or fallback_name,
            description=parsed.get("description", "No description provided.")
            or "No description provided.",
        )

    return meta, body


def get_skill_roots(cwd: Path) -> list[tuple[Path, str]]:
    """
    返回 skill 搜索根目录及来源标签。
    优先级 项目 > 全局
    """
    return [
        (cwd / ".claude" / "skills", "project"),
        (Path.home() / ".claude" / "skills", "user"),
    ]


def load_skill_from_root(name: str, root: Path) -> str | None:
    """尝试从单个根目录加载 SKILL.md 内容。"""
    skill_path = root / name / "SKILL.md"
    if skill_path.is_file():
        return skill_path.read_text(encoding="utf-8")
    return None


def load_skill_content(name: str, cwd: Path | None = None) -> LoadedSkill | None:
    """按名称加载 skill 内容。

    Args:
        name: Skill 目录名（大小写敏感）。
        cwd: 可选工作目录，默认当前工作目录。

    Returns:
        LoadedSkill 对象，未找到时返回 None。
    """
    normalized_name = name.strip()
    if not normalized_name:
        return None

    cwd = Path.cwd().resolve() if cwd is None else cwd.resolve()
    for root, source in get_skill_roots(cwd):
        raw_content = load_skill_from_root(normalized_name, root)
        if raw_content is None:
            continue

        meta, body = _extract_meta_data(raw_content, fallback_name=normalized_name)
        skill_path = root / normalized_name / "SKILL.md"
        return LoadedSkill(
            name=meta["name"],
            description=meta["description"],
            path=str(skill_path),
            source=source,  
            content=body,
        )

    return None


def discover_skills(cwd: Path | None = None) -> list[SkillSummary]:
    """发现所有可用的 skill，返回摘要列表（供后续扩展使用）。"""
    cwd = Path.cwd().resolve() if cwd is None else cwd.resolve()
    seen = set()
    results: list[SkillSummary] = []

    for root, source in get_skill_roots(cwd):
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.is_file() or entry.name in seen:
                continue
            seen.add(entry.name)
            raw_content = skill_file.read_text(encoding="utf-8")
            meta, _ = _extract_meta_data(raw_content, fallback_name=entry.name)
            results.append(
                SkillSummary(
                    name=meta["name"],
                    description=meta["description"],
                    path=str(skill_file),
                    source=source,  # type: ignore[typeddict-item]
                )
            )

    return results
