"""Retrieve local context for the LLM prompt pack."""

from __future__ import annotations

from pathlib import Path

from repolens.learning.index import LearningIndex

# Optional embeddings path — only when repolens[local-ml] is installed.
try:
    from repolens.learning.embeddings import enhance_query  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - optional extra

    def enhance_query(text: str) -> str:
        return text


def retrieve_context(root: Path, query: str, *, limit: int = 5) -> str:
    """Return a markdown block of related local chunks (may be empty)."""
    idx = LearningIndex(root)
    hits = idx.query(enhance_query(query), limit=limit)
    if not hits:
        return ""
    lines = ["## Local learning context (on-disk index)", ""]
    for hit in hits:
        lines.append(f"### {hit.path}")
        lines.append("```")
        lines.append(hit.snippet.strip() or "(no snippet)")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
