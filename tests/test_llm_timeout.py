"""LLM timeout resolution and timeout error messaging."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from repolens.config import ModelConfig
from repolens.llm import (
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_OLLAMA_TIMEOUT,
    LlmError,
    analyze,
    resolve_llm_timeout,
)


def test_resolve_llm_timeout_defaults() -> None:
    assert resolve_llm_timeout(ModelConfig(provider="ollama")) == DEFAULT_OLLAMA_TIMEOUT
    assert resolve_llm_timeout(ModelConfig(provider="openai")) == DEFAULT_LLM_TIMEOUT
    assert resolve_llm_timeout(ModelConfig(provider="ollama", timeout_seconds=60)) == 60.0


def test_analyze_timeout_message() -> None:
    cfg = ModelConfig(provider="ollama", model="qwen2.5:7b", timeout_seconds=12)
    client = MagicMock()
    # Ollama uses streaming; timeout surfaces from client.stream(...)
    client.stream.side_effect = httpx.TimeoutException("timed out")
    with pytest.raises(LlmError, match="timed out after 12"):
        analyze("prompt", cfg, client=client)


def test_env_timeout_override(tmp_path, monkeypatch) -> None:
    from repolens.config import load_config, write_user_config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    write_user_config(provider="ollama", model="qwen2.5:7b")
    monkeypatch.setenv("REPOLENS_TIMEOUT", "1800")
    cfg = load_config(tmp_path)
    assert cfg.model.timeout_seconds == 1800.0


def test_init_writes_ollama_timeout(tmp_path, monkeypatch) -> None:
    from repolens.config import write_user_config

    path = tmp_path / "config.toml"
    with patch("repolens.llm.list_ollama_models", return_value=["qwen2.5:7b"]):
        write_user_config(
            provider="ollama",
            model="qwen2.5:7b",
            base_url="http://127.0.0.1:11434/v1",
            path=path,
        )
    text = path.read_text(encoding="utf-8")
    assert "timeout_seconds = 900" in text
