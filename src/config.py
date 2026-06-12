"""CamelCode 运行时配置。

配置优先级（后者覆盖前者）：
    ~/.camel-code/settings.json
    < 进程环境变量（含 .env）

settings.json 中可以直接使用环境变量名作为键，例如：
    {
      "model": "deepseek-v4-flash",
      "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
      "ANTHROPIC_AUTH_TOKEN": "sk-xxx"
    }

也支持少量别名：
    model -> ANTHROPIC_MODEL
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录 .env，确保环境变量在配置解析前生效
load_dotenv()


# ── 路径常量 ───────────────────────────────────────────────
HOME_DIR = Path.home()
CAMEL_CODE_DIR = Path(os.getenv("CAMEL_CODE_HOME", HOME_DIR / ".camel-code"))
CAMEL_CODE_SETTINGS_PATH = CAMEL_CODE_DIR / "settings.json"


# ── 默认配置 ───────────────────────────────────────────────
# 键名为环境变量名，settings.json 中可直接使用这些键名
_DEFAULTS: dict[str, str] = {
    "ANTHROPIC_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_AUTH_TOKEN": "",
    "MODEL_PROVIDER": "anthropic",
    "MODEL_MAX_TOKENS": "8000",
    "MODEL_TEMPERATURE": "0.1",
}

# settings.json 中支持的友好别名
_ALIASES: dict[str, str] = {
    "model": "ANTHROPIC_MODEL",
}

_CONFIG_KEYS = tuple(_DEFAULTS.keys())


# ── 数据类型 ───────────────────────────────────────────────
@dataclass
class RuntimeConfig:
    """运行时配置对象。"""

    provider: str
    model: str
    base_url: str
    api_key: str
    max_tokens: int
    temperature: float
    source_summary: str


# ── 内部辅助函数 ───────────────────────────────────────────
def _read_settings_file(path: Path) -> dict:
    """读取 settings.json 文件；不存在则返回空配置。"""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件格式错误: {path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"配置文件顶层必须是对象: {path}")

    return parsed


def _lookup(settings: dict, key: str) -> str | None:
    """从 settings 对象中查找配置键。

    查找顺序：顶层直接键名 > 顶层别名 > env 字段中的键名。
    """
    # 1. 顶层直接键名
    if key in settings:
        return str(settings[key])

    # 2. 顶层别名
    for alias, target in _ALIASES.items():
        if target == key and alias in settings:
            return str(settings[alias])

    # 3. env 字段中的键名
    env = settings.get("env")
    if isinstance(env, dict) and key in env:
        return str(env[key])

    return None


# ── 公开接口 ───────────────────────────────────────────────
def load_runtime_config() -> RuntimeConfig:
    """加载运行时配置，应用优先级规则。

    每次调用都会重新读取 ~/.camel-code/settings.json，因此修改配置文件后
    无需重启进程即可生效。
    """
    settings = _read_settings_file(CAMEL_CODE_SETTINGS_PATH)

    values: dict[str, str] = {}
    source_parts: list[str] = []

    for key in _CONFIG_KEYS:
        # 1. 真实进程环境变量优先级最高
        if key in os.environ:
            values[key] = os.environ[key]
            source_parts.append(f"{key}=env")
            continue

        # 2. ~/.camel-code/settings.json
        setting_value = _lookup(settings, key)
        if setting_value is not None:
            values[key] = setting_value
            source_parts.append(f"{key}=settings")
            continue

        # 3. 默认值
        values[key] = _DEFAULTS[key]
        source_parts.append(f"{key}=default")

    source_summary = "; ".join(source_parts)

    try:
        max_tokens = int(values["MODEL_MAX_TOKENS"])
    except ValueError as exc:
        raise ValueError(
            f"MODEL_MAX_TOKENS 必须是整数，当前值: {values['MODEL_MAX_TOKENS']!r}"
        ) from exc

    try:
        temperature = float(values["MODEL_TEMPERATURE"])
    except ValueError as exc:
        raise ValueError(
            f"MODEL_TEMPERATURE 必须是数字，当前值: {values['MODEL_TEMPERATURE']!r}"
        ) from exc

    return RuntimeConfig(
        provider=values["MODEL_PROVIDER"].lower(),
        model=values["ANTHROPIC_MODEL"],
        base_url=values["ANTHROPIC_BASE_URL"],
        api_key=values["ANTHROPIC_AUTH_TOKEN"],
        max_tokens=max_tokens,
        temperature=temperature,
        source_summary=source_summary,
    )
