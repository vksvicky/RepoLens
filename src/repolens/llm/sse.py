"""Shared SSE deadline and HTTP-error helpers for provider streams."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from repolens.llm.errors import LlmError


def stream_deadline(timeout: float) -> float:
    return time.monotonic() + max(0.0, float(timeout))


def timeout_message(label: str, timeout: float) -> str:
    return (
        f"{label} timed out after {timeout:g}s. "
        f"Try `--timeout {int(timeout * 2)}` or set timeout_seconds in config."
    )


def raise_if_past_deadline(deadline: float, timeout: float, label: str) -> None:
    if time.monotonic() >= deadline:
        raise LlmError(timeout_message(label, timeout))


def raise_for_http_status(response: httpx.Response, label: str) -> None:
    if response.status_code < 400:
        return
    detail = (response.read().decode("utf-8", errors="replace") or "").strip()
    if len(detail) > 300:
        detail = detail[:300] + "…"
    suffix = f": {detail}" if detail else ""
    raise LlmError(f"{label} error {response.status_code}{suffix}")


def take_sse_piece(
    parts: list[str],
    piece: str | None,
    on_delta: Callable[[str], None] | None,
) -> None:
    if not piece:
        return
    parts.append(piece)
    if on_delta is not None:
        on_delta(piece)


def consume_sse_lines(
    response: httpx.Response,
    *,
    parse_line: Callable[[str], str | None],
    parts: list[str],
    deadline: float,
    timeout: float,
    label: str,
    on_delta: Callable[[str], None] | None,
) -> None:
    for line in response.iter_lines():
        raise_if_past_deadline(deadline, timeout, label)
        if not line:
            continue
        take_sse_piece(parts, parse_line(line), on_delta)
        raise_if_past_deadline(deadline, timeout, label)


def require_stream_text(parts: list[str], label: str) -> str:
    content = "".join(parts)
    if not content.strip():
        raise LlmError(f"{label} stream completed with empty content")
    return content
