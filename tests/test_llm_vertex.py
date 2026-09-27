"""Phase 9: Vertex AI native streaming (reuses Gemini SSE)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.config import ModelConfig
from repolens.llm import LlmError, analyze_raw
from repolens.llm.vertex import resolve_vertex_token, vertex_stream_url
from repolens.providers import default_key_env_for, default_model_for

runner = CliRunner()


def _gemini_sse(text: str) -> str:
    return "data: " + json.dumps(
        {"candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}]}
    )


def test_vertex_defaults() -> None:
    assert default_key_env_for("vertex") == "VERTEX_ACCESS_TOKEN"
    assert default_model_for("vertex") == "gemini-2.0-flash"
    url = vertex_stream_url(
        project="my-proj", location="us-central1", model="gemini-2.0-flash"
    )
    assert "us-central1-aiplatform.googleapis.com" in url
    assert "projects/my-proj" in url
    assert "streamGenerateContent" in url


def test_resolve_vertex_token_env(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_ACCESS_TOKEN", "ya29.env")
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    assert resolve_vertex_token() == "ya29.env"


def test_resolve_vertex_token_missing(monkeypatch) -> None:
    monkeypatch.delenv("VERTEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)

    import builtins

    real_import = builtins.__import__

    def _blocked(name: str, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "google" or name.startswith("google."):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(LlmError, match="VERTEX_ACCESS_TOKEN"):
        resolve_vertex_token()


def test_analyze_raw_vertex_streams(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VERTEX_PROJECT", "p1")
    monkeypatch.setenv("VERTEX_LOCATION", "europe-west1")
    cfg = ModelConfig(provider="vertex", model="gemini-2.0-flash")
    chunks = [_gemini_sse('{"ok":'), _gemini_sse("1}"), "data: [DONE]"]
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(chunks)
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    seen: list[str] = []
    text = analyze_raw("prompt", cfg, client=client, on_delta=seen.append)
    assert text == '{"ok":1}'
    assert seen == ['{"ok":', "1}"]
    _args, kwargs = client.stream.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert "europe-west1-aiplatform.googleapis.com" in str(
        kwargs.get("url") or _args[1]
    )


def test_init_vertex_writes_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "vertex", "--force"])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'provider = "vertex"' in text
    assert "VERTEX_ACCESS_TOKEN" in text
    assert "gemini-2.0-flash" in text
