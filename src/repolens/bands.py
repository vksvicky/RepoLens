"""Priority / band coercion for post-merge findings.

MVP rules (Phase 5.1):
1. ``heuristic.*`` categories are capped at P2 (P1 → P2).
2. Other P1 findings are demoted to P2 unless the category is clearly
   security-related: starts with ``sec.`` or ``security``, or is / contains
   a scanner tool name (``gitleaks``, ``semgrep``, ``osv``).

True ``sec.practice_review`` P1 stays. Band coercion changes priority only;
severity and the finding itself are preserved.
"""

from __future__ import annotations

from repolens.schema import Issue

_SCANNER_MARKERS = ("gitleaks", "semgrep", "osv")


def _is_security_category(category: str) -> bool:
    cat = category.strip().lower()
    if cat.startswith(("sec.", "security")):
        return True
    if cat in _SCANNER_MARKERS:
        return True
    return any(marker in cat for marker in _SCANNER_MARKERS)


def coerce_issue_bands(issues: list[Issue]) -> list[Issue]:
    """Return issues with non-security / heuristic P1 priorities coerced to P2."""
    out: list[Issue] = []
    for issue in issues:
        priority = issue.priority
        category = issue.category
        if category.startswith("heuristic.") and priority == "P1":
            out.append(issue.model_copy(update={"priority": "P2"}))
            continue
        if priority == "P1" and not _is_security_category(category):
            out.append(issue.model_copy(update={"priority": "P2"}))
            continue
        out.append(issue)
    return out
