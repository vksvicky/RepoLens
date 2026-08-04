"""Unified SQLite project store: fingerprints, runs, meta, FTS5 chunks."""

from __future__ import annotations

import shutil
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

LEGACY_INDEX_NAME = "index.sqlite"
STORE_NAME = "repolens.sqlite"


@dataclass(frozen=True)
class FtsHit:
    path: str
    snippet: str
    rank: float


@dataclass(frozen=True)
class FingerprintDiff:
    added: list[str]
    changed: list[str]
    deleted: list[str]
    unchanged: list[str]


def store_db_path(root: Path) -> Path:
    return root.resolve() / ".repolens" / STORE_NAME


def legacy_index_path(root: Path) -> Path:
    return root.resolve() / ".repolens" / LEGACY_INDEX_NAME


class ProjectStore:
    """Always-on fingerprints/metrics; FTS chunks filled only when learning consents."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.db_path = store_db_path(self.root)
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_if_needed()
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> ProjectStore:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ProjectStore is not open")
        return self._conn

    def _migrate_legacy_if_needed(self) -> None:
        legacy = legacy_index_path(self.root)
        if self.db_path.is_file() or not legacy.is_file():
            return
        shutil.copy2(legacy, self.db_path)
        bak = legacy.with_name("index.sqlite.bak")
        if bak.exists():
            bak.unlink()
        legacy.rename(bak)

    def _ensure_schema(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
              path TEXT PRIMARY KEY,
              sha256 TEXT NOT NULL,
              size INTEGER NOT NULL,
              mtime_ns INTEGER NOT NULL,
              priority_band INTEGER NOT NULL DEFAULT 3,
              updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              started_at REAL NOT NULL,
              finished_at REAL,
              mode TEXT,
              provider TEXT,
              model TEXT,
              files_in_prompt INTEGER,
              llm_seconds REAL,
              timeout_used REAL,
              outcome TEXT
            );
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """
        )
        # FTS5 virtual table (idempotent check)
        row = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
        ).fetchone()
        if row is None:
            c.execute(
                "CREATE VIRTUAL TABLE chunks USING fts5(path, content, tokenize='porter')"
            )
        self.set_meta("schema_version", SCHEMA_VERSION)
        c.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def replace_fingerprints(self, rows: Iterable[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM files")
        now = time.time()
        self.conn.executemany(
            "INSERT INTO files(path, sha256, size, mtime_ns, priority_band, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    r["path"],
                    r["sha256"],
                    int(r["size"]),
                    int(r["mtime_ns"]),
                    int(r.get("priority_band", 3)),
                    now,
                )
                for r in rows
            ],
        )
        self.conn.commit()

    def list_fingerprints(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for path, sha, size, mtime_ns, band in self.conn.execute(
            "SELECT path, sha256, size, mtime_ns, priority_band FROM files"
        ):
            out[str(path)] = {
                "path": str(path),
                "sha256": str(sha),
                "size": int(size),
                "mtime_ns": int(mtime_ns),
                "priority_band": int(band),
            }
        return out

    def diff_fingerprints(self, new_rows: Iterable[dict[str, Any]]) -> FingerprintDiff:
        new_map = {r["path"]: r for r in new_rows}
        old = self.list_fingerprints()
        added: list[str] = []
        changed: list[str] = []
        unchanged: list[str] = []
        for path, row in new_map.items():
            if path not in old:
                added.append(path)
            elif old[path]["sha256"] != row["sha256"]:
                changed.append(path)
            else:
                unchanged.append(path)
        deleted = [p for p in old if p not in new_map]
        return FingerprintDiff(
            added=sorted(added),
            changed=sorted(changed),
            deleted=sorted(deleted),
            unchanged=sorted(unchanged),
        )

    def apply_fingerprint_diff(
        self,
        diff: FingerprintDiff,
        new_rows: Iterable[dict[str, Any]],
    ) -> None:
        new_map = {r["path"]: r for r in new_rows}
        now = time.time()
        for path in diff.deleted:
            self.conn.execute("DELETE FROM files WHERE path = ?", (path,))
        for path in list(diff.added) + list(diff.changed):
            r = new_map[path]
            self.conn.execute(
                "INSERT INTO files(path, sha256, size, mtime_ns, priority_band, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET "
                "sha256=excluded.sha256, size=excluded.size, mtime_ns=excluded.mtime_ns, "
                "priority_band=excluded.priority_band, updated_at=excluded.updated_at",
                (
                    r["path"],
                    r["sha256"],
                    int(r["size"]),
                    int(r["mtime_ns"]),
                    int(r.get("priority_band", 3)),
                    now,
                ),
            )
        self.conn.commit()

    def record_run(
        self,
        *,
        started_at: float,
        finished_at: float,
        mode: str,
        provider: str | None,
        model: str | None,
        files_in_prompt: int,
        llm_seconds: float | None,
        timeout_used: float | None,
        outcome: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO runs(started_at, finished_at, mode, provider, model, "
            "files_in_prompt, llm_seconds, timeout_used, outcome) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                started_at,
                finished_at,
                mode,
                provider,
                model,
                files_in_prompt,
                llm_seconds,
                timeout_used,
                outcome,
            ),
        )
        self.conn.commit()

    def successful_llm_seconds(self, *, limit: int = 20) -> list[float]:
        rows = self.conn.execute(
            "SELECT llm_seconds FROM runs "
            "WHERE outcome = 'ok' AND llm_seconds IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [float(r[0]) for r in rows]

    def upsert_chunk(self, path: str, content: str) -> None:
        self.conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
        if content.strip():
            self.conn.execute(
                "INSERT INTO chunks(path, content) VALUES (?, ?)",
                (path, content),
            )
        self.conn.commit()

    def delete_chunk(self, path: str) -> None:
        self.conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
        self.conn.commit()

    def clear_chunks(self) -> None:
        self.conn.execute("DELETE FROM chunks")
        self.conn.commit()

    def query_fts(self, text: str, *, limit: int = 5) -> list[FtsHit]:
        import re

        token = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
        terms = token.findall(text.lower())
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms[:12])
        try:
            rows = self.conn.execute(
                """
                SELECT path, snippet(chunks, 1, '', '', '…', 24) AS snip,
                       bm25(chunks) AS rank
                FROM chunks
                WHERE chunks MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [FtsHit(path=r[0], snippet=r[1] or "", rank=float(r[2])) for r in rows]
