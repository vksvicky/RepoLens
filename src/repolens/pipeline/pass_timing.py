"""Per-pass queue, first-token, and generation times. No tokenizer."""

from __future__ import annotations

import time
from contextvars import ContextVar, Token
from pathlib import Path

from repolens.pipeline.journal import read_events
from repolens.schema import PassTiming

_rows: ContextVar[list[PassTiming] | None] = ContextVar("repolens_pass_timings", default=None)


class StreamClock:
    """Request start, first chunk, and stream end. A missing chunk stays empty."""

    def __init__(self) -> None:
        self.started: float | None = None
        self.first: float | None = None
        self.ended: float | None = None

    def start(self) -> None:
        self.started = time.perf_counter()

    def note_chunk(self, text: str) -> None:
        if text and self.first is None:
            self.first = time.perf_counter()

    def finish(self) -> None:
        self.ended = time.perf_counter()

    def time_to_first_token(self) -> float | None:
        if self.started is None or self.first is None:
            return None
        return round(self.first - self.started, 1)

    def generation_seconds(self) -> float | None:
        if self.first is None or self.ended is None:
            return None
        return round(self.ended - self.first, 1)


def live_pass_timing(
    pass_name: str,
    *,
    queue_wait_seconds: float,
    prompt_chars: int,
    raw_text: str,
    clock: StreamClock,
    token_count: int | None = None,
) -> PassTiming:
    output_chars = len(raw_text)
    generation = clock.generation_seconds()
    rate = None
    if generation is not None and generation > 0:
        rate = round(output_chars / generation, 1)
    return PassTiming(
        passName=pass_name,
        outcome="live",
        queueWaitSeconds=queue_wait_seconds,
        timeToFirstTokenSeconds=clock.time_to_first_token(),
        generationSeconds=generation,
        promptChars=prompt_chars,
        outputChars=output_chars,
        charsPerSecond=rate,
        tokenCount=token_count,
    )


def resumed_pass_timing(pass_name: str) -> PassTiming:
    """A cache hit has no generation numbers. Empty, not zero."""
    return PassTiming(passName=pass_name, outcome="resumed")


def format_pass_timing(row: PassTiming) -> str:
    if row.outcome != "live":
        return f"- **Pass {row.passName}**: {row.outcome}"
    bits = [row.outcome]
    if row.queueWaitSeconds is not None:
        bits.append(f"queue {row.queueWaitSeconds:.1f}s")
    if row.timeToFirstTokenSeconds is not None:
        bits.append(f"first token {row.timeToFirstTokenSeconds:.1f}s")
    if row.generationSeconds is not None:
        bits.append(f"generation {row.generationSeconds:.1f}s")
    if row.charsPerSecond is not None:
        bits.append(f"{row.charsPerSecond:.1f} chars/s")
    return f"- **Pass {row.passName}**: " + " · ".join(bits)


def open_pass_timings() -> Token[list[PassTiming] | None]:
    return _rows.set([])


def close_pass_timings(token: Token[list[PassTiming] | None]) -> list[PassTiming]:
    found = list(_rows.get() or [])
    _rows.reset(token)
    return found


def record_pass_timing(row: PassTiming) -> None:
    bucket = _rows.get()
    if bucket is not None:
        bucket.append(row)


def last_first_token_seconds(root: Path, model: str) -> float | None:
    """Last live first-token sample for this model on this tree."""
    if not model:
        return None
    found: float | None = None
    for row in read_events(root):
        if row.get("event") != "pass_completed" or row.get("resumed"):
            continue
        if str(row.get("model") or "") != model:
            continue
        sample = row.get("time_to_first_token_seconds")
        if sample is None:
            continue
        found = float(sample)
    return found


def with_first_token_sample(root: Path, model: str, coarse: str, *, passes: int) -> str:
    sample = last_first_token_seconds(root, model)
    if sample is None:
        return f"{coarse} No first-token sample on this tree yet."
    ahead = sample * passes
    return (
        f"{coarse} Last first token for {model} on this tree was {sample:.1f}s"
        f" × {passes} pass(es) → ~{ahead:.1f}s before generation."
    )
