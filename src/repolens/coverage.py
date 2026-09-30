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
# The model often drops the coverage: prefix. Same id and N/A marker still counts.
_BARE_NA_RE = re.compile(
    r"^(?P<id>(?:sec|rel|arch)\.[^\s:]+)\s*:\s*N/A\s*[—\-]\s*(?P<reason>.+)$",
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
    covered_notes: dict[str, str] = field(default_factory=dict)
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
    """Map checklist id → N/A reason.

    A later lazy reason does not replace an earlier concrete one.
    """
    notes: dict[str, str] = {}
    for gap in gaps:
        text = gap.strip()
        match = _COVERAGE_NA_RE.match(text) or _BARE_NA_RE.match(text)
        if not match:
            continue
        cid = match.group("id")
        reason = match.group("reason").strip()
        previous = notes.get(cid)
        if previous is None or (
            is_lazy_na_reason(previous) and not is_lazy_na_reason(reason)
        ):
            notes[cid] = reason
        elif is_lazy_na_reason(previous) and is_lazy_na_reason(reason):
            notes[cid] = reason
    return notes


_BAND_PASS = {
    "sec.": ("p1", "security"),
    "rel.": ("p2", "reliability"),
    "arch.": ("p3", "architecture"),
}

_FIX_POINTER = (
    "Findings under P1, P2, and P3 are the changes that make the product "
    "more secure and stable."
)


def checklist_title(cid: str) -> str:
    """Human title for a checklist id. Unknown ids stay as the id."""
    for entry in load_coverage_matrix().entries:
        if entry.id == cid:
            return entry.title
    return cid


def _question_label(cid: str) -> str:
    title = checklist_title(cid)
    if title == cid:
        return cid
    return f"{title} ({cid})"


def _timed_out_band(cid: str, gaps: Iterable[str]) -> str | None:
    for prefix, (band, name) in _BAND_PASS.items():
        if not cid.startswith(prefix):
            continue
        marker = f"(pass: {band})"
        for gap in gaps:
            if marker in gap and "timed out" in gap.lower():
                return name
    return None


def hollow_pass_note(gaps: Iterable[str], prefix: str) -> str | None:
    """Name a band whose pass returned nothing, so the score cannot look finished."""
    spec = _BAND_PASS.get(prefix)
    if spec is None:
        return None
    name, band = spec
    marker = f"metrics.vacuous_pass_floor_skipped:{name}="
    kind: str | None = None
    for gap in gaps:
        text = str(gap)
        if not text.startswith(marker):
            continue
        if "no_analysis_evidence" in text:
            kind = "empty"
        elif "pass_degraded" in text:
            kind = "degraded"
    if kind == "empty":
        return (
            f"{name} ({band}) returned no analysis evidence. "
            "The 75% floor was not applied"
        )
    if kind == "degraded":
        return f"{name} ({band}) did not finish. The 75% floor was not applied"
    return None


def reopen_hollow_bands(result: CoverageResult, gaps: Iterable[str]) -> CoverageResult:
    """Leave a hollow pass's questions unanswered.

    An N/A line from another pass must not close security, reliability, or
    architecture when that pass itself returned no analysis.
    """
    gap_list = list(gaps)
    prefixes = [prefix for prefix in _BAND_PASS if hollow_pass_note(gap_list, prefix)]
    if not prefixes:
        return result
    na = dict(result.na)
    missed = list(result.missed)
    invalid = dict(result.invalid_na)
    for cid in list(na):
        if any(cid.startswith(prefix) for prefix in prefixes):
            na.pop(cid)
            invalid.pop(cid, None)
            if cid not in missed:
                missed.append(cid)
    for cid in list(invalid):
        if any(cid.startswith(prefix) for prefix in prefixes) and cid not in missed:
            invalid.pop(cid)
            missed.append(cid)
    return CoverageResult(
        covered=list(result.covered),
        covered_notes=dict(result.covered_notes),
        na=na,
        missed=missed,
        invalid_na=invalid,
    )


def explain_missed_id(cid: str, gaps: Iterable[str]) -> str:
    """What the reader does when a checklist question was not answered."""
    label = _question_label(cid)
    gap_list = list(gaps)
    for prefix in _BAND_PASS:
        note = hollow_pass_note(gap_list, prefix)
        if cid.startswith(prefix) and note:
            name, band = _BAND_PASS[prefix]
            if "did not finish" in note:
                reason = f"{name} ({band}) did not finish, so this question is unanswered."
            else:
                reason = (
                    f"{name} ({band}) returned no analysis evidence, "
                    "so this question is unanswered."
                )
            return f"{label}. {reason} {_FIX_POINTER}"
    band = _timed_out_band(cid, gap_list)
    if band is not None:
        return (
            f"{label}. The {band} pass timed out before the first token. "
            "Finished passes are kept. Re-run when the local model is free. "
            f"{_FIX_POINTER}"
        )
    related = [gap.strip() for gap in gaps if cid in gap]
    if any(
        "lazy n/a rejected" in gap.lower() or "not reviewed" in gap.lower()
        for gap in related
    ):
        return (
            f"{label}. The review marked this as not looked at. "
            "Re-run so it is closed with a finding or a fact from this repository. "
            f"{_FIX_POINTER}"
        )
    return (
        f"{label}. This question has no finding and no fact from this repository. "
        "Re-run so it is answered. "
        f"{_FIX_POINTER}"
    )


def explain_answered(cid: str, issues: Iterable[Issue]) -> str:
    """Point an answered question at the finding the reader should fix."""
    label = _question_label(cid)
    issue = _finding_for(cid, issues)
    if issue is None:
        return (
            f"{label}. A finding in this report covers this question. "
            "Apply its recommended fix."
        )
    return (
        f"{label}. See “{issue.title}” under {issue.priority} "
        "and apply its recommended fix."
    )


def _finding_for(cov_id: str, issues: Iterable[Issue]) -> Issue | None:
    """Link a question to a finding by its theme or its full coverage id."""
    from repolens.themes import canonicalize_coverage_id, theme_id_for_category

    canon = canonicalize_coverage_id(cov_id)
    needle = canon.lower()
    for issue in issues:
        mapped = theme_id_for_category(issue.category)
        if mapped == canon:
            return issue
        hay = " ".join(
            [
                issue.title,
                issue.explanation,
                issue.category,
                issue.impact,
                issue.recommendedFix,
            ]
        ).lower()
        if needle in hay:
            return issue
    return None


def _issue_addresses(cov_id: str, issues: Iterable[Issue]) -> bool:
    return _finding_for(cov_id, issues) is not None


def evaluate_coverage(
    ids: Iterable[str],
    issues: Iterable[Issue],
    gaps: Iterable[str],
    *,
    seeded_na: dict[str, str] | None = None,
    seeded_covered: dict[str, str] | None = None,
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

    seed_na = {
        canonicalize_coverage_id(k): v for k, v in (seeded_na or {}).items()
    }
    seed_cov = {
        canonicalize_coverage_id(k): v for k, v in (seeded_covered or {}).items()
    }
    na_raw = parse_coverage_notes(gaps)
    na = {
        **seed_na,
        **{
            canonicalize_coverage_id(cid): reason for cid, reason in na_raw.items()
        },
    }
    issue_list = list(issues)
    covered: list[str] = []
    covered_notes: dict[str, str] = {}
    missed: list[str] = []
    result_na: dict[str, str] = {}
    invalid_na: dict[str, str] = {}

    for cov_id in wanted:
        # Issues win over N/A when evidence exists (alias notes must not hide findings).
        if _issue_addresses(cov_id, issue_list):
            covered.append(cov_id)
            continue
        if cov_id in seed_cov:
            covered.append(cov_id)
            covered_notes[cov_id] = seed_cov[cov_id]
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
        covered=covered,
        covered_notes=covered_notes,
        na=result_na,
        missed=missed,
        invalid_na=invalid_na,
    )
