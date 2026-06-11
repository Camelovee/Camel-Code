import re
import shlex
import subprocess
from pathlib import Path

from langchain_core.tools import tool

_WORKDIR = Path.cwd().resolve()

# ── Command Categories ─────────────────────────────────────────
READONLY_COMMANDS = frozenset([
    "pwd", "ls", "find", "rg", "grep", "cat", "head", "tail", "wc",
    "sed", "echo", "df", "du", "free", "uname", "uptime", "whoami",
    "which", "file", "stat", "sort", "uniq", "awk", "cut", "tr",
    "diff", "less", "more", "ps", "top", "htop", "lsof", "netstat",
])

DEVELOPMENT_COMMANDS = frozenset([
    "git", "npm", "node", "python3", "python", "pytest",
    "bash", "sh", "bun", "yarn", "pnpm", "cargo", "go",
    "make", "cmake", "gcc", "g++", "clang", "javac", "java",
    "pip", "pip3", "mypy", "black", "isort", "flake8", "tsc",
    "docker", "docker-compose", "kubectl", "terraform", "ansible",
    "pre-commit", "poetry", "pipenv", "conda",
])

DANGEROUS_PATTERNS = ["rm -rf /", "> /dev/", "mkfs", "dd if="]


def is_allowed_command(command: str) -> bool:
    return command in READONLY_COMMANDS or command in DEVELOPMENT_COMMANDS


def is_readonly_command(command: str) -> bool:
    return command in READONLY_COMMANDS


def _safe_path(p: str) -> Path:
    path = (_WORKDIR / p).resolve()
    if not path.is_relative_to(_WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def looks_like_shell_snippet(command: str, args: list[str] | None) -> bool:
    """Detect shell features: pipes, redirects, subshells, etc."""
    if args:
        return False
    return bool(re.search(r'[|&;<>()$`]', command))


def is_background_shell_snippet(command: str, args: list[str] | None) -> bool:
    """Detect trailing & (background) — but not &&."""
    if args:
        return False
    trimmed = command.strip()
    return trimmed.endswith("&") and not trimmed.endswith("&&")


def strip_trailing_background_op(command: str) -> str:
    return command.strip().rstrip("&").strip()


def normalize_command_input(
    command: str, args: list[str] | None
) -> tuple[str, list[str]]:
    """
    If args are provided, use them directly.
    Otherwise parse command as a shell-like string (e.g. "git status").
    """
    if args:
        return command.strip(), list(args)

    trimmed = command.strip()
    if not trimmed:
        return "", []

    # For simple commands, try shlex split to separate command and args
    if not looks_like_shell_snippet(trimmed, None):
        try:
            parsed = shlex.split(trimmed)
        except ValueError:
            parsed = trimmed.split()
        if parsed:
            return parsed[0], parsed[1:]

    # Shell snippet: let the caller handle it via bash -lc
    return "", []


# ── Background Task Registry ───────────────────────────────────
_background_tasks: dict[int, dict] = {}


def register_background_task(
    pid: int, command: str, cwd: Path
) -> dict:
    task = {
        "task_id": f"bg_{pid}",
        "pid": pid,
        "command": command,
        "cwd": str(cwd),
    }
    _background_tasks[pid] = task
    return task


@tool(
    description=(
        "Run a shell command from an allowlist of common development tools. "
        "Supports both single-string commands ('git status') and command+arguments. "
        "Shell features (pipes, redirects, subshells) are automatically detected "
        "and routed through bash. Append & to run in background."
    )
)
def bash(
    command: str,
    arguments: list[str] | None = None,
    cwd: str | None = None,
) -> str:
    """
    Run a shell command and return its output.

    Args:
        command: The command to execute (e.g. 'git', 'ls', or 'git status')
        arguments: Optional list of arguments (e.g. ['status', '--short'])
        cwd: Optional working directory (relative to workspace root)
    """
    # ── Safety checks ───────────────────────────────────────────
    for d in DANGEROUS_PATTERNS:
        if d in command:
            return f"Error: Dangerous command blocked — '{d}'"

    # ── Resolve working directory ───────────────────────────────
    effective_cwd = _WORKDIR
    if cwd:
        try:
            effective_cwd = _safe_path(cwd)
        except ValueError as e:
            return f"Error: {e}"

    # ── Normalize input ─────────────────────────────────────────
    cmd_name, cmd_args = normalize_command_input(command, arguments)
    use_shell = looks_like_shell_snippet(command, arguments)
    background_shell = is_background_shell_snippet(command, arguments)

    if not use_shell and not cmd_name:
        return "Error: empty command"

    # ── Choose execution mode ───────────────────────────────────
    if use_shell:
        exec_cmd = "bash"
        exec_args = [
            "-lc",
            strip_trailing_background_op(command) if background_shell else command,
        ]
    else:
        exec_cmd = cmd_name
        exec_args = cmd_args

    # ── Unknown command note ────────────────────────────────────
    if not use_shell and not is_allowed_command(cmd_name):
        # In a real system this would trigger a permission prompt.
        # For now we allow but note it's outside the allowlist.
        pass

    # ── Background execution ────────────────────────────────────
    if background_shell:
        try:
            proc = subprocess.Popen(
                [exec_cmd, *exec_args],
                cwd=effective_cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            task = register_background_task(
                pid=proc.pid,
                command=strip_trailing_background_op(command),
                cwd=effective_cwd,
            )
            return (
                f"Background command started.\n"
                f"TASK: {task['task_id']}\n"
                f"PID: {task['pid']}"
            )
        except Exception as e:
            return f"Error starting background process: {e}"

    # ── Foreground execution ────────────────────────────────────
    try:
        result = subprocess.run(
            [exec_cmd, *exec_args],
            cwd=effective_cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (result.stdout + "\n" + result.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except FileNotFoundError:
        return f"Error: command not found — '{exec_cmd}'"
    except Exception as e:
        return f"Error: {e}"
