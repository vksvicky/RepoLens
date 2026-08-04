"""Unified ProjectStore — fingerprints + FTS5 schema + legacy migrate."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from repolens.learning.store import ProjectStore, store_db_path


def test_store_path(tmp_path: Path) -> None:
    assert store_db_path(tmp_path) == tmp_path / ".repolens" / "repolens.sqlite"


def test_open_creates_schema(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.open()
    db = store_db_path(tmp_path)
    assert db.is_file()
    conn = sqlite3.connect(db)
    try:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
            )
        }
    finally:
        conn.close()
    assert "files" in tables
    assert "runs" in tables
    assert "meta" in tables
    assert "chunks" in tables
    store.close()


def test_upsert_and_diff_files(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.open()
    store.replace_fingerprints(
        [
            {"path": "a.py", "sha256": "aaa", "size": 10, "mtime_ns": 1, "priority_band": 1},
            {"path": "b.py", "sha256": "bbb", "size": 20, "mtime_ns": 2, "priority_band": 2},
        ]
    )
    diff = store.diff_fingerprints(
        [
            {"path": "a.py", "sha256": "aaa", "size": 10, "mtime_ns": 1, "priority_band": 1},
            {"path": "c.py", "sha256": "ccc", "size": 30, "mtime_ns": 3, "priority_band": 1},
            {"path": "b.py", "sha256": "BBB", "size": 21, "mtime_ns": 4, "priority_band": 2},
        ]
    )
    assert set(diff.added) == {"c.py"}
    assert set(diff.changed) == {"b.py"}
    assert set(diff.deleted) == set()  # diff vs current inventory — deleted = in DB not in new
    # deleted relative to previous DB after applying new set:
    store.apply_fingerprint_diff(diff, new_rows=[
        {"path": "a.py", "sha256": "aaa", "size": 10, "mtime_ns": 1, "priority_band": 1},
        {"path": "c.py", "sha256": "ccc", "size": 30, "mtime_ns": 3, "priority_band": 1},
        {"path": "b.py", "sha256": "BBB", "size": 21, "mtime_ns": 4, "priority_band": 2},
    ])
    # Remove b from inventory → deleted
    diff2 = store.diff_fingerprints(
        [
            {"path": "a.py", "sha256": "aaa", "size": 10, "mtime_ns": 1, "priority_band": 1},
            {"path": "c.py", "sha256": "ccc", "size": 30, "mtime_ns": 3, "priority_band": 1},
        ]
    )
    assert set(diff2.deleted) == {"b.py"}
    store.close()


def test_migrate_legacy_index_sqlite(tmp_path: Path) -> None:
    legacy = tmp_path / ".repolens" / "index.sqlite"
    legacy.parent.mkdir(parents=True)
    conn = sqlite3.connect(legacy)
    conn.execute(
        "CREATE VIRTUAL TABLE chunks USING fts5(path, content, tokenize='porter')"
    )
    conn.execute(
        "INSERT INTO chunks(path, content) VALUES (?, ?)",
        ("legacy.py", "def hello_world(): pass"),
    )
    conn.commit()
    conn.close()

    store = ProjectStore(tmp_path)
    store.open()
    assert store_db_path(tmp_path).is_file()
    hits = store.query_fts("hello_world", limit=5)
    assert hits
    assert hits[0].path == "legacy.py"
    assert not legacy.is_file()
    assert legacy.with_name("index.sqlite.bak").is_file()
    store.close()


def test_meta_recommended_timeout(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.open()
    assert store.get_meta("recommended_timeout_seconds") is None
    store.set_meta("recommended_timeout_seconds", "900")
    assert store.get_meta("recommended_timeout_seconds") == "900"
    store.close()
