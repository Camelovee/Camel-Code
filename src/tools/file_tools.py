from pathlib import Path

from langchain_core.tools import tool

_WORKDIR = Path.cwd().resolve()


def _safe_path(p: str) -> Path:
    """Resolve path and ensure it stays within workspace."""
    path = (_WORKDIR / p).resolve()
    if not path.is_relative_to(_WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


@tool(description="Read a UTF-8 text file relative to the workspace root. Large files can be read in chunks via offset and limit.")
def read_file(path: str, limit: int | None = None, offset: int = 0) -> str:
    """
    Read a file and return its contents.

    Args:
        path: Relative path to the file
        limit: Max number of lines to read (None = all)
        offset: Line number to start from (0-based)
    """
    try:
        lines = _safe_path(path).read_text().splitlines()
        offset = max(int(offset or 0), 0)
        limit = int(limit) if limit is not None else None
        lines = lines[offset:]
        if limit is not None and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@tool(description="Write content to a file. Creates parent directories if needed.")
def write_file(path: str, content: str) -> str:
    """
    Write text content to a file. Overwrites if exists.

    Args:
        path: Relative path to the file
        content: Text content to write
    """
    try:
        fp = _safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


@tool(description="Replace exact text in a file once. old_text must match exactly.")
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """
    Replace exact text in a file. The old_text must exist exactly once.

    Args:
        path: Relative path to the file
        old_text: Exact text to find and replace
        new_text: Replacement text
    """
    try:
        fp = _safe_path(path)
        text = fp.read_text()
        if old_text not in text:
            return f"Error: text not found in {path}"
        if text.count(old_text) > 1:
            return f"Error: old_text appears {text.count(old_text)} times in {path} — must be unique"
        fp.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"
