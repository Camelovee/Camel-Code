"""grep tool —— 在工作区内搜索文件内容。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from langchain_core.tools import tool

_WORKDIR = Path.cwd().resolve()

# ── 限制常量 ──────────────────────────────────────────────────
_MAX_LINES = 100
_MAX_OUTPUT = 50_000
_TIMEOUT = 30


def _safe_path(p: str | None) -> Path:
    """解析相对工作区的安全路径。"""
    if not p:
        return _WORKDIR
    path = (_WORKDIR / p).resolve()
    if not path.is_relative_to(_WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


@tool(
    description=(
        "Search UTF-8 text files under the workspace using a regex pattern. "
        "Results are returned as path:line:content."
    )
)
def grep(
    pattern: str,
    path: str | None = None,
    include: str | None = None,
) -> str:
    """在工作区内搜索文件内容。

    Args:
        pattern: 正则表达式字符串。
        path: 相对工作区的子目录（可选，默认工作区根目录）。
        include: glob 过滤，例如 "*.py"（可选）。

    Returns:
        path:line:content 格式的匹配结果，末尾附摘要。
    """
    if not isinstance(pattern, str) or not pattern:
        return "Error: pattern is required"

    try:
        target = _safe_path(path)
    except ValueError as e:
        return f"Error: {e}"

    if not target.exists():
        return f"Error: directory not found: {path or '.'}"
    if not target.is_dir():
        return f"Error: not a directory: {path or '.'}"

    cmd = ["grep", "-rnH", "-I", "--color=never"]
    if include:
        cmd.extend(["--include", include])
    cmd.extend(["--", pattern, str(target)])

    try:
        result = subprocess.run(
            cmd,
            cwd=_WORKDIR,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError:
        return "Error: grep not found"
    except subprocess.TimeoutExpired:
        return "Error: grep timeout"

    lines = result.stdout.splitlines()
    if result.returncode != 0 and not lines:
        return "(no matches)"

    truncated = False
    if len(lines) > _MAX_LINES:
        lines = lines[:_MAX_LINES]
        truncated = True

    output = "\n".join(lines)
    if len(output) > _MAX_OUTPUT:
        output = output[:_MAX_OUTPUT] + "\n... (truncated)"
        truncated = True

    if truncated:
        output += "\n... (truncated)"

    output += f"\n\n{len(lines)} match(es)"
    return output
