"""Google Gemini AI Studio native transport (Phase 9).

Uses Generative Language API ``streamGenerateContent`` with ``alt=sse``.
Auth is a single ``GEMINI_API_KEY`` via ``x-goog-api-key`` — no google-auth /
Vertex ADC. Vertex and Bedrock remain follow-up Phase 9 slices.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

from repolens.config import ModelConfig, resolve_api_key
from repolens.llm.errors import LlmError
from repolens.llm.setup import SYSTEM_PROMPT, default_model, resolve_llm_timeout

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _parse_gemini_sse_text_delta(line: str) -> str | None:
    """Extract text from one Gemini ``streamGenerateContent`` SSE ``data:`` line."""
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
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            piece = part.get("text")
            if isinstance(piece, str) and piece:
                chunks.append(piece)
    return "".join(chunks) if chunks else None


def analyze_gemini(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    client: httpx.Client | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    api_key = resolve_api_key(model_cfg) or resolve_api_key(
        ModelConfig(provider="gemini", api_key_env="GEMINI_API_KEY")
    )
    if not api_key:
        raise LlmError(
            "Missing GEMINI_API_KEY for provider=gemini. "
            "Export GEMINI_API_KEY or run: repolens init --provider gemini"
        )

    model = model_cfg.model or default_model("gemini") or DEFAULT_GEMINI_MODEL
    # Models may include path-ish ids; keep URL-safe.
    model_path = quote(model, safe=".-_/")
    base = (model_cfg.base_url or GEMINI_API_ROOT).rstrip("/")
    url = f"{base}/models/{model_path}:streamGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    timeout = resolve_llm_timeout(model_cfg)
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        return _stream_gemini(
            client,
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout,
            on_delta=on_delta,
        )
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Gemini timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    except (KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
        raise LlmError(f"Failed to complete Gemini analysis: {exc}") from exc
    finally:
        if owns_client:
            client.close()


def _stream_gemini(
    client: httpx.Client,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    on_delta: Callable[[str], None] | None,
) -> str:
    """Accumulate Gemini SSE text deltas (``alt=sse``)."""
    parts: list[str] = []
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        with client.stream(
            "POST",
            url,
            headers=headers,
            params={"alt": "sse"},
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (
                    response.read().decode("utf-8", errors="replace") or ""
                ).strip()
                if len(detail) > 300:
                    detail = detail[:300] + "…"
                raise LlmError(
                    f"Gemini error {response.status_code}"
                    + (f": {detail}" if detail else "")
                )
            for line in response.iter_lines():
                if time.monotonic() >= deadline:
                    raise LlmError(
                        f"Gemini timed out after {timeout:g}s. "
                        f"Try `--timeout {int(timeout * 2)}` or set "
                        "timeout_seconds in config."
                    )
                if not line:
                    continue
                piece = _parse_gemini_sse_text_delta(line)
                if piece is None:
                    continue
                parts.append(piece)
                if on_delta is not None:
                    on_delta(piece)
                if time.monotonic() >= deadline:
                    raise LlmError(
                        f"Gemini timed out after {timeout:g}s. "
                        f"Try `--timeout {int(timeout * 2)}` or set "
                        "timeout_seconds in config."
                    )
    except httpx.TimeoutException as exc:
        raise LlmError(
            f"Gemini timed out after {timeout:g}s. "
            f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
        ) from exc
    content = "".join(parts)
    if not content.strip():
        raise LlmError("Gemini stream completed with empty content")
    return content
