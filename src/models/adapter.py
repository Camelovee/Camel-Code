"""模型适配器 —— 根据 .env 配置自动创建对应的 LLM 实例"""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from src.config import (
    MODEL_API_KEY,
    MODEL_BASE_URL,
    MODEL_ID,
    MODEL_MAX_TOKENS,
    MODEL_PROVIDER,
    MODEL_TEMPERATURE,
)

# 映射表：provider -> 构造函数
_PROVIDER_MAP = {
    "anthropic": ChatAnthropic,
    "openai": ChatOpenAI,
}


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
):
    """根据配置创建 LLM 实例。

    参数优先级：传入值 > .env 配置 > 默认值
    """
    provider = (provider or MODEL_PROVIDER).lower()
    model = model or MODEL_ID
    base_url = base_url or MODEL_BASE_URL
    api_key = api_key or MODEL_API_KEY
    max_tokens = max_tokens if max_tokens is not None else MODEL_MAX_TOKENS
    temperature = temperature if temperature is not None else MODEL_TEMPERATURE

    cls = _PROVIDER_MAP.get(provider)
    if cls is None:
        raise ValueError(
            f"不支持的模型 provider: {provider}。"
            f"支持的选项: {list(_PROVIDER_MAP.keys())}"
        )

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # Anthropic 用 base_url / api_key
    if provider == "anthropic":
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
    # OpenAI 用 base_url / api_key
    elif provider == "openai":
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key

    return cls(**kwargs)
