"""Phase 9: Gemini AI Studio native streaming transport."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.config import ModelConfig, resolve_api_key
from repolens.llm import LlmError, _parse_gemini_sse_text_delta, analyze_raw
from repolens.providers import ALLOWED_KEY_ENVS, default_key_env_for, default_model_for

runner = CliRunner()


def _gemini_sse(text: str) -> str:
    return "data: " + json.dumps(
        {"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}]}
    )


def test_parse_gemini_sse_text_delta() -> None:
    assert _parse_gemini_sse_text_delta(_gemini_sse('{"a":')) == '{"a":'
    assert _parse_gemini_sse_text_delta("data: [DONE]") is None
    assert _parse_gemini_sse_text_delta("event: ping") is None


def test_gemini_defaults() -> None:
    assert default_key_env_for("gemini") == "GEMINI_API_KEY"
    assert default_model_for("gemini") == "gemini-2.0-flash"
    assert "GEMINI_API_KEY" in ALLOWED_KEY_ENVS


def test_resolve_api_key_gemini(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    assert resolve_api_key(ModelConfig(provider="gemini")) == "AIza-test"


def test_analyze_raw_gemini_streams_on_delta() -> None:
    cfg = ModelConfig(
        provider="gemini", model="gemini-2.0-flash", api_key_env="GEMINI_API_KEY"
    )
    chunks = [_gemini_sse('{"confidence":'), _gemini_sse("2}"), "data: [DONE]"]
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(chunks)
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    seen: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GEMINI_API_KEY", "test-key")
        text = analyze_raw("prompt", cfg, client=client, on_delta=seen.append)
    assert text == '{"confidence":2}'
    assert seen == ['{"confidence":', "2}"]
    client.stream.assert_called_once()
    args, kwargs = client.stream.call_args
    assert kwargs.get("params", {}).get("alt") == "sse"
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    url = kwargs.get("url") or (args[1] if len(args) > 1 else "")
    assert "streamGenerateContent" in str(url)


def test_analyze_raw_gemini_empty_raises() -> None:
    cfg = ModelConfig(provider="gemini", api_key_env="GEMINI_API_KEY")
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(["data: [DONE]"])
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GEMINI_API_KEY", "test-key")
        with pytest.raises(LlmError, match="empty content"):
            analyze_raw("prompt", cfg, client=client, on_delta=lambda _: None)


def test_analyze_raw_gemini_missing_key() -> None:
    cfg = ModelConfig(provider="gemini", api_key_env="GEMINI_API_KEY")
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(LlmError, match="GEMINI_API_KEY"):
            analyze_raw("prompt", cfg, client=MagicMock())


def test_init_gemini_writes_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "gemini", "--force"])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'provider = "gemini"' in text
    assert 'api_key_env = "GEMINI_API_KEY"' in text
    assert "gemini-2.0-flash" in text
    assert "generativelanguage.googleapis.com" in text
