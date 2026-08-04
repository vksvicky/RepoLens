"""LLM provider adapters (OpenAI-compatible + Ollama)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from repolens.config import ModelConfig, resolve_api_key
from repolens.schema import FindingReport

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


class LlmError(RuntimeError):
    """Provider or parse failure."""


def default_base_url(provider: str | None) -> str:
    return {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "ollama": "http://127.0.0.1:11434/v1",
        "openai_compatible": "http://127.0.0.1:11434/v1",
    }.get(provider or "", "https://api.openai.com/v1")


def default_model(provider: str | None) -> str:
    return {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-sonnet-4-20250514",
        "deepseek": "deepseek-chat",
        "ollama": "llama3.1",
        "openai_compatible": "llama3.1",
    }.get(provider or "", "gpt-4.1-mini")


def analyze(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
) -> FindingReport:
    if not model_cfg.provider:
        raise LlmError(
            "No model provider configured. Set [model].provider in config "
            "(openai|anthropic|deepseek|ollama) or see docs/setup-ai-and-scanners.md"
        )

    # Anthropic uses a different API; Phase 1 routes via OpenAI-compatible where possible.
    if model_cfg.provider == "anthropic":
        return _analyze_anthropic(prompt, model_cfg, client=client)

    return _analyze_openai_compatible(prompt, model_cfg, client=client)


def _analyze_openai_compatible(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
) -> FindingReport:
    api_key = resolve_api_key(model_cfg)
    if model_cfg.provider != "ollama" and not api_key:
        raise LlmError(
            f"Missing API key. Export {model_cfg.api_key_env or 'the provider key env var'} "
            "or use provider=ollama for local AI."
        )

    base = (model_cfg.base_url or default_base_url(model_cfg.provider)).rstrip("/")
    model = model_cfg.model or default_model(model_cfg.provider)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }

    owns_client = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        response = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            raise LlmError(f"LLM provider error {response.status_code}")
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return parse_report_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete LLM analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _analyze_anthropic(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
) -> FindingReport:
    api_key = resolve_api_key(model_cfg) or resolve_api_key(
        ModelConfig(provider="anthropic", api_key_env="ANTHROPIC_API_KEY")
    )
    if not api_key:
        raise LlmError("Missing ANTHROPIC_API_KEY for provider=anthropic")

    model = model_cfg.model or default_model("anthropic")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    owns_client = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        response = client.post(
            "https://api.anthropic.com/v1/messages", headers=headers, json=payload
        )
        if response.status_code >= 400:
            raise LlmError(f"Anthropic error {response.status_code}")
        data = response.json()
        content = data["content"][0]["text"]
        return parse_report_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete Anthropic analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def parse_report_json(content: str) -> FindingReport:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        raw = json.loads(match.group(0))
    report = FindingReport.model_validate(raw)
    # Keep summary consistent with issues when model drifts
    counted = report.recount_summary()
    report.summary = counted
    return report


def repair_prompt(original: str, error: str) -> str:
    return (
        f"{original}\n\n---\nYour previous JSON was invalid: {error}\n"
        "Return corrected FindingReport JSON only. "
        "Critical/High must include impact and codeExample."
    )
