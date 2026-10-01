"""Compare two FindingReport JSON files for drift (diff-audit)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from repolens.schema import FindingReport, Issue


@dataclass
class DiffAuditResult:
    left: str
    right: str
    resolved: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    unchanged: int = 0
    left_confidence: int = 0
    right_confidence: int = 0
    confidence_delta: int = 0
    notes: list[str] = field(default_factory=list)


def _issue_key(issue: Issue) -> str:
    return f"{issue.file}:{issue.line}:{issue.title}"


def diff_audit_reports(left: FindingReport, right: FindingReport) -> DiffAuditResult:
    left_map = {_issue_key(i): i for i in left.issues}
    right_map = {_issue_key(i): i for i in right.issues}
    left_keys = set(left_map)
    right_keys = set(right_map)
    resolved = sorted(left_keys - right_keys)
    new = sorted(right_keys - left_keys)
    unchanged = len(left_keys & right_keys)
    notes: list[str] = []
    if left.graph and right.graph:
        lc = left.graph.cyclicity
        rc = right.graph.cyclicity
        if lc != rc:
            notes.append(f"cyclicity drift: {lc} → {rc}")
    return DiffAuditResult(
        left="",
        right="",
        resolved=resolved,
        new=new,
        unchanged=unchanged,
        left_confidence=int(left.confidence),
        right_confidence=int(right.confidence),
        confidence_delta=int(right.confidence) - int(left.confidence),
        notes=notes,
    )


def load_report(path: Path) -> FindingReport:
    return FindingReport.model_validate_json(path.read_text(encoding="utf-8"))


def diff_audit_files(left_path: Path, right_path: Path) -> DiffAuditResult:
    result = diff_audit_reports(load_report(left_path), load_report(right_path))
    result.left = str(left_path)
    result.right = str(right_path)
    return result


def diff_audit_as_dict(result: DiffAuditResult) -> dict:
    return asdict(result)
