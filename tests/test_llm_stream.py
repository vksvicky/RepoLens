"""OpenAI-compatible SSE stream parsing and accumulation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from repolens.config import ModelConfig
from repolens.llm import LlmError, _parse_sse_chat_chunk, analyze_raw


def _sse(content: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": content}}]})


def test_parse_sse_chat_chunk_extracts_delta() -> None:
    assert _parse_sse_chat_chunk(_sse("hello")) == "hello"
    assert _parse_sse_chat_chunk("data: [DONE]") is None
    assert _parse_sse_chat_chunk("event: ping") is None


def test_analyze_raw_streams_and_calls_on_delta() -> None:
    cfg = ModelConfig(provider="openai", model="gpt-test", api_key_env="OPENAI_API_KEY")
    chunks = [_sse('{"confidence":'), _sse("1}"), "data: [DONE]"]
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(chunks)
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)

    client = MagicMock()
    client.stream.return_value = response

    seen: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPENAI_API_KEY", "test-key")
        text = analyze_raw("prompt", cfg, client=client, on_delta=seen.append)
    assert text == '{"confidence":1}'
    assert seen == ['{"confidence":', "1}"]
    client.stream.assert_called_once()
    client.post.assert_not_called()


def test_analyze_raw_stream_empty_raises() -> None:
    cfg = ModelConfig(provider="openai", model="gpt-test", api_key_env="OPENAI_API_KEY")
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(["data: [DONE]"])
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPENAI_API_KEY", "test-key")
        with pytest.raises(LlmError, match="empty content"):
            analyze_raw("prompt", cfg, client=client, on_delta=lambda _: None)


def test_analyze_raw_openai_streams_even_without_callback() -> None:
    """First-class BYOK OpenAI-compatible providers always stream for wait UX."""
    cfg = ModelConfig(provider="openai", model="gpt-test", api_key_env="OPENAI_API_KEY")
    chunks = [_sse('{"confidence":0}'), "data: [DONE]"]
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(chunks)
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPENAI_API_KEY", "test-key")
        text = analyze_raw("prompt", cfg, client=client)
    assert text == '{"confidence":0}'
    client.stream.assert_called_once()
    client.post.assert_not_called()


def _anthropic_sse_text(text: str) -> str:
    return "data: " + json.dumps(
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": text},
        }
    )


def test_parse_anthropic_sse_text_delta() -> None:
    from repolens.llm import _parse_anthropic_sse_text_delta

    assert _parse_anthropic_sse_text_delta(_anthropic_sse_text("Hi")) == "Hi"
    assert _parse_anthropic_sse_text_delta('data: {"type":"message_stop"}') is None


def test_analyze_raw_anthropic_streams_and_calls_on_delta() -> None:
    cfg = ModelConfig(
        provider="anthropic", model="claude-test", api_key_env="ANTHROPIC_API_KEY"
    )
    chunks = [
        'data: {"type":"message_start","message":{}}',
        _anthropic_sse_text('{"ok":'),
        _anthropic_sse_text("true}"),
        'data: {"type":"message_stop"}',
    ]
    response = MagicMock()
    response.status_code = 200
    response.iter_lines.return_value = iter(chunks)
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.stream.return_value = response
    seen: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANTHROPIC_API_KEY", "test-key")
        text = analyze_raw("prompt", cfg, client=client, on_delta=seen.append)
    assert text == '{"ok":true}'
    assert seen == ['{"ok":', "true}"]
    client.stream.assert_called_once()
