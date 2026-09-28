"""Phase 9: Bedrock Converse stream + SigV4."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.config import ModelConfig
from repolens.llm import LlmError, analyze_raw
from repolens.llm.bedrock import (
    encode_event_stream_message,
    extract_text_from_bedrock_payload,
    iter_bedrock_text_deltas,
    sigv4_headers,
)
from repolens.providers import default_key_env_for, default_model_for

runner = CliRunner()


def test_bedrock_defaults() -> None:
    assert default_key_env_for("bedrock") == "AWS_ACCESS_KEY_ID"
    assert default_model_for("bedrock") == "amazon.nova-lite-v1:0"


def test_extract_text_ignores_non_object_payloads() -> None:
    assert extract_text_from_bedrock_payload(b"[]") is None
    assert extract_text_from_bedrock_payload(b"null") is None
    assert extract_text_from_bedrock_payload(b'{"contentBlockDelta":"nope"}') is None
    assert extract_text_from_bedrock_payload(b"not-json") is None


def test_analyze_raw_bedrock_empty_stream_raises(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    cfg = ModelConfig(provider="bedrock", model="amazon.nova-lite-v1:0")
    response = MagicMock()
    response.status_code = 200
    response.iter_bytes.return_value = iter([b""])
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    with pytest.raises(LlmError, match="empty content"):
        analyze_raw("prompt", cfg, client=client)


def test_extract_text_from_bedrock_payload() -> None:
    payload = json.dumps(
        {"contentBlockDelta": {"delta": {"text": "hello"}, "contentBlockIndex": 0}}
    ).encode()
    assert extract_text_from_bedrock_payload(payload) == "hello"


def test_event_stream_roundtrip_text() -> None:
    payload = json.dumps(
        {"contentBlockDelta": {"delta": {"text": '{"a":1}'}}}
    ).encode()
    blob = encode_event_stream_message(payload)
    texts = list(iter_bedrock_text_deltas(iter([blob])))
    assert texts == ['{"a":1}']


def test_sigv4_headers_stable_shape() -> None:
    headers = sigv4_headers(
        method="POST",
        url="https://bedrock-runtime.us-east-1.amazonaws.com/model/m/converse-stream",
        body=b"{}",
        region="us-east-1",
        access_key="AKIATEST",
        secret_key="secret",
        session_token=None,
        amz_date="20260101T000000Z",
    )
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIATEST/")
    assert "X-Amz-Date" in headers
    assert headers["Host"] == "bedrock-runtime.us-east-1.amazonaws.com"


def test_analyze_raw_bedrock_streams(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    cfg = ModelConfig(provider="bedrock", model="amazon.nova-lite-v1:0")
    payload = json.dumps(
        {"contentBlockDelta": {"delta": {"text": '{"confidence":9}'}}}
    ).encode()
    blob = encode_event_stream_message(payload)
    response = MagicMock()
    response.status_code = 200
    response.iter_bytes.return_value = iter([blob])
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    seen: list[str] = []
    text = analyze_raw("prompt", cfg, client=client, on_delta=seen.append)
    assert text == '{"confidence":9}'
    assert seen == ['{"confidence":9}']
    _args, kwargs = client.stream.call_args
    assert "Authorization" in kwargs["headers"]
    assert "us-west-2" in str(kwargs.get("url") or _args[1])


def test_analyze_raw_bedrock_missing_creds(monkeypatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    cfg = ModelConfig(provider="bedrock")
    with pytest.raises(LlmError, match="AWS_ACCESS_KEY_ID"):
        analyze_raw("prompt", cfg, client=MagicMock())


def test_init_bedrock_writes_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "bedrock", "--force"])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'provider = "bedrock"' in text
    assert "AWS_ACCESS_KEY_ID" in text
    assert "nova-lite" in text
