"""Fast Brain worker count. ``0`` means leave one core free, capped at eight."""

from __future__ import annotations

import os


def resolve_fast_brain_workers(configured: int, *, cpu_count: int | None = None) -> int:
    if configured > 0:
        return configured
    available = os.cpu_count() if cpu_count is None else cpu_count
    cores = available or 1
    return min(8, max(1, cores - 1))
