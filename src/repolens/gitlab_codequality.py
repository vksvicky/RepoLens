"""GitLab merge-request code-quality JSON for one FindingReport.

Scanner, heuristic, graph, and architecture rows with a safe path and line
are included. An LLM row is included only when its location was verified.
The widget object is the title, category, fingerprint, severity, and line.
"""

from __future__ import annotations

import json
from pathlib import Path

from repolens.issue_ids import stable_id
from repolens.schema import FindingReport, Issue, Severity

GITLAB_CODEQUALITY_NAME = "gl-code-quality-report.json"

_SEVERITY = {
    Severity.CRITICAL: "critical",
    Severity.HIGH: "major",
    Severity.MEDIUM: "minor",
    Severity.LOW: "info",
}
_TRUSTED_SOURCES = frozenset({"scanner", "heuristic", "graph", "architecture"})


def _export_path(file: str) -> str | None:
    raw = file.strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("~"):
        return None
    if len(raw) >= 2 and raw[1] == ":":
        return None
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _counts_as_trusted(issue: Issue) -> bool:
    if issue.source in _TRUSTED_SOURCES:
        return True
    if issue.source is None and issue.category.startswith("heuristic."):
        return True
    return issue.source == "llm" and issue.locationVerified is True


def gitlab_codequality_payload(report: FindingReport) -> list[dict]:
    """Map included findings to GitLab's code-quality array."""
    rows: list[dict] = []
    for issue in report.issues:
        path = _export_path(issue.file)
        if path is None or issue.line < 1 or not _counts_as_trusted(issue):
            continue
        fingerprint = issue.stableId or stable_id(
            category=issue.category,
            file=issue.file,
            title=issue.title,
        )
        rows.append({
            "description": issue.title,
            "check_name": issue.category,
            "fingerprint": fingerprint,
            "severity": _SEVERITY[issue.severity],
            "location": {"path": path, "lines": {"begin": issue.line}},
        })
    return rows


def write_gitlab_codequality(report: FindingReport, dest: Path) -> Path:
    """Write the code-quality array. The same report always produces the same bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(gitlab_codequality_payload(report), indent=2) + "\n"
    dest.write_text(text, encoding="utf-8")
    return dest
