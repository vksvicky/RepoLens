"""Local learning: consent, index, memory, retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.learning.consent import (
    CONSENT_NOTICE,
    accept_local_learning,
    ensure_consent,
    has_consent,
)
from repolens.learning.index import LearningIndex, clear_index
from repolens.learning.memory import LearningMemory
from repolens.learning.retrieve import retrieve_context


def test_consent_notice_mentions_local_and_cloud() -> None:
    assert "local" in CONSENT_NOTICE.lower()
    assert "cloud" in CONSENT_NOTICE.lower() or "provider" in CONSENT_NOTICE.lower()


def test_consent_gate(tmp_path: Path) -> None:
    root = tmp_path
    assert has_consent(root) is False
    with pytest.raises(PermissionError, match="consent"):
        ensure_consent(root, accept=False)
    accept_local_learning(root)
    assert has_consent(root) is True
    ensure_consent(root, accept=False)  # already consented


def test_index_build_and_retrieve(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def authenticate_user(token):\n    verify_jwt(token)\n",
        encoding="utf-8",
    )
    (tmp_path / "readme.md").write_text("# hello\n", encoding="utf-8")
    accept_local_learning(tmp_path)
    idx = LearningIndex(tmp_path)
    n = idx.build()
    assert n >= 1
    hits = idx.query("authenticate jwt", limit=3)
    assert hits
    assert any("app.py" in h.path for h in hits)
    block = retrieve_context(tmp_path, "jwt auth", limit=2)
    assert "app.py" in block
    clear_index(tmp_path)
    assert idx.query("authenticate jwt", limit=3) == []
    # Unified DB may remain (fingerprints/runs); FTS chunks cleared
    assert (tmp_path / ".repolens" / "repolens.sqlite").is_file()


def test_memory_roundtrip(tmp_path: Path) -> None:
    mem = LearningMemory(tmp_path)
    mem.dismiss("issue-1")
    mem.add_ignore("vendor/**")
    mem.save()
    loaded = LearningMemory(tmp_path)
    assert "issue-1" in loaded.dismissed
    assert "vendor/**" in loaded.ignore_paths
