"""Named LLM provider aliases (Phase 8) and transport helpers.

Aliases keep OpenAI-compatible chat-completions transport. Native Gemini /
Bedrock SDKs remain Phase 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Canonical + Phase 8 aliases stored in config / accepted by ``repolens init``.
ProviderName = Literal[
    "openai",
    "anthropic",
    "deepseek",
    "ollama",
    "openai_compatible",
    "azure",
    "azure_openai",
    "mistral",
    "groq",
    "openrouter",
    "together",
    "fireworks",
]

CANONICAL_PROVIDERS = frozenset(
    {"openai", "anthropic", "deepseek", "ollama", "openai_compatible"}
)

# OpenAI-compatible chat + SSE path (everything except Anthropic Messages).
OPENAI_COMPAT_TRANSPORT = frozenset(
    {
        "openai",
        "deepseek",
        "ollama",
        "openai_compatible",
        "azure",
        "azure_openai",
        "mistral",
        "groq",
        "openrouter",
        "together",
        "fireworks",
    }
)

ALLOWED_KEY_ENVS = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "REPOLENS_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
    }
)


@dataclass(frozen=True)
class ProviderAlias:
    """Defaults written by ``repolens init --provider <alias>``."""

    default_model: str | None
    api_key_env: str | None
    base_url: str | None
    # Azure / deployment hosts need an explicit resource endpoint.
    requires_base_url: bool = False
    notes: str = ""


# P0 + P1 OpenAI-shaped aliases (design: phase-8-provider-aliases-and-recipes.md).
PROVIDER_ALIASES: dict[str, ProviderAlias] = {
    "azure": ProviderAlias(
        default_model="gpt-4o-mini",
        api_key_env="AZURE_OPENAI_API_KEY",
        base_url=None,
        requires_base_url=True,
        notes="Pass --base-url https://<resource>.openai.azure.com/openai/v1 "
        "and use the deployment name as --model.",
    ),
    "azure_openai": ProviderAlias(
        default_model="gpt-4o-mini",
        api_key_env="AZURE_OPENAI_API_KEY",
        base_url=None,
        requires_base_url=True,
        notes="Pass --base-url https://<resource>.openai.azure.com/openai/v1 "
        "and use the deployment name as --model.",
    ),
    "mistral": ProviderAlias(
        default_model="mistral-small-latest",
        api_key_env="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
    ),
    "groq": ProviderAlias(
        default_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
    ),
    "openrouter": ProviderAlias(
        default_model="openai/gpt-4.1-mini",
        api_key_env="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
    ),
    "together": ProviderAlias(
        default_model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        api_key_env="TOGETHER_API_KEY",
        base_url="https://api.together.xyz/v1",
    ),
    "fireworks": ProviderAlias(
        default_model="accounts/fireworks/models/llama-v3p1-70b-instruct",
        api_key_env="FIREWORKS_API_KEY",
        base_url="https://api.fireworks.ai/inference/v1",
    ),
}

INIT_PROVIDERS = frozenset(
    {
        "openai",
        "anthropic",
        "deepseek",
        "openai_compatible",
        "ollama",
        "none",
        *PROVIDER_ALIASES.keys(),
    }
)

# Recipe-only hosts (no new enum — document as openai_compatible).
RECIPE_ONLY_HOSTS: tuple[tuple[str, str, str], ...] = (
    ("LM Studio", "http://127.0.0.1:1234/v1", "Local OpenAI-compatible server"),
    ("vLLM / llama.cpp", "http://127.0.0.1:8000/v1", "Self-hosted chat completions"),
    (
        "Gemini (OpenAI-compatible gateway)",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "Use Google’s OpenAI-compatible endpoint if available; native SDK is Phase 9",
    ),
)


def is_openai_compat_transport(provider: str | None) -> bool:
    return bool(provider) and provider in OPENAI_COMPAT_TRANSPORT


def default_key_env_for(provider: str | None) -> str | None:
    if not provider:
        return None
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider].api_key_env
    return {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "ollama": None,
        "openai_compatible": "REPOLENS_API_KEY",
    }.get(provider)


def default_base_url_for(provider: str | None) -> str:
    if provider and provider in PROVIDER_ALIASES:
        alias = PROVIDER_ALIASES[provider]
        if alias.base_url:
            return alias.base_url
    return {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "ollama": "http://127.0.0.1:11434/v1",
        "openai_compatible": "http://127.0.0.1:11434/v1",
    }.get(provider or "", "https://api.openai.com/v1")


def default_model_for(provider: str | None) -> str | None:
    """Static default model name (Ollama resolution is handled separately)."""
    if provider and provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider].default_model
    return {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-chat",
        "openai_compatible": None,
        "ollama": None,
    }.get(provider or "")
