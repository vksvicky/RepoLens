"""Optional embedding helpers (requires ``repolens[local-ml]``)."""

from __future__ import annotations


def embeddings_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def enhance_query(text: str) -> str:
    """Pass-through for keyword FTS; embeddings can expand query later.

    Full vector retrieval can land when a project opts into [local-ml] and
    rebuilds the index with embedding columns. Keyword FTS remains the default.
    """
    return text
