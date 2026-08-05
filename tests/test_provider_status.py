"""Ollama /api/ps status helper."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from repolens.provider_status import ollama_running_summary


def test_ollama_running_summary_idle() -> None:
    resp = MagicMock()
    resp.read.return_value = json.dumps({"models": []}).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    with patch("repolens.provider_status.urllib.request.urlopen", return_value=resp):
        text = ollama_running_summary("http://127.0.0.1:11434/v1")
    assert text is not None
    assert "idle" in text.lower() or "waiting" in text.lower()


def test_ollama_running_summary_with_model() -> None:
    payload = {
        "models": [
            {"name": "qwen2.5-coder:32b", "size": 20 * 1024**3},
        ]
    }
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    with patch("repolens.provider_status.urllib.request.urlopen", return_value=resp):
        text = ollama_running_summary("http://127.0.0.1:11434")
    assert text is not None
    assert "qwen2.5-coder:32b" in text
    assert "GiB" in text


def test_ollama_running_summary_unreachable() -> None:
    with patch(
        "repolens.provider_status.urllib.request.urlopen",
        side_effect=OSError("down"),
    ):
        assert ollama_running_summary() is None
