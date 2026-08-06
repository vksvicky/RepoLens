"""Hybrid issue identity: stableId (UUID v5) + runId (UUID v4)."""

from __future__ import annotations

import uuid

from repolens.schema import Issue

# Fixed namespace for RepoLens stable finding IDs (do not change).
_REPOLENS_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_STABLE_NAME_PREFIX = "repolens.issue.v1"


def _normalize_file(path: str) -> str:
    return path.strip().replace("\\", "/").lower()


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def stable_id(*, category: str, file: str, title: str) -> str:
    """Deterministic UUID v5 from normalized (category, file, title)."""
    key = "|".join(
        [
            _STABLE_NAME_PREFIX,
            _normalize_text(category).lower(),
            _normalize_file(file),
            _normalize_text(title),
        ]
    )
    return str(uuid.uuid5(_REPOLENS_NAMESPACE, key))


def new_run_id() -> str:
    """Unique UUID v4 for one finding row in a report."""
    return str(uuid.uuid4())


def stamp_issue_ids(issues: list[Issue]) -> list[Issue]:
    """Ensure every issue has stableId + a fresh runId for this report row."""
    out: list[Issue] = []
    for issue in issues:
        sid = issue.stableId or stable_id(
            category=issue.category,
            file=issue.file,
            title=issue.title,
        )
        out.append(
            issue.model_copy(
                update={
                    "stableId": sid,
                    "runId": new_run_id(),
                }
            )
        )
    return out
