"""src/config.py 运行时配置优先级测试。

运行：pytest test/test_config.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config
from src.config import CAMEL_CODE_SETTINGS_PATH, RuntimeConfig, load_runtime_config


# ── 辅助函数 ───────────────────────────────────────────────────
def _write_settings(path: Path, data: dict) -> None:
    """写入 settings.json 并确保父目录存在。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清除与本模块相关的环境变量，避免受宿主 shell 影响。"""
    for key in (
        "ANTHROPIC_MODEL",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "MODEL_PROVIDER",
        "MODEL_MAX_TOKENS",
        "MODEL_TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)


# ── load_runtime_config 测试 ───────────────────────────────────
def test_env_variable_highest_priority(tmp_path, monkeypatch):
    """环境变量优先级最高，覆盖 settings.json。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(config.CAMEL_CODE_SETTINGS_PATH, {"model": "settings-model"})
    monkeypatch.setenv("ANTHROPIC_MODEL", "env-model")

    cfg = load_runtime_config()
    assert cfg.model == "env-model"


def test_settings_direct_env_keys(tmp_path, monkeypatch):
    """settings.json 中可直接使用环境变量名作为键。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(
        config.CAMEL_CODE_SETTINGS_PATH,
        {
            "ANTHROPIC_MODEL": "settings-model",
            "ANTHROPIC_BASE_URL": "https://example.com",
            "ANTHROPIC_AUTH_TOKEN": "settings-token",
        },
    )

    cfg = load_runtime_config()
    assert cfg.model == "settings-model"
    assert cfg.base_url == "https://example.com"
    assert cfg.api_key == "settings-token"


def test_settings_model_alias(tmp_path, monkeypatch):
    """settings.json 中可以使用 model 作为 ANTHROPIC_MODEL 的别名。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(config.CAMEL_CODE_SETTINGS_PATH, {"model": "alias-model"})

    cfg = load_runtime_config()
    assert cfg.model == "alias-model"


def test_env_field_in_settings(tmp_path, monkeypatch):
    """settings.json 的 env 字段可以被真实环境变量覆盖。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(
        config.CAMEL_CODE_SETTINGS_PATH,
        {"env": {"ANTHROPIC_MODEL": "env-field-model"}},
    )

    cfg = load_runtime_config()
    assert cfg.model == "env-field-model"


def test_top_level_alias_overrides_env_field(tmp_path, monkeypatch):
    """顶层别名字段优先级高于 env 字段中的同名环境变量。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(
        config.CAMEL_CODE_SETTINGS_PATH,
        {
            "model": "top-level-model",
            "env": {"ANTHROPIC_MODEL": "env-field-model"},
        },
    )

    cfg = load_runtime_config()
    assert cfg.model == "top-level-model"


def test_default_values_when_no_config(tmp_path, monkeypatch):
    """无任何配置时返回默认值。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    cfg = load_runtime_config()
    assert cfg.provider == "anthropic"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.base_url == ""
    assert cfg.api_key == ""
    assert cfg.max_tokens == 8000
    assert cfg.temperature == 0.1
    assert "default" in cfg.source_summary


def test_invalid_json_raises(tmp_path, monkeypatch):
    """损坏的 settings.json 抛出 ValueError。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    path = config.CAMEL_CODE_SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="配置文件格式错误"):
        load_runtime_config()


def test_max_tokens_must_be_int(tmp_path, monkeypatch):
    """MODEL_MAX_TOKENS 非整数时抛出 ValueError。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(
        config.CAMEL_CODE_SETTINGS_PATH,
        {"MODEL_MAX_TOKENS": "not-a-number"},
    )

    with pytest.raises(ValueError, match="MODEL_MAX_TOKENS"):
        load_runtime_config()


# ── 热更新测试 ─────────────────────────────────────────────────
def test_load_runtime_config_reloads_settings(tmp_path, monkeypatch):
    """每次调用 load_runtime_config 都会重新读取 settings.json。"""
    monkeypatch.setattr(
        config, "CAMEL_CODE_SETTINGS_PATH", tmp_path / ".camel-code" / "settings.json"
    )
    _clear_env(monkeypatch)

    _write_settings(config.CAMEL_CODE_SETTINGS_PATH, {"model": "first-model"})
    first = load_runtime_config()
    assert first.model == "first-model"

    _write_settings(config.CAMEL_CODE_SETTINGS_PATH, {"model": "second-model"})
    second = load_runtime_config()
    assert second.model == "second-model"


# ── 适配器集成测试 ─────────────────────────────────────────────
def test_create_llm_uses_runtime_config(monkeypatch):
    """create_llm 使用传入的 RuntimeConfig，不依赖环境变量。"""
    from src.models.adapter import create_llm

    runtime_config = RuntimeConfig(
        provider="openai",
        model="gpt-4o",
        base_url="",
        api_key="test-key",
        max_tokens=1024,
        temperature=0.7,
        source_summary="test",
    )

    # 仅需验证创建过程不抛异常且不读取环境
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    llm = create_llm(runtime_config)
    assert llm is not None
    assert llm.model_name == "gpt-4o"


# ── LeadAgent 热更新测试 ───────────────────────────────────────
def test_lead_agent_refresh_llm_reloads_config(monkeypatch):
    """LeadAgent._refresh_llm 每次调用都重新加载配置。"""
    from src.agents.lead_agent import LeadAgent

    calls: list[int] = []

    def fake_load_runtime_config() -> RuntimeConfig:
        idx = len(calls)
        calls.append(idx)
        return RuntimeConfig(
            provider="anthropic",
            model=f"model-{idx}",
            base_url="",
            api_key="",
            max_tokens=1000,
            temperature=0.1,
            source_summary="test",
        )

    created: list[str] = []

    def fake_create_llm(cfg: RuntimeConfig) -> object:
        created.append(cfg.model)
        return object()  # 伪造 LLM 实例

    monkeypatch.setattr(
        "src.agents.lead_agent.config.load_runtime_config", fake_load_runtime_config
    )
    monkeypatch.setattr("src.agents.lead_agent.create_llm", fake_create_llm)

    agent = LeadAgent()
    assert agent.model_name == "model-0"
    assert created == ["model-0"]

    agent._refresh_llm()
    assert agent.model_name == "model-1"
    assert created == ["model-0", "model-1"]
