"""First Ctrl+C unwinds the review. The second one exits immediately."""

from __future__ import annotations

import signal
import sys
import threading
from typing import Any


class InterruptGuard:
    def __init__(self) -> None:
        self._hits = 0
        self._previous: Any = None

    def handle(self, _signum: int, _frame: object) -> None:
        self._hits += 1
        if self._hits >= 2:
            sys.exit(1)
        raise KeyboardInterrupt

    def __enter__(self) -> InterruptGuard:
        if threading.current_thread() is threading.main_thread():
            self._previous = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self.handle)
        return self

    def __exit__(self, *args: object) -> None:
        if self._previous is not None:
            signal.signal(signal.SIGINT, self._previous)
            self._previous = None
