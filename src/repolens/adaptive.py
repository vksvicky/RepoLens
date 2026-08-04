"""Per-project fingerprint sync and timeout recommendations (Phase 5)."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from repolens.config import AdaptiveConfig
from repolens.inventory import FileEntry
from repolens.learning.store import FingerprintDiff, ProjectStore
from repolens.llm import DEFAULT_LLM_TIMEOUT, DEFAULT_OLLAMA_TIMEOUT


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint_rows_from_entries(entries: list[FileEntry]) -> list[dict]:
    rows: list[dict] = []
    for entry in entries:
        try:
            st = entry.path.stat()
            sha = file_sha256(entry.path)
        except OSError:
            continue
        rows.append(
            {
                "path": entry.relative,
                "sha256": sha,
                "size": int(st.st_size),
                "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
                "priority_band": int(entry.priority_band),
            }
        )
    return rows


def sync_project_fingerprints(
    store: ProjectStore,
    entries: list[FileEntry],
) -> FingerprintDiff:
    """Diff inventory against store and apply updates. Returns the diff applied."""
    rows = fingerprint_rows_from_entries(entries)
    diff = store.diff_fingerprints(rows)
    if not store.list_fingerprints():
        store.replace_fingerprints(rows)
        return FingerprintDiff(
            added=sorted(r["path"] for r in rows),
            changed=[],
            deleted=[],
            unchanged=[],
        )
    store.apply_fingerprint_diff(diff, rows)
    return diff


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))
    return ordered[idx]


def cold_start_timeout(file_count: int, *, adaptive: AdaptiveConfig) -> float:
    """Heuristic when no successful run history exists."""
    # ~2s per file in prompt pack, floor/ceil by adaptive bounds
    estimate = max(adaptive.min_timeout_seconds, float(file_count) * 2.0 + 60.0)
    return min(adaptive.max_timeout_seconds, estimate)


def recommend_timeout(
    llm_seconds_history: list[float],
    *,
    adaptive: AdaptiveConfig,
    file_count: int,
) -> float:
    if not llm_seconds_history:
        return cold_start_timeout(file_count, adaptive=adaptive)
    p95 = _percentile(llm_seconds_history, 0.95)
    raw = p95 * float(adaptive.timeout_margin)
    return max(
        adaptive.min_timeout_seconds,
        min(adaptive.max_timeout_seconds, raw),
    )


def resolve_effective_timeout(
    *,
    explicit: float | None,
    recommended: float | None,
    provider: str | None,
    adaptive: AdaptiveConfig,
) -> float:
    """CLI/config explicit wins; else recommended; else provider default."""
    if explicit is not None and explicit > 0:
        return float(explicit)
    if adaptive.enabled and recommended is not None and recommended > 0:
        return float(recommended)
    if provider == "ollama":
        return DEFAULT_OLLAMA_TIMEOUT
    return DEFAULT_LLM_TIMEOUT


def select_pack_paths(
    entries: list[FileEntry],
    diff: FingerprintDiff,
    *,
    mode: str,
) -> list[FileEntry]:
    """Choose which files enter the LLM pack."""
    mode_norm = (mode or "auto").strip().lower()
    if mode_norm == "full":
        return list(entries)
    interesting = set(diff.added) | set(diff.changed)
    # No delta since last sync → keep a full pack (avoid under-reviewing)
    if not interesting and mode_norm != "changed":
        return list(entries)
    if mode_norm == "changed":
        return [e for e in entries if e.relative in interesting]
    # auto: changed/added + all P1-band
    return [
        e
        for e in entries
        if e.relative in interesting or e.priority_band <= 1
    ]
