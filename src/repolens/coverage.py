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
    pack: str = "core"  # core | extended | meta


@dataclass(frozen=True)
class CoverageMatrix:
    entries: list[CoverageEntry]


@dataclass
class CoverageResult:
    covered: list[str] = field(default_factory=list)
    na: dict[str, str] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    invalid_na: dict[str, str] = field(default_factory=dict)


# Always-invalid N/A phrases (case-insensitive substring match).
_ALWAYS_LAZY_NA_PHRASES = (
    "not reviewed",
    "not explicitly reviewed",
    "not addressed in this document",
)

# Soft-lazy phrases: invalid unless a concrete out-of-scope justification is present.
_SOFT_LAZY_NA_PHRASES = (
    "could be improved",
    "partially addressed",
)

# Signals that a reason is a concrete out-of-scope justification (valid N/A).
_CONCRETE_NA_MARKERS = (
    "no http",
    "no html",
    "no sql",
    "no orm",
    "no network",
    "not present",
    "out of scope",
    "n/a for",
    "in pack",
    "in provided",
    "in reviewed",
    "desktop app",
)


def is_lazy_na_reason(reason: str) -> bool:
    """Return True when an N/A reason is lazy/invalid rather than concrete out-of-scope.

    Heuristics (spec §4): "not reviewed" / "not addressed in this document" are always
    lazy; "could be improved" / "partially addressed" are lazy without a concrete
    out-of-scope reason (e.g. no HTTP surface).
    """
    text = reason.strip().lower()
    if not text:
        return True

    if any(phrase in text for phrase in _ALWAYS_LAZY_NA_PHRASES):
        return True

    if any(phrase in text for phrase in _SOFT_LAZY_NA_PHRASES):
        has_concrete = any(marker in text for marker in _CONCRETE_NA_MARKERS)
        return not has_concrete

    return False


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
        pack = str(item.get("pack", "core")).lower()
        if pack not in {"core", "extended", "meta"}:
            raise ValueError(f"coverage {cov_id}: pack must be core|extended|meta")
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
                pack=pack,
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
    """Best-effort link: theme/heuristic map, coverage id, or token in issue text."""
    from repolens.themes import canonicalize_coverage_id, theme_id_for_category

    canon = canonicalize_coverage_id(cov_id)
    token = canon.split(".")[-1].lower()
    needle = canon.lower()
    for issue in issues:
        mapped = theme_id_for_category(issue.category)
        if mapped == canon:
            return True
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
    from repolens.themes import canonicalize_coverage_id

    wanted: list[str] = []
    seen: set[str] = set()
    for raw_id in ids:
        cov_id = canonicalize_coverage_id(raw_id)
        if cov_id in seen:
            continue
        seen.add(cov_id)
        wanted.append(cov_id)

    na_raw = parse_coverage_notes(gaps)
    na = {
        canonicalize_coverage_id(cid): reason for cid, reason in na_raw.items()
    }
    issue_list = list(issues)
    covered: list[str] = []
    missed: list[str] = []
    result_na: dict[str, str] = {}
    invalid_na: dict[str, str] = {}

    for cov_id in wanted:
        # Issues win over N/A when evidence exists (alias notes must not hide findings).
        if _issue_addresses(cov_id, issue_list):
            covered.append(cov_id)
            continue
        if cov_id in na:
            reason = na[cov_id]
            if is_lazy_na_reason(reason):
                missed.append(cov_id)
                invalid_na[cov_id] = reason
            else:
                result_na[cov_id] = reason
            continue
        missed.append(cov_id)

    return CoverageResult(
        covered=covered, na=result_na, missed=missed, invalid_na=invalid_na
    )
