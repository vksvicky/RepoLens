"""Ollama reachability probe and provider-missing guidance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from repolens.llm import (
    detect_ollama,
    list_ollama_models,
    pick_ollama_model,
    provider_setup_hints,
    resolve_ollama_model,
)


def test_detect_ollama_true_on_tags() -> None:
    response = MagicMock()
    response.status_code = 200
    with patch("repolens.llm.setup.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        assert detect_ollama() is True
        client.get.assert_called_once()


def test_detect_ollama_false_on_connection_error() -> None:
    with patch("repolens.llm.setup.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = httpx.ConnectError("down")
        assert detect_ollama() is False


def test_list_ollama_models_parses_tags() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "models": [{"name": "qwen2.5:7b"}, {"name": "llama3.1:latest"}]
    }
    with patch("repolens.llm.setup.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        assert list_ollama_models() == ["qwen2.5:7b", "llama3.1:latest"]


def test_pick_ollama_model_uses_installed_not_fallback() -> None:
    assert pick_ollama_model(["qwen2.5:7b"]) == "qwen2.5:7b"
    assert pick_ollama_model([]) == "llama3.1"


def test_resolve_ollama_model_explicit_wins() -> None:
    with patch("repolens.llm.setup.list_ollama_models", return_value=["qwen2.5:7b"]):
        assert resolve_ollama_model("mistral") == ("mistral", ["qwen2.5:7b"])


def test_resolve_ollama_model_picks_installed() -> None:
    with patch("repolens.llm.setup.list_ollama_models", return_value=["qwen2.5:7b"]):
        assert resolve_ollama_model(None) == ("qwen2.5:7b", ["qwen2.5:7b"])


def test_provider_setup_hints_when_ollama_up() -> None:
    with (
        patch("repolens.llm.setup.detect_ollama", return_value=True),
        patch("repolens.llm.setup.list_ollama_models", return_value=["qwen2.5:7b"]),
    ):
        hints = provider_setup_hints()
    assert any("qwen2.5:7b" in h for h in hints)
    assert any("init --provider ollama" in h for h in hints)
    assert not any("ollama pull llama3.1" in h for h in hints)


def test_provider_setup_hints_when_ollama_down() -> None:
    with patch("repolens.llm.setup.detect_ollama", return_value=False):
        hints = provider_setup_hints()
    assert any("init --provider" in h for h in hints)
    assert any("dry-run" in h.lower() or "scanners-only" in h.lower() for h in hints)
