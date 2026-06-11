import glob as g
from pathlib import Path

from langchain_core.tools import tool

_WORKDIR = Path.cwd().resolve()


def _safe_path(p: str) -> Path:
    path = (_WORKDIR / p).resolve()
    if not path.is_relative_to(_WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


@tool(description="Find files matching a glob pattern within the workspace.")
def glob(pattern: str, path: str | None = None) -> str:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g. "**/*.py", "src/*.ts")
        path: Optional subdirectory to search in (relative to workspace root)
    """
    try:
        base = _safe_path(path) if path else _WORKDIR
        results = []
        for match in g.glob(pattern, root_dir=base, recursive=True):
            full = (base / match).resolve()
            if full.is_relative_to(_WORKDIR):
                # Return path relative to workspace root for consistency
                try:
                    rel = full.relative_to(_WORKDIR)
                    results.append(str(rel))
                except ValueError:
                    results.append(str(full))
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"
