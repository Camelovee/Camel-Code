from typing import Literal, TypedDict


class SkillMetaData(TypedDict):
    """SKILL.md YAML frontmatter 中的元数据。"""

    name: str
    description: str


class SkillSummary(TypedDict):
    """Skill 摘要信息，用于发现列表。"""

    name: str
    description: str
    path: str
    source: Literal["project", "user"]


class LoadedSkill(SkillSummary):
    """加载后的 skill，在摘要基础上增加 Markdown 正文。"""

    content: str
