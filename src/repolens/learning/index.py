"""SQLite FTS5 keyword index for local learning."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from repolens.inventory import list_files
from repolens.learning.consent import ensure_consent

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class IndexHit:
    path: str
    snippet: str
    rank: float


def index_db_path(root: Path) -> Path:
    return root / ".repolens" / "index.sqlite"


class LearningIndex:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.db_path = index_db_path(self.root)

    def build(self, *, accept: bool = False) -> int:
        ensure_consent(self.root, accept=accept)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE chunks USING fts5(path, content, tokenize='porter')"
            )
            files = list_files(self.root, mode="full")
            count = 0
            for entry in files:
                try:
                    text = entry.path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # Keep chunks modest for FTS
                content = text[:80_000]
                if not content.strip():
                    continue
                conn.execute(
                    "INSERT INTO chunks(path, content) VALUES (?, ?)",
                    (entry.relative, content),
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def query(self, text: str, *, limit: int = 5) -> list[IndexHit]:
        if not self.db_path.is_file():
            return []
        terms = _TOKEN.findall(text.lower())
        if not terms:
            return []
        # OR query; quote tokens for FTS
        match = " OR ".join(f'"{t}"' for t in terms[:12])
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
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
            return [IndexHit(path=r[0], snippet=r[1] or "", rank=float(r[2])) for r in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()


def clear_index(root: Path) -> None:
    path = index_db_path(root.resolve())
    if path.is_file():
        path.unlink()
