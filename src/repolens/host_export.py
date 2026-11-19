"""Which findings a host widget may publish. No network."""

from __future__ import annotations

from repolens.schema import Issue

_TRUSTED_SOURCES = frozenset({"scanner", "heuristic", "graph", "architecture"})


def export_path(file: str) -> str | None:
    """Safe relative path, or None. Slashes are normalized. ``..`` is dropped."""
    raw = file.strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("~"):
        return None
    if len(raw) >= 2 and raw[1] == ":":
        return None
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def counts_as_trusted(issue: Issue) -> bool:
    """Scanner, Fast Brain, graph, and architecture. LLM only when verified."""
    if issue.source in _TRUSTED_SOURCES:
        return True
    if issue.source is None and issue.category.startswith("heuristic."):
        return True
    return issue.source == "llm" and issue.locationVerified is True
