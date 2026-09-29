"""Shared SSE helpers for provider streams.

The prefill budget waits for the first token. After that, only a stretch of
silence aborts the stream. A long run that keeps producing tokens finishes.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from repolens.llm.errors import LlmError

DEFAULT_SILENCE_TIMEOUT = 300.0


class StreamWatch:
    """Prefill budget until the first token, then an inactivity limit."""

    def __init__(
        self,
        *,
        prefill_timeout: float,
        silence_timeout: float = DEFAULT_SILENCE_TIMEOUT,
        label: str = "LLM",
    ) -> None:
        self.prefill_timeout = max(0.0, float(prefill_timeout))
        self.silence_timeout = max(0.0, float(silence_timeout))
        self.label = label
        self.started = time.monotonic()
        self.last_token: float | None = None

    def note_token(self) -> None:
        self.last_token = time.monotonic()

    def check(self) -> None:
        now = time.monotonic()
        if self.last_token is None:
            if now - self.started >= self.prefill_timeout:
                raise LlmError(
                    f"{self.label} timed out after {self.prefill_timeout:g}s "
                    "waiting for the first token"
                )
            return
        if now - self.last_token >= self.silence_timeout:
            raise LlmError(
                f"{self.label} stream went silent for {self.silence_timeout:g}s"
            )


def timeout_message(label: str, timeout: float) -> str:
    return (
        f"{label} timed out after {timeout:g}s waiting for the first token. "
        "Finished passes are kept. Re-run when the local model is free."
    )


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
    watch: StreamWatch,
    on_delta: Callable[[str], None] | None,
) -> None:
    for line in response.iter_lines():
        watch.check()
        if not line:
            continue
        piece = parse_line(line)
        take_sse_piece(parts, piece, on_delta)
        if piece:
            watch.note_token()


def require_stream_text(parts: list[str], label: str) -> str:
    content = "".join(parts)
    if not content.strip():
        raise LlmError(f"{label} stream completed with empty content")
    return content
