"""Adaptive fingerprint sync and timeout recommendations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from repolens.adaptive import (
    fingerprint_rows_from_entries,
    recommend_timeout,
    sync_project_fingerprints,
)
from repolens.config import AdaptiveConfig
from repolens.inventory import FileEntry
from repolens.learning.store import ProjectStore


def _entry(root: Path, name: str, text: str, band: int = 1) -> FileEntry:
    path = root / name
    path.write_text(text, encoding="utf-8")
    st = path.stat()
    return FileEntry(
        path=path,
        relative=name,
        size=st.st_size,
        priority_band=band,
    )


def test_sync_detects_added_changed_deleted(tmp_path: Path) -> None:
    a = _entry(tmp_path, "a.py", "print(1)\n")
    b = _entry(tmp_path, "b.py", "print(2)\n", band=2)
    with ProjectStore(tmp_path) as store:
        diff1 = sync_project_fingerprints(store, [a, b])
    assert set(diff1.added) == {"a.py", "b.py"}

    b.path.write_text("print(2)\nprint(3)\n", encoding="utf-8")
    b2 = FileEntry(
        path=b.path,
        relative="b.py",
        size=b.path.stat().st_size,
        priority_band=2,
    )
    c = _entry(tmp_path, "c.py", "print(9)\n")
    with ProjectStore(tmp_path) as store:
        diff2 = sync_project_fingerprints(store, [a, b2, c])
    assert set(diff2.added) == {"c.py"}
    assert set(diff2.changed) == {"b.py"}
    assert diff2.deleted == []

    with ProjectStore(tmp_path) as store:
        diff3 = sync_project_fingerprints(store, [a, c])
    assert set(diff3.deleted) == {"b.py"}


def test_recommend_timeout_from_history() -> None:
    cfg = AdaptiveConfig(timeout_margin=1.5, min_timeout_seconds=100, max_timeout_seconds=2000)
    # p95 of [10,20,30,40,100] ~ 100 → 150
    assert recommend_timeout([10, 20, 30, 40, 100], adaptive=cfg, file_count=10) == 150.0


def test_recommend_timeout_cold_heuristic() -> None:
    cfg = AdaptiveConfig(min_timeout_seconds=120, max_timeout_seconds=3600)
    cold = recommend_timeout([], adaptive=cfg, file_count=200)
    assert cold >= 120
    assert cold <= 3600


def test_fingerprint_sha_stable(tmp_path: Path) -> None:
    e = _entry(tmp_path, "x.py", "abc\n")
    rows = fingerprint_rows_from_entries([e])
    digest = hashlib.sha256(b"abc\n").hexdigest()
    assert rows[0]["sha256"] == digest
