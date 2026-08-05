"""Review progress / status feedback for the CLI."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import TextIO

from rich.console import Console


@dataclass
class LlmGenerateProgress:
    """Thread-safe counters updated while an LLM stream is in flight."""

    chars: int = 0
    chunks: int = 0
    phase: str = "connecting"  # connecting | generating | done
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def note_delta(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self.chars += len(text)
            self.chunks += 1
            self.phase = "generating"

    def mark_done(self) -> None:
        with self._lock:
            self.phase = "done"

    def summary(self) -> str:
        with self._lock:
            if self.chars <= 0:
                return "stream: waiting for first token (prompt still evaluating)"
            return f"stream: {self.chars:,} chars · {self.chunks} chunk(s) received"


@dataclass
class ReviewProgress:
    """Phase lines (A), verbose details (B), and LLM wait heartbeat (C)."""

    quiet: bool = False
    verbose: bool = False
    heartbeat_seconds: float = 15.0
    console: Console | None = None
    _file: TextIO = field(default_factory=lambda: sys.stderr)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console(file=self._file, quiet=self.quiet)

    def _print(self, message: str) -> None:
        if self.quiet:
            return
        assert self.console is not None
        with self._lock:
            self.console.print(message)

    def phase(self, message: str) -> None:
        self._print(f"[cyan]→[/cyan] {message}")

    def detail(self, message: str) -> None:
        if self.quiet or not self.verbose:
            return
        self._print(f"[dim]  · {message}[/dim]")

    @contextmanager
    def waiting(
        self,
        message: str,
        *,
        hint: str | None = None,
        status_fn: Callable[[], str | None] | None = None,
    ) -> Iterator[None]:
        """Show spinner (TTY) and periodic heartbeat while a long step runs.

        ``hint`` is printed once at start (verbose). Heartbeats prefer live
        ``status_fn`` output (stream chars, Ollama /api/ps) over repeating the
        static hint, so progress lines stay readable.
        """
        if self.quiet:
            yield
            return

        assert self.console is not None
        self.phase(message)
        if hint:
            self.detail(hint)
        stop = threading.Event()
        started = time.monotonic()

        def _heartbeat() -> None:
            interval = max(0.05, float(self.heartbeat_seconds))
            while not stop.wait(interval):
                elapsed = int(time.monotonic() - started)
                extras: list[str] = []
                if status_fn is not None:
                    try:
                        live = status_fn()
                    except Exception:  # noqa: BLE001 — never break wait on status probe
                        live = None
                    if live:
                        extras.append(live)
                elif hint:
                    extras.append(hint)
                suffix = (" — " + " | ".join(extras)) if extras else ""
                self._print(
                    f"[dim]… still waiting ({elapsed}s): {message}{suffix}[/dim]"
                )

        use_heartbeat = float(self.heartbeat_seconds) > 0
        thread: threading.Thread | None = None
        if use_heartbeat:
            thread = threading.Thread(
                target=_heartbeat, name="repolens-heartbeat", daemon=True
            )
            thread.start()
        status_cm = (
            self.console.status(message, spinner="dots")
            if self.console.is_terminal
            else nullcontext()
        )
        try:
            with status_cm:
                yield
        finally:
            stop.set()
            if thread is not None:
                thread.join(timeout=0.2)
            elapsed = int(time.monotonic() - started)
            self.detail(f"finished in {elapsed}s")


def null_progress() -> ReviewProgress:
    """Silent progress reporter for tests / library use."""
    return ReviewProgress(quiet=True)
