"""Configuration loading (flags > env > project.toml > user.toml)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderName = Literal["openai", "anthropic", "deepseek", "ollama", "openai_compatible"]
AdaptiveMode = Literal["auto", "full", "changed"]

# Project .repolens.toml must not silently redirect network / credential selection.
PROJECT_MODEL_DENY = frozenset({"base_url", "api_key_env", "provider"})
ALLOWED_KEY_ENVS = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "REPOLENS_API_KEY",
    }
)


class ModelConfig(BaseModel):
    provider: ProviderName | None = None
    model: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    # LLM HTTP timeout (seconds). None → provider default (ollama longer).
    timeout_seconds: float | None = None


class GeneralConfig(BaseModel):
    default_mode: str = "review"
    report_dir: str = "reports"


class ScannersConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["gitleaks", "semgrep", "osv"])
    require: bool = False


class LocalLearningConfig(BaseModel):
    enabled: bool = False
    cache_dir: str = ".repolens"


class AdaptiveConfig(BaseModel):
    """Phase 5 fingerprint cache + timeout recommendations."""

    enabled: bool = True
    mode: AdaptiveMode = "auto"
    timeout_margin: float = 1.3
    min_timeout_seconds: float = 120
    max_timeout_seconds: float = 3600


class DeepConfig(BaseModel):
    """Multi-pass deep coverage review (heuristics + chunked P1→P3)."""

    enabled: bool = True
    chars_per_pass: int = 100_000
    mega_file_lines: int = 500
    # Empty list falls back to package defaults in mega_files / runner.
    mega_file_exclude_globs: list[str] = Field(default_factory=list)
    # Empty map → packaged FP-calibration defaults (see repolens.fp_calibrations).
    # Set an id to false to disable; unknown ids are ignored.
    fp_calibrations: dict[str, bool] = Field(default_factory=dict)


class RepoLensConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    scanners: ScannersConfig = Field(default_factory=ScannersConfig)
    local_learning: LocalLearningConfig = Field(default_factory=LocalLearningConfig)
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)
    deep: DeepConfig = Field(default_factory=DeepConfig)


def user_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "repolens" / "config.toml"
    return Path.home() / ".config" / "repolens" / "config.toml"


def load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_dicts(out[key], value)  # type: ignore[arg-type]
        else:
            out[key] = value
    return out


def sanitize_project_config(project: dict[str, Any], *, trust_project: bool) -> dict[str, Any]:
    """Strip credential/network model fields from untrusted project config."""
    if trust_project or "model" not in project:
        return project
    model = project.get("model")
    if not isinstance(model, dict):
        return project
    cleaned = {k: v for k, v in model.items() if k not in PROJECT_MODEL_DENY}
    return {**project, "model": cleaned}


def env_overrides() -> dict[str, Any]:
    """Overlay from REPOLENS_* environment variables."""
    model: dict[str, Any] = {}
    if provider := os.environ.get("REPOLENS_PROVIDER"):
        model["provider"] = provider
    if name := os.environ.get("REPOLENS_MODEL"):
        model["model"] = name
    if base := os.environ.get("REPOLENS_BASE_URL"):
        model["base_url"] = base
    if key_env := os.environ.get("REPOLENS_API_KEY_ENV"):
        model["api_key_env"] = key_env
    if timeout := os.environ.get("REPOLENS_TIMEOUT"):
        try:
            model["timeout_seconds"] = float(timeout)
        except ValueError as exc:
            raise ValueError(
                f"REPOLENS_TIMEOUT must be a number of seconds, got {timeout!r}"
            ) from exc

    general: dict[str, Any] = {}
    if report_dir := os.environ.get("REPOLENS_REPORT_DIR"):
        general["report_dir"] = report_dir

    data: dict[str, Any] = {}
    if model:
        data["model"] = model
    if general:
        data["general"] = general
    return data


def _validate_api_key_env(cfg: RepoLensConfig) -> None:
    env_name = cfg.model.api_key_env
    if env_name and env_name not in ALLOWED_KEY_ENVS:
        raise ValueError(
            f"Unsupported api_key_env {env_name!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_KEY_ENVS))}"
        )


def load_config(
    project_root: Path | None = None,
    *,
    trust_project: bool = False,
) -> RepoLensConfig:
    data: dict[str, Any] = {}
    data = merge_dicts(data, load_toml(user_config_path()))
    if project_root is not None:
        project = load_toml(project_root / ".repolens.toml")
        project = sanitize_project_config(project, trust_project=trust_project)
        data = merge_dicts(data, project)
    data = merge_dicts(data, env_overrides())
    cfg = RepoLensConfig.model_validate(data)
    _validate_api_key_env(cfg)
    return cfg


def resolve_api_key(model: ModelConfig) -> str | None:
    env_name = model.api_key_env
    if not env_name:
        defaults = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "ollama": None,
            "openai_compatible": "REPOLENS_API_KEY",
        }
        env_name = defaults.get(model.provider or "")
    if not env_name:
        return None
    if env_name not in ALLOWED_KEY_ENVS:
        raise ValueError(
            f"Unsupported api_key_env {env_name!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_KEY_ENVS))}"
        )
    value = os.environ.get(env_name)
    return value if value else None


def write_user_config(
    *,
    provider: str | None,
    model: str | None = None,
    api_key_env: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
    path: Path | None = None,
) -> Path:
    """Write a minimal user config (used by `repolens init`)."""
    target = path or user_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by `repolens init`. Do not commit API keys.",
        "",
        "[general]",
        'report_dir = "reports"',
        "",
        "[model]",
    ]
    if provider:
        lines.append(f'provider = "{provider}"')
    else:
        lines.append(
            '# provider = "openai"  # openai | anthropic | deepseek | openai_compatible | ollama'
        )
    if model:
        lines.append(f'model = "{model}"')
    if api_key_env:
        lines.append(f'api_key_env = "{api_key_env}"')
    if base_url:
        lines.append(f'base_url = "{base_url}"')
    if timeout_seconds is not None:
        lines.append(f"timeout_seconds = {timeout_seconds:g}")
    elif provider == "ollama":
        # Local models often need longer than cloud APIs for large prompts.
        lines.append("timeout_seconds = 900")
    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def resolve_report_dir(root: Path, report_dir: str) -> Path:
    """Resolve report directory under project root (reject escapes)."""
    candidate = Path(report_dir)
    if candidate.is_absolute():
        raise ValueError(
            f"report_dir must be relative to the project root, got absolute path: {report_dir}"
        )
    resolved = (root / candidate).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"report_dir escapes project root: {report_dir}"
        ) from exc
    return resolved
