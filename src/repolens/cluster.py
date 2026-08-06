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

# Higher wins severity ties: scanner > llm > heuristic.
_SOURCE_RANK = {"scanner": 3, "llm": 2, "heuristic": 1}

_THEME_FAMILY = {
    "heuristic.gitignore_secrets": "secrets_hygiene",
    "sec.repo_hygiene_secrets": "secrets_hygiene",
    "heuristic.scripts_hygiene": "secrets_hygiene",
    "heuristic.mega_file": "structure_size",
    "arch.structure_size": "structure_size",
    "heuristic.sibling_duplication": "duplication",
    "arch.duplication": "duplication",
    "heuristic.deep_nesting": "readability",
    "arch.readability_complexity": "readability",
}

_WS = re.compile(r"\s+")


def _norm_file(path: str) -> str:
    return path.strip().replace("\\", "/").lower().lstrip("./")


def _norm_title(title: str) -> str:
    return _WS.sub(" ", title.strip().lower())


def _theme_family(category: str) -> str:
    c = (category or "").strip().lower()
    return _THEME_FAMILY.get(c, c)


def _cluster_key(issue: Issue) -> tuple[str, str, str]:
    identity = (issue.cwe or "").strip().lower()
    if not identity:
        # Same file + theme family collapses heuristic/LLM twins even if titles differ slightly
        identity = _theme_family(issue.category) or _norm_title(issue.title)
    return (_norm_file(issue.file), _theme_family(issue.category), identity)


def _prefer(candidate: Issue, existing: Issue) -> bool:
    """True if candidate should replace existing (higher severity, then source rank)."""
    cand_sev = _SEV_RANK[candidate.severity]
    exist_sev = _SEV_RANK[existing.severity]
    if cand_sev != exist_sev:
        return cand_sev > exist_sev
    cand_src = _SOURCE_RANK.get((candidate.source or "").strip().lower(), 0)
    exist_src = _SOURCE_RANK.get((existing.source or "").strip().lower(), 0)
    return cand_src > exist_src


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
        if _prefer(issue, existing):
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
