"""Near-clone detection (Fast Brain — line/hash only, no AST)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowHit:
    """One sliding-window content hash with physical and normalised line bounds."""

    hash: str
    phys_start: int
    phys_end: int
    norm_start: int
    norm_end: int


def normalize_lines(text: str) -> tuple[list[str], list[int]]:
    """Drop blank lines; map each kept line to its 1-based physical line number."""
    norm: list[str] = []
    phys: list[int] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        norm.append(raw.lstrip())
        phys.append(i)
    return norm, phys


def window_hash(lines: Sequence[str]) -> str:
    """Stable truncated SHA-256 of normalised window text."""
    payload = "\n".join(lines).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def iter_windows(
    norm: list[str],
    phys: list[int],
    *,
    window: int,
    stride: int,
) -> Iterator[WindowHit]:
    """Yield sliding windows over normalised lines with physical line bounds."""
    if len(norm) != len(phys):
        msg = "norm and phys must have the same length"
        raise ValueError(msg)
    if window <= 0 or stride <= 0:
        msg = "window and stride must be positive"
        raise ValueError(msg)
    if len(norm) < window:
        return
    for start in range(0, len(norm) - window + 1, stride):
        end = start + window
        chunk = norm[start:end]
        yield WindowHit(
            hash=window_hash(chunk),
            phys_start=phys[start],
            phys_end=phys[end - 1],
            norm_start=start,
            norm_end=end,
        )
