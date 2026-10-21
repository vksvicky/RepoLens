"""Token counts from one model call. A missing count stays None."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class RawCompletion(str):
    """Model text for one call. ``usage`` is that call's counts, or None."""

    usage: LlmUsage | None

    def __new__(cls, text: str, usage: LlmUsage | None = None) -> RawCompletion:
        obj = str.__new__(cls, text)
        obj.usage = usage
        return obj


class UsageBox:
    """Last non-empty field in one stream wins. Fields are not added."""

    def __init__(self) -> None:
        self.value: LlmUsage | None = None

    def note(self, incoming: LlmUsage | None) -> None:
        self.value = fold_usage(self.value, incoming)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _add(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    return left + right


def add_usage(left: LlmUsage | None, right: LlmUsage | None) -> LlmUsage | None:
    """Sum two calls. Either missing side makes the total missing."""
    if left is None or right is None:
        return None
    return LlmUsage(
        prompt_tokens=_add(left.prompt_tokens, right.prompt_tokens),
        completion_tokens=_add(left.completion_tokens, right.completion_tokens),
        total_tokens=_add(left.total_tokens, right.total_tokens),
    )


def fold_usage(current: LlmUsage | None, incoming: LlmUsage | None) -> LlmUsage | None:
    """Keep the later value for each field. Do not add a field to itself."""
    if incoming is None:
        return current
    if current is None:
        return incoming
    return LlmUsage(
        prompt_tokens=_later(incoming.prompt_tokens, current.prompt_tokens),
        completion_tokens=_later(incoming.completion_tokens, current.completion_tokens),
        total_tokens=_later(incoming.total_tokens, current.total_tokens),
    )


def _later(incoming: int | None, current: int | None) -> int | None:
    if incoming is None:
        return current
    return incoming


def call_usage(value: object) -> LlmUsage | None:
    usage = getattr(value, "usage", None)
    if not isinstance(usage, LlmUsage):
        return None
    if (
        usage.prompt_tokens is None
        and usage.completion_tokens is None
        and usage.total_tokens is None
    ):
        return None
    return usage


def _measured(usage: LlmUsage) -> LlmUsage | None:
    if (
        usage.prompt_tokens is None
        and usage.completion_tokens is None
        and usage.total_tokens is None
    ):
        return None
    return usage


def json_data_line(line: str) -> dict[str, object] | None:
    text = line.strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    return data


def usage_from_openai_payload(data: object) -> LlmUsage | None:
    if not isinstance(data, dict):
        return None
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    return _measured(
        LlmUsage(
            prompt_tokens=_as_int(usage.get("prompt_tokens")),
            completion_tokens=_as_int(usage.get("completion_tokens")),
            total_tokens=_as_int(usage.get("total_tokens")),
        )
    )


def usage_from_anthropic_event(data: object) -> LlmUsage | None:
    if not isinstance(data, dict):
        return None
    kind = data.get("type")
    usage: object | None
    if kind == "message_start":
        message = data.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
    elif kind == "message_delta":
        usage = data.get("usage")
    else:
        return None
    if not isinstance(usage, dict):
        return None
    return _measured(
        LlmUsage(
            prompt_tokens=_as_int(usage.get("input_tokens")),
            completion_tokens=_as_int(usage.get("output_tokens")),
        )
    )


def usage_from_gemini_payload(data: object) -> LlmUsage | None:
    if not isinstance(data, dict):
        return None
    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        return None
    return _measured(
        LlmUsage(
            prompt_tokens=_as_int(usage.get("promptTokenCount")),
            completion_tokens=_as_int(usage.get("candidatesTokenCount")),
            total_tokens=_as_int(usage.get("totalTokenCount")),
        )
    )


def usage_from_bedrock_payload(payload: bytes) -> LlmUsage | None:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    meta = data.get("metadata")
    usage = meta.get("usage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict):
        direct = data.get("usage")
        usage = direct if isinstance(direct, dict) else None
    if not isinstance(usage, dict):
        return None
    return _measured(
        LlmUsage(
            prompt_tokens=_as_int(usage.get("inputTokens")),
            completion_tokens=_as_int(usage.get("outputTokens")),
            total_tokens=_as_int(usage.get("totalTokens")),
        )
    )
