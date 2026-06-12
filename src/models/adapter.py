"""模型适配器 —— 根据运行时配置自动创建对应的 LLM 实例"""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from src.config import RuntimeConfig, load_runtime_config

# 映射表：provider -> 构造函数
_PROVIDER_MAP = {
    "anthropic": ChatAnthropic,
    "openai": ChatOpenAI,
}


def create_llm(runtime_config: RuntimeConfig | None = None):
    """根据运行时配置创建 LLM 实例。

    Args:
        runtime_config: 可选的运行时配置对象。若未提供，则调用
            load_runtime_config() 重新读取配置，支持热更新。
    """
    cfg = runtime_config if runtime_config is not None else load_runtime_config()

    cls = _PROVIDER_MAP.get(cfg.provider)
    if cls is None:
        raise ValueError(
            f"不支持的模型 provider: {cfg.provider}。"
            f"支持的选项: {list(_PROVIDER_MAP.keys())}"
        )

    kwargs = {
        "model": cfg.model,
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
    }

    # Anthropic 用 base_url / api_key
    if cfg.provider == "anthropic":
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
    # OpenAI 用 base_url / api_key
    elif cfg.provider == "openai":
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key

    return cls(**kwargs)
