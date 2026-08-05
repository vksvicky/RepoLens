"""HTTP transport for OpenAI-compatible and Anthropic chat APIs."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from repolens.config import ModelConfig, resolve_api_key
from repolens.llm.errors import LlmError, _provider_error_hint, _timeout_error
from repolens.llm.parse import parse_report_json
from repolens.llm.setup import (
    SYSTEM_PROMPT,
    default_base_url,
    default_model,
    provider_setup_hints,
    resolve_llm_timeout,
)
from repolens.schema import FindingReport


def analyze(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
) -> FindingReport:
    content = analyze_raw(prompt, model_cfg, client=client)
    return parse_report_json(content)


def analyze_raw(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    if not model_cfg.provider:
        raise LlmError(
            "No model provider configured. "
            + " ".join(provider_setup_hints()[:3])
        )

    # Anthropic uses its Messages API; others use OpenAI-compatible chat completions.
    if model_cfg.provider == "anthropic":
        return _analyze_anthropic(
            prompt, model_cfg, client=client, on_delta=on_delta
        )

    return _analyze_openai_compatible(
        prompt, model_cfg, client=client, on_delta=on_delta
    )


def _provider_error_hint(
    *,
    status_code: int,
    detail: str,
    provider: str | None,
    model: str,
) -> str:
    hint = ""
    if status_code == 404 and provider == "ollama":
        installed = list_ollama_models()
        if installed:
            hint = (
                f" Model {model!r} is not installed. "
                f"Installed: {', '.join(installed[:8])}. "
                f"Run: repolens init --provider ollama --model {installed[0]} --force"
            )
        else:
            hint = (
                f" Model {model!r} may be missing — run: ollama list "
                f"then either `ollama pull {model}` or "
                f"`repolens init --provider ollama --model <name> --force`."
            )
    return (
        f"LLM provider error {status_code}"
        + (f": {detail}" if detail else "")
        + hint
    )


def _timeout_error(timeout: float, model: str, provider: str | None) -> LlmError:
    return LlmError(
        f"LLM timed out after {timeout:g}s talking to {model} ({provider}). "
        "Large repos + local models often need more time. Try: "
        f"`repolens review --timeout {int(timeout * 2)} …`, "
        "set `timeout_seconds` in ~/.config/repolens/config.toml, "
        "or narrow scope with `--mode diff --since HEAD~20`, "
        "`--scanners-only`, or `--dry-run`."
    )


def _parse_sse_chat_chunk(line: str) -> str | None:
    """Extract delta content from one OpenAI-compatible SSE ``data:`` line."""
    text = line.strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    choices = data.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else None


def _analyze_openai_compatible(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
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

    # Stream when a progress callback is provided, or always for local Ollama /
    # OpenAI-compatible BYOK so wait UX can show chars received.
    use_stream = on_delta is not None or model_cfg.provider in {
        "ollama",
        "openai",
        "deepseek",
        "openai_compatible",
    }

    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    if use_stream:
        payload["stream"] = True

    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        if use_stream:
            return _stream_openai_compatible(
                client,
                base=base,
                headers=headers,
                payload=payload,
                model=model,
                provider=model_cfg.provider,
                timeout=timeout,
                on_delta=on_delta,
            )
        response = client.post(f"{base}/chat/completions", headers=headers, json=payload)
        if response.status_code >= 400:
            detail = (response.text or "").strip()
            if len(detail) > 300:
                detail = detail[:300] + "…"
            raise LlmError(
                _provider_error_hint(
                    status_code=response.status_code,
                    detail=detail,
                    provider=model_cfg.provider,
                    model=model,
                )
            )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content
    except httpx.TimeoutException as exc:
        raise _timeout_error(timeout, model, model_cfg.provider) from exc
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete LLM analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _stream_openai_compatible(
    client: httpx.Client,
    *,
    base: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    model: str,
    provider: str | None,
    timeout: float,
    on_delta: Callable[[str], None] | None,
) -> str:
    """Accumulate streamed chat.completion chunks; invoke ``on_delta`` per piece.

    Enforces a **wall-clock** deadline of ``timeout`` seconds. httpx read
    timeouts alone are insufficient: they reset whenever a chunk arrives, so a
    slow but continuous stream can run far past ``--timeout``.
    """
    parts: list[str] = []
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        with client.stream(
            "POST",
            f"{base}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (response.read().decode("utf-8", errors="replace") or "").strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    _provider_error_hint(
                        status_code=response.status_code,
                        detail=detail,
                        provider=provider,
                        model=model,
                    )
                )
            for line in response.iter_lines():
                if time.monotonic() >= deadline:
                    raise _timeout_error(timeout, model, provider)
                if not line:
                    continue
                piece = _parse_sse_chat_chunk(line)
                if piece is None:
                    continue
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
                if time.monotonic() >= deadline:
                    raise _timeout_error(timeout, model, provider)
    except httpx.TimeoutException as exc:
        raise _timeout_error(timeout, model, provider) from exc
    content = "".join(parts)
    if not content.strip():
        raise LlmError("LLM stream completed with empty content")
    return content


def _parse_anthropic_sse_text_delta(line: str) -> str | None:
    """Extract text from an Anthropic ``content_block_delta`` SSE data line."""
    text = line.strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if data.get("type") != "content_block_delta":
        return None
    delta = data.get("delta") or {}
    if delta.get("type") != "text_delta":
        return None
    piece = delta.get("text")
    return piece if isinstance(piece, str) else None


def _analyze_anthropic(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
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
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        return _stream_anthropic(
            client,
            headers=headers,
            payload=payload,
            timeout=timeout,
            on_delta=on_delta,
        )
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Anthropic timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete Anthropic analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _stream_anthropic(
    client: httpx.Client,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    on_delta: Callable[[str], None] | None,
) -> str:
    """Accumulate Anthropic Messages SSE ``text_delta`` chunks."""
    parts: list[str] = []
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (
                    response.read().decode("utf-8", errors="replace") or ""
                ).strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    f"Anthropic error {response.status_code}"
                    + (f": {detail}" if detail else "")
                )
            for line in response.iter_lines():
                if time.monotonic() >= deadline:
                    raise LlmError(
                        f"Anthropic timed out after {timeout:g}s. "
                        f"Try `--timeout {int(timeout * 2)}` or set "
                        "timeout_seconds in config."
                    )
                if not line:
                    continue
                piece = _parse_anthropic_sse_text_delta(line)
                if piece is None:
                    continue
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
                if time.monotonic() >= deadline:
                    raise LlmError(
                        f"Anthropic timed out after {timeout:g}s. "
                        f"Try `--timeout {int(timeout * 2)}` or set "
                        "timeout_seconds in config."
                    )
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Anthropic timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    content = "".join(parts)
    if not content.strip():
        raise LlmError("Anthropic stream completed with empty content")
    return content


