"""SQLite FTS5 keyword index for local learning (unified ProjectStore)."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import list_files
from repolens.learning.consent import ensure_consent
from repolens.learning.store import (
    FtsHit,
    ProjectStore,
    legacy_index_path,
    store_db_path,
)

# Back-compat alias for tests / callers
IndexHit = FtsHit


def index_db_path(root: Path) -> Path:
    """Preferred unified DB path (may migrate legacy index.sqlite on open)."""
    return store_db_path(root)


class LearningIndex:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.db_path = store_db_path(self.root)

    def build(self, *, accept: bool = False) -> int:
        ensure_consent(self.root, accept=accept)
        with ProjectStore(self.root) as store:
            store.clear_chunks()
            files = list_files(self.root, mode="full")
            count = 0
            for entry in files:
                try:
                    text = entry.path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                content = text[:80_000]
                if not content.strip():
                    continue
                store.upsert_chunk(entry.relative, content)
                count += 1
            return count

    def query(self, text: str, *, limit: int = 5) -> list[FtsHit]:
        if not self.db_path.is_file() and not legacy_index_path(self.root).is_file():
            return []
        with ProjectStore(self.root) as store:
            return store.query_fts(text, limit=limit)


def clear_index(root: Path) -> None:
    """Remove FTS chunks; keep fingerprint/runs tables if the unified DB exists."""
    root = root.resolve()
    unified = store_db_path(root)
    legacy = legacy_index_path(root)
    bak = legacy.with_name("index.sqlite.bak")
    if unified.is_file():
        with ProjectStore(root) as store:
            store.clear_chunks()
        return
    for path in (legacy, bak):
        if path.is_file():
            path.unlink()
