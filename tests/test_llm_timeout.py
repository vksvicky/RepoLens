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
    _stream_openai_compatible,
    analyze,
    resolve_llm_timeout,
)


def test_resolve_llm_timeout_defaults() -> None:
    assert resolve_llm_timeout(ModelConfig(provider="ollama")) == DEFAULT_OLLAMA_TIMEOUT
    assert resolve_llm_timeout(ModelConfig(provider="openai")) == DEFAULT_LLM_TIMEOUT
    assert resolve_llm_timeout(ModelConfig(provider="ollama", timeout_seconds=60)) == 60.0


def test_analyze_timeout_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
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


def test_stream_keeps_going_when_tokens_arrive_past_the_prefill_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A long steady stream is not cut off at --timeout."""

    class _FakeResponse:
        status_code = 200

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def close(self) -> None:
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"ab"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"cd"}}]}'

    client = MagicMock()
    client.stream.return_value = _FakeResponse()
    # First token inside the prefill budget, then a later token still inside
    # the silence window. Total time is past --timeout.
    ticks = iter([0.0, 1.0, 1.0, 200.0, 200.0])
    monkeypatch.setattr(
        "repolens.llm.sse.time.monotonic",
        lambda: next(ticks, 200.0),
    )

    text = _stream_openai_compatible(
        client,
        base="http://example.test/v1",
        headers={},
        payload={"model": "m", "messages": []},
        model="m",
        provider="ollama",
        timeout=10.0,
        silence_timeout=300.0,
        on_delta=None,
    )
    assert text == "abcd"


def test_stream_aborts_when_tokens_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        status_code = 200

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def close(self) -> None:
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"x"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"y"}}]}'

    client = MagicMock()
    client.stream.return_value = _FakeResponse()
    ticks = iter([0.0, 1.0, 1.0, 50.0])
    monkeypatch.setattr(
        "repolens.llm.sse.time.monotonic",
        lambda: next(ticks, 50.0),
    )

    with pytest.raises(LlmError, match="went silent for 10"):
        _stream_openai_compatible(
            client,
            base="http://example.test/v1",
            headers={},
            payload={"model": "m", "messages": []},
            model="m",
            provider="ollama",
            timeout=7200.0,
            silence_timeout=10.0,
            on_delta=None,
        )


def test_init_writes_ollama_timeout(tmp_path, monkeypatch) -> None:
    from repolens.config import write_user_config

    path = tmp_path / "config.toml"
    with patch("repolens.llm.setup.list_ollama_models", return_value=["qwen2.5:7b"]):
        write_user_config(
            provider="ollama",
            model="qwen2.5:7b",
            base_url="http://127.0.0.1:11434/v1",
            path=path,
        )
    text = path.read_text(encoding="utf-8")
    assert "timeout_seconds = 900" in text
