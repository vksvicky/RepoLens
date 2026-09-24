"""Near-clone detection (Fast Brain — line/hash only, no AST)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PairHit:
    """Matching window between two files (physical line ranges, inclusive)."""

    file_a: str
    file_b: str
    phys_start_a: int
    phys_end_a: int
    phys_start_b: int
    phys_end_b: int


@dataclass(frozen=True)
class CloneBlock:
    """Coalesced near-clone region for one file pair."""

    file_a: str
    file_b: str
    phys_start_a: int
    phys_end_a: int
    phys_start_b: int
    phys_end_b: int
    occurrences: int


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


def _pair_offset(hit: PairHit) -> int:
    return hit.phys_start_b - hit.phys_start_a


def _can_merge_pair_hits(cur: PairHit, nxt: PairHit) -> bool:
    if cur.file_a != nxt.file_a or cur.file_b != nxt.file_b:
        return False
    if nxt.phys_start_a > cur.phys_end_a + 1:
        return False
    if nxt.phys_start_b > cur.phys_end_b + 1:
        return False
    return _pair_offset(cur) == _pair_offset(nxt)


def _merge_pair_hits(cur: PairHit, nxt: PairHit) -> PairHit:
    return PairHit(
        cur.file_a,
        cur.file_b,
        cur.phys_start_a,
        max(cur.phys_end_a, nxt.phys_end_a),
        cur.phys_start_b,
        max(cur.phys_end_b, nxt.phys_end_b),
    )


def coalesce_pair_hits(hits_a_to_b: list[PairHit]) -> list[CloneBlock]:
    """Merge overlapping/abutting windows with the same A→B line offset."""
    if not hits_a_to_b:
        return []

    sorted_hits = sorted(
        hits_a_to_b,
        key=lambda h: (h.file_a, h.file_b, h.phys_start_a, h.phys_start_b),
    )
    merged: list[tuple[PairHit, int]] = []
    cur = sorted_hits[0]
    count = 1

    for nxt in sorted_hits[1:]:
        if _can_merge_pair_hits(cur, nxt):
            cur = _merge_pair_hits(cur, nxt)
            count += 1
        else:
            merged.append((cur, count))
            cur = nxt
            count = 1
    merged.append((cur, count))

    return [
        CloneBlock(
            h.file_a,
            h.file_b,
            h.phys_start_a,
            h.phys_end_a,
            h.phys_start_b,
            h.phys_end_b,
            occurrences,
        )
        for h, occurrences in merged
    ]
