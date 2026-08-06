"""Near-duplicate finding clustering (Phase 6.9)."""

from __future__ import annotations

import re

from repolens.schema import Issue, Severity

_SEV_RANK = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}

_WS = re.compile(r"\s+")


def _norm_file(path: str) -> str:
    return path.strip().replace("\\", "/").lower().lstrip("./")


def _norm_title(title: str) -> str:
    return _WS.sub(" ", title.strip().lower())


def _cluster_key(issue: Issue) -> tuple[str, str, str]:
    # Prefer CWE when present so "same CWE, same file" collapses.
    identity = (issue.cwe or "").strip().lower() or _norm_title(issue.title)
    return (_norm_file(issue.file), (issue.category or "").strip().lower(), identity)


def cluster_near_duplicates(issues: list[Issue]) -> list[Issue]:
    """Collapse near-duplicates; keep highest severity; set ``clusteredCount``."""
    best: dict[tuple[str, str, str], Issue] = {}
    counts: dict[tuple[str, str, str], int] = {}
    order: list[tuple[str, str, str]] = []

    for issue in issues:
        key = _cluster_key(issue)
        counts[key] = counts.get(key, 0) + 1
        existing = best.get(key)
        if existing is None:
            best[key] = issue
            order.append(key)
            continue
        if _SEV_RANK[issue.severity] > _SEV_RANK[existing.severity]:
            best[key] = issue

    out: list[Issue] = []
    for key in order:
        issue = best[key]
        n = counts[key]
        if n > 1:
            out.append(issue.model_copy(update={"clusteredCount": n}))
        else:
            out.append(issue)
    return out
