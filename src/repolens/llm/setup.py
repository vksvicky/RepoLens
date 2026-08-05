"""Timeouts, Ollama detection, and provider defaults."""

from __future__ import annotations

import json

import httpx

from repolens.config import ModelConfig

SYSTEM_PROMPT = """You are RepoLens, a rigorous code reviewer.
Return ONLY valid JSON matching the FindingReport schema:
{
  "schemaVersion": "1.0",
  "confidence": 0-100,
  "summary": {"critical":0,"high":0,"medium":0,"low":0},
  "issues": [{
    "severity":"CRITICAL|HIGH|MEDIUM|LOW",
    "priority":"P1|P2|P3",
    "category":"string",
    "file":"path",
    "line":1,
    "title":"string",
    "explanation":"string",
    "impact":"string",
    "recommendedFix":"string",
    "codeExample":"string",
    "fixTiming":"immediately|before launch|after launch|if time permits",
    "cwe": null,
    "owasp": null
  }],
  "durabilityGaps": ["string"],
  "scores": null
}
Critical and High issues MUST include non-empty impact and codeExample.
Be evidence-based. Prefer fewer high-confidence findings over speculation.
"""


OLLAMA_PROBE_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_FALLBACK_MODEL = "llama3.1"
DEFAULT_LLM_TIMEOUT = 120.0
DEFAULT_OLLAMA_TIMEOUT = 900.0


def resolve_llm_timeout(model_cfg: ModelConfig) -> float:
    """Seconds for the chat-completions HTTP call."""
    if model_cfg.timeout_seconds is not None and model_cfg.timeout_seconds > 0:
        return float(model_cfg.timeout_seconds)
    if model_cfg.provider == "ollama":
        return DEFAULT_OLLAMA_TIMEOUT
    return DEFAULT_LLM_TIMEOUT


def detect_ollama(*, timeout: float = 0.5) -> bool:
    """Return True if a local Ollama HTTP API answers on the default port."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(OLLAMA_PROBE_URL)
        return response.status_code < 500
    except (httpx.HTTPError, OSError):
        return False


def list_ollama_models(*, timeout: float = 1.0) -> list[str]:
    """Return model names reported by the local Ollama `/api/tags` endpoint."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(OLLAMA_PROBE_URL)
        if response.status_code >= 500:
            return []
        payload = response.json()
    except (httpx.HTTPError, OSError, json.JSONDecodeError, ValueError):
        return []
    names: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def pick_ollama_model(
    installed: list[str], *, fallback: str = OLLAMA_FALLBACK_MODEL
) -> str:
    """Prefer an already-installed model; only use fallback when the list is empty."""
    return installed[0] if installed else fallback


def resolve_ollama_model(
    explicit: str | None = None,
) -> tuple[str, list[str]]:
    """Return (model_to_use, installed_models). Explicit `--model` always wins."""
    installed = list_ollama_models()
    if explicit and explicit.strip():
        return explicit.strip(), installed
    return pick_ollama_model(installed), installed


def provider_setup_hints() -> list[str]:
    """Actionable next steps when [model].provider is missing."""
    from repolens.config import user_config_path

    cfg = user_config_path()
    hints = [
        f"RepoLens needs a one-time model config at: {cfg}",
        "Having Ollama installed is not enough — point RepoLens at it with:",
        "  repolens init --provider ollama",
        "Or use a cloud key:  repolens init --provider openai",
        "Or skip the LLM:  repolens review --path … --dry-run",
        "                 repolens review --path … --scanners-only",
        "Docs: docs/setup-ai-and-scanners.md",
    ]
    if detect_ollama():
        installed = list_ollama_models()
        if installed:
            chosen = pick_ollama_model(installed)
            listed = ", ".join(installed[:5]) + ("…" if len(installed) > 5 else "")
            hints.insert(
                1,
                f"Detected Ollama with installed model(s): {listed} — "
                f"run:  repolens init --provider ollama  "
                f"(will use {chosen} unless you pass --model)",
            )
        else:
            hints.insert(
                1,
                "Detected Ollama running on http://127.0.0.1:11434 (no models yet) — "
                f"run:  ollama pull {OLLAMA_FALLBACK_MODEL}  then  "
                "repolens init --provider ollama",
            )
            hints.insert(
                2,
                "Or pull any model you prefer, then: "
                "repolens init --provider ollama --model <name>",
            )
    return hints


def default_base_url(provider: str | None) -> str:
    return {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "ollama": "http://127.0.0.1:11434/v1",
        "openai_compatible": "http://127.0.0.1:11434/v1",
    }.get(provider or "", "https://api.openai.com/v1")


def default_model(provider: str | None) -> str:
    if provider in {"ollama", "openai_compatible"}:
        return resolve_ollama_model(None)[0]
    return {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-chat",
    }.get(provider or "", "gpt-4.1-mini")


