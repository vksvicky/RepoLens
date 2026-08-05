"""LLM provider adapters (OpenAI-compatible + Ollama)."""

from __future__ import annotations

from repolens.llm.errors import LlmError
from repolens.llm.parse import (
    _coerce_report_payload,
    parse_report_json,
    repair_prompt,
)
from repolens.llm.setup import (
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_OLLAMA_TIMEOUT,
    OLLAMA_FALLBACK_MODEL,
    OLLAMA_PROBE_URL,
    SYSTEM_PROMPT,
    default_base_url,
    default_model,
    detect_ollama,
    list_ollama_models,
    pick_ollama_model,
    provider_setup_hints,
    resolve_llm_timeout,
    resolve_ollama_model,
)
from repolens.llm.transport import (
    _parse_anthropic_sse_text_delta,
    _parse_sse_chat_chunk,
    _stream_openai_compatible,
    analyze,
    analyze_raw,
)

__all__ = [
    "DEFAULT_LLM_TIMEOUT",
    "DEFAULT_OLLAMA_TIMEOUT",
    "LlmError",
    "OLLAMA_FALLBACK_MODEL",
    "OLLAMA_PROBE_URL",
    "SYSTEM_PROMPT",
    "analyze",
    "analyze_raw",
    "default_base_url",
    "default_model",
    "detect_ollama",
    "list_ollama_models",
    "parse_report_json",
    "pick_ollama_model",
    "provider_setup_hints",
    "repair_prompt",
    "resolve_llm_timeout",
    "resolve_ollama_model",
    "_coerce_report_payload",
    "_parse_sse_chat_chunk",
    "_parse_anthropic_sse_text_delta",
    "_stream_openai_compatible",
]
