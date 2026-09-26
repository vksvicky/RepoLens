"""Phase 8 provider alias defaults and init wiring."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.providers import (
    ALLOWED_KEY_ENVS,
    PROVIDER_ALIASES,
    default_base_url_for,
    default_key_env_for,
    default_model_for,
    is_openai_compat_transport,
)

runner = CliRunner()


def test_p0_alias_defaults_map() -> None:
    for name in ("azure", "azure_openai", "mistral", "groq", "openrouter"):
        assert name in PROVIDER_ALIASES
        alias = PROVIDER_ALIASES[name]
        assert alias.api_key_env in ALLOWED_KEY_ENVS
        if name.startswith("azure"):
            assert alias.requires_base_url
            assert alias.base_url is None
        else:
            assert alias.base_url and alias.base_url.startswith("https://")
            assert default_model_for(name)
            assert default_base_url_for(name) == alias.base_url
        assert default_key_env_for(name) == alias.api_key_env
        assert is_openai_compat_transport(name)


def test_p1_alias_defaults_map() -> None:
    for name in ("together", "fireworks"):
        alias = PROVIDER_ALIASES[name]
        assert alias.api_key_env in ALLOWED_KEY_ENVS
        assert is_openai_compat_transport(name)


def test_init_groq_writes_alias_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "groq", "--force"])
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'provider = "groq"' in text
    assert 'api_key_env = "GROQ_API_KEY"' in text
    assert "api.groq.com" in text
    assert "llama-3.3-70b-versatile" in text


def test_init_azure_requires_base_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "azure", "--force"])
    assert result.exit_code == 2
    assert "--base-url" in result.output


def test_init_azure_with_base_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(
        app,
        [
            "init",
            "--provider",
            "azure",
            "--base-url",
            "https://my.openai.azure.com/openai/v1",
            "--model",
            "my-deploy",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'provider = "azure"' in text
    assert "AZURE_OPENAI_API_KEY" in text
    assert "my.openai.azure.com" in text
    assert "my-deploy" in text


def test_resolve_api_key_for_alias(monkeypatch) -> None:
    from repolens.config import ModelConfig, resolve_api_key

    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    assert resolve_api_key(ModelConfig(provider="groq")) == "gsk-test"
