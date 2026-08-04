"""Coverage matrix loading and evaluation against FindingReport gaps/issues."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from repolens.schema import Issue

_COVERAGE_NA_RE = re.compile(
    r"^coverage:(?P<id>[^\s:]+)\s*:\s*N/A\s*[—\-]\s*(?P<reason>.+)$",
    re.IGNORECASE,
)

_PASS_TO_BAND = {
    "p1": "p1",
    "security": "p1",
    "p2": "p2",
    "reliability": "p2",
    "p3": "p3",
    "architecture": "p3",
}


@dataclass(frozen=True)
class CoverageEntry:
    id: str
    rule_id: str
    band: str
    full_audit_only: bool
    title: str
    playbook_anchor: str | None = None


@dataclass(frozen=True)
class CoverageMatrix:
    entries: list[CoverageEntry]


@dataclass
class CoverageResult:
    covered: list[str] = field(default_factory=list)
    na: dict[str, str] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)


def _defaults_coverage_path() -> Path:
    try:
        root = resources.files("repolens.rules") / "defaults"
        candidate = root / "coverage.json"
        if candidate.is_file():
            return Path(str(candidate))
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass

    here = Path(__file__).resolve().parent / "rules" / "defaults" / "coverage.json"
    if here.is_file():
        return here
    raise FileNotFoundError("Could not locate rules defaults coverage.json")


def load_coverage_matrix() -> CoverageMatrix:
    path = _defaults_coverage_path()
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    entries_raw = raw.get("entries", [])
    if not isinstance(entries_raw, list):
        raise ValueError("coverage.json entries must be a list")

    entries: list[CoverageEntry] = []
    for item in entries_raw:
        if not isinstance(item, dict):
            continue
        cov_id = item.get("id")
        rule_id = item.get("rule_id")
        if not isinstance(cov_id, str) or not isinstance(rule_id, str):
            raise ValueError(f"coverage entry missing id/rule_id: {item!r}")
        band = str(item.get("band", "p3")).lower()
        title = str(item.get("title", cov_id))
        full_audit_only = bool(item.get("full_audit_only", False))
        anchor = item.get("playbook_anchor")
        if anchor is not None and not isinstance(anchor, str):
            raise ValueError(f"coverage {cov_id}: playbook_anchor must be string or null")
        entries.append(
            CoverageEntry(
                id=cov_id,
                rule_id=rule_id,
                band=band,
                full_audit_only=full_audit_only,
                title=title,
                playbook_anchor=anchor,
            )
        )
    return CoverageMatrix(entries=entries)


def coverage_ids_for_pass(
    pass_id: str,
    *,
    full_audit: bool,
    enabled_rule_ids: Iterable[str],
) -> list[str]:
    band = _PASS_TO_BAND.get(pass_id.lower())
    if band is None:
        raise ValueError(f"Unknown pass_id: {pass_id}")

    enabled = set(enabled_rule_ids)
    matrix = load_coverage_matrix()
    selected: list[str] = []
    for entry in matrix.entries:
        if entry.band != band:
            continue
        if entry.rule_id not in enabled:
            continue
        if entry.full_audit_only and not full_audit:
            continue
        selected.append(entry.id)
    return selected


def parse_coverage_notes(gaps: Iterable[str]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for gap in gaps:
        text = gap.strip()
        match = _COVERAGE_NA_RE.match(text)
        if match:
            notes[match.group("id")] = match.group("reason").strip()
    return notes


def _issue_addresses(cov_id: str, issues: Iterable[Issue]) -> bool:
    """Best-effort link: coverage id or trailing token appears in issue text."""
    token = cov_id.split(".")[-1].lower()
    needle = cov_id.lower()
    for issue in issues:
        hay = " ".join(
            [
                issue.title,
                issue.explanation,
                issue.category,
                issue.impact,
                issue.recommendedFix,
            ]
        ).lower()
        if needle in hay or (token and token in hay):
            return True
    return False


def evaluate_coverage(
    ids: Iterable[str],
    issues: Iterable[Issue],
    gaps: Iterable[str],
) -> CoverageResult:
    wanted = list(ids)
    na = parse_coverage_notes(gaps)
    issue_list = list(issues)
    covered: list[str] = []
    missed: list[str] = []
    result_na: dict[str, str] = {}

    for cov_id in wanted:
        if cov_id in na:
            result_na[cov_id] = na[cov_id]
            continue
        if _issue_addresses(cov_id, issue_list):
            covered.append(cov_id)
        else:
            missed.append(cov_id)

    return CoverageResult(covered=covered, na=result_na, missed=missed)
