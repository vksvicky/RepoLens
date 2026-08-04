"""Config merge order and API key resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.config import (
    ModelConfig,
    load_config,
    resolve_api_key,
    resolve_report_dir,
    write_user_config,
)


def test_project_toml_model_name_overrides_user(tmp_path: Path, monkeypatch) -> None:
    user_dir = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_dir))
    write_user_config(
        provider="openai",
        model="user-model",
        path=user_dir / "repolens" / "config.toml",
    )

    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        '[model]\nprovider = "ollama"\nmodel = "project-model"\nbase_url = "http://evil.test"\n',
        encoding="utf-8",
    )

    cfg = load_config(project, trust_project=False)
    # Untrusted project cannot override provider/base_url
    assert cfg.model.provider == "openai"
    assert cfg.model.base_url is None
    assert cfg.model.model == "project-model"


def test_trust_project_allows_provider_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        '[model]\nprovider = "ollama"\nmodel = "local"\n'
        'base_url = "http://127.0.0.1:11434/v1"\n',
        encoding="utf-8",
    )
    cfg = load_config(project, trust_project=True)
    assert cfg.model.provider == "ollama"
    assert cfg.model.base_url == "http://127.0.0.1:11434/v1"


def test_env_overrides_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        '[model]\nmodel = "from-toml"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("REPOLENS_PROVIDER", "ollama")
    monkeypatch.setenv("REPOLENS_MODEL", "from-env")

    cfg = load_config(project)
    assert cfg.model.provider == "ollama"
    assert cfg.model.model == "from-env"


def test_resolve_api_key_default_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    key = resolve_api_key(ModelConfig(provider="openai"))
    assert key == "sk-test"


def test_reject_arbitrary_api_key_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("REPOLENS_API_KEY_ENV", "AWS_SECRET_ACCESS_KEY")
    with pytest.raises(ValueError, match="Unsupported api_key_env"):
        load_config(tmp_path)


def test_report_dir_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_report_dir(tmp_path, "../outside")
