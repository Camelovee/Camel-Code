"""模型上下文窗口配置。

将模型名称映射到 (context_window, effective_input) 对，
便于集中维护而无需修改多处 if/elif 分支。
"""
from __future__ import annotations

from dataclasses import dataclass


# ── 默认值 ──────────────────────────────────────────────────────
DEFAULT_CONTEXT_WINDOW = 200_000    # 模型总上下文窗口（含输入+输出）
DEFAULT_EFFECTIVE_INPUT = 180_000   # 实际可用输入长度（预留输出空间）


# ── 配置条目 ────────────────────────────────────────────────────
@dataclass(frozen=True)
class ModelContextConfig:
    """单个模型的上下文窗口配置。"""

    name: str           # 模型配置名称（仅用于说明）
    context_window: int # 总上下文窗口大小
    effective_input: int    # 实际可用输入长度
    patterns: list[str]     # 模型名（小写）需要全部匹配的子串列表


# ── 模型注册表 ──────────────────────────────────────────────────
# 按优先级排列：越具体的匹配应放在越前面
MODEL_CONTEXT_REGISTRY: list[ModelContextConfig] = [
    # Claude 3 系列
    ModelContextConfig(
        name="claude-3-opus",
        context_window=200_000,
        effective_input=180_000,
        patterns=["claude-3-opus"],
    ),
    ModelContextConfig(
        name="claude-3-5-sonnet",
        context_window=200_000,
        effective_input=180_000,
        patterns=["claude-3-5-sonnet"],
    ),
    ModelContextConfig(
        name="claude-3-sonnet",
        context_window=200_000,
        effective_input=180_000,
        patterns=["claude-3-sonnet"],
    ),
    ModelContextConfig(
        name="claude-3-haiku",
        context_window=200_000,
        effective_input=180_000,
        patterns=["claude-3-haiku"],
    ),

    # GPT-4 系列（特定变体优先于普通 gpt-4）
    ModelContextConfig(
        name="gpt-4-32k",
        context_window=32_768,
        effective_input=28_000,
        patterns=["gpt-4", "32k"],
    ),
    ModelContextConfig(
        name="gpt-4-128k",
        context_window=128_000,
        effective_input=120_000,
        patterns=["gpt-4", "128k"],
    ),
    ModelContextConfig(
        name="gpt-4-turbo",
        context_window=128_000,
        effective_input=120_000,
        patterns=["gpt-4-turbo"],
    ),
    ModelContextConfig(
        name="gpt-4o",
        context_window=128_000,
        effective_input=120_000,
        patterns=["gpt-4o"],
    ),
    ModelContextConfig(
        name="gpt-4",
        context_window=8_192,
        effective_input=7_000,
        patterns=["gpt-4"],
    ),

    # GPT-3.5 系列
    ModelContextConfig(
        name="gpt-3.5",
        context_window=16_384,
        effective_input=14_000,
        patterns=["gpt-3.5"],
    ),
    ModelContextConfig(
        name="gpt-35",
        context_window=16_384,
        effective_input=14_000,
        patterns=["gpt-35"],
    ),

    # DeepSeek 系列
    ModelContextConfig(
        name="deepseek",
        context_window=128_000,
        effective_input=120_000,
        patterns=["deepseek"],
    ),
]


# ── 查询函数 ────────────────────────────────────────────────────
def get_model_context_window(model_name: str) -> tuple[int, int]:
    """返回已知模型的 (context_window, effective_input)。"""
    name = model_name.lower()
    for cfg in MODEL_CONTEXT_REGISTRY:
        if all(pattern in name for pattern in cfg.patterns):
            return cfg.context_window, cfg.effective_input
    return DEFAULT_CONTEXT_WINDOW, DEFAULT_EFFECTIVE_INPUT
