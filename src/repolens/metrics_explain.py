"""Plain-language audit confidence explanations (report / CLI brief).

Split from ``repolens.metrics`` so the compute module stays under the mega-file
threshold. Public names are also available via ``repolens.metrics``.
"""

from __future__ import annotations

from collections.abc import Iterable

from repolens.metrics import (
    _PASS_LABEL,
    LOW_AUDIT_BELOW,
    _is_architecture_issue,
    _is_reliability_issue,
    _is_security_issue,
    degraded_passes_from_gaps,
)
from repolens.schema import FindingReport, Issue, Severity


def _titles(issues: Iterable[Issue], pred, severity: Severity) -> list[str]:
    return [
        issue.title
        for issue in issues
        if issue.source != "llm" and pred(issue) and issue.severity == severity
    ]


def _missed_clause(ids: list[str]) -> str | None:
    if not ids:
        return None
    noun = (
        "checklist id was not counted"
        if len(ids) == 1
        else "checklist ids were not counted"
    )
    return f"{len(ids)} {noun}"


def _finding_clause(critical: int, high: int) -> str | None:
    parts: list[str] = []
    if critical:
        noun = "Critical finding" if critical == 1 else "Critical findings"
        parts.append(f"{critical} {noun}")
    if high:
        noun = "High finding" if high == 1 else "High findings"
        parts.append(f"{high} {noun}")
    if not parts:
        return None
    return " and ".join(parts)


_PASS_FOR_PREFIX = {"sec.": "p1", "rel.": "p2", "arch.": "p3"}


def _pass_failure_note(report: FindingReport, prefix: str) -> str | None:
    """A hollow or timed-out band did not answer the checklist."""
    from repolens.coverage import hollow_pass_note

    hollow = hollow_pass_note(report.durabilityGaps, prefix)
    if hollow is not None:
        return hollow
    band = _PASS_FOR_PREFIX.get(prefix)
    if band is None:
        return None
    marker = f"(pass: {band})"
    for gap in report.durabilityGaps:
        if marker in gap and "timed out" in gap.lower():
            return "the checklist pass timed out before it could answer"
    return None


def _band_sentence(
    label: str,
    score: int,
    *,
    missed: list[str],
    issues: list[Issue],
    pred,
    detail: bool,
    pass_note: str | None = None,
) -> str:
    critical = _titles(issues, pred, Severity.CRITICAL)
    high = _titles(issues, pred, Severity.HIGH)
    clauses = [
        clause
        for clause in (
            pass_note,
            _missed_clause(missed),
            _finding_clause(len(critical), len(high)),
        )
        if clause
    ]
    if clauses:
        body = "; ".join(clauses)
    else:
        body = (
            "no missed checklist ids and no Critical/High findings in this band, "
            "so the pass base was already under 70%"
        )
    sentence = f"{label} audit {score}%: {body}."
    if not detail:
        return sentence
    extras: list[str] = []
    if missed:
        extras.append("Each unanswered question is explained under Checklist.")
    named = critical + high
    if named:
        shown = "; ".join(named[:8])
        extras.append(f"Open Critical/High in this band: {shown}.")
        extras.append("Clearing those findings raises this score.")
    if extras:
        sentence = f"{sentence} {' '.join(extras)}"
    return sentence


def _scored_bands(report: FindingReport) -> list[tuple[str, str, int]]:
    rows = [
        ("Security", "sec.", report.securityAuditConfidence),
        ("Reliability", "rel.", report.reliabilityAuditConfidence),
        ("Architecture", "arch.", report.architectureAuditConfidence),
    ]
    return [(label, prefix, score) for label, prefix, score in rows if score is not None]


def _band_predicate(prefix: str):
    return {
        "sec.": _is_security_issue,
        "rel.": _is_reliability_issue,
        "arch.": _is_architecture_issue,
    }[prefix]


def _gate_sentence(report: FindingReport, bands: list[tuple[str, str, int]]) -> str | None:
    if report.confidence >= LOW_AUDIT_BELOW or not bands:
        return None
    label, _prefix, lowest = min(bands, key=lambda row: row[2])
    missed = report.coverage.missed if report.coverage is not None else []
    prefixes = [prefix for _label, prefix, _score in bands]
    scoped = [item for item in missed if any(item.startswith(p) for p in prefixes)]
    if scoped and report.confidence < lowest:
        return (
            f"Gate {report.confidence}%: {label.lower()} is the lowest band at "
            f"{lowest}%, and checklist ids that were not counted lower it further. "
            "See Coverage."
        )
    if report.confidence == lowest:
        return f"Gate {report.confidence}% matches the lowest band, {label.lower()}."
    return (
        f"Gate {report.confidence}%: the lowest band is {label.lower()} at {lowest}%."
    )


def unverified_band_notes(report: FindingReport) -> list[str]:
    """One line per packaging-degraded band. Never implies 0% quality.

    Only bands that are both marked in durabilityGaps *and* left unscored
    (``None`` audit confidence) are listed, so forged LLM gap markers cannot
    invent UNVERIFIED lines for answered passes.
    """
    degraded = degraded_passes_from_gaps(report.durabilityGaps)
    conf_for = {
        "p1": report.securityAuditConfidence,
        "p2": report.reliabilityAuditConfidence,
        "p3": report.architectureAuditConfidence,
    }
    return [
        f"{_PASS_LABEL[band]}: UNVERIFIED ({band.upper()} packaging failure)"
        for band in sorted(degraded)
        if conf_for.get(band) is None
    ]


def low_audit_explanations(report: FindingReport) -> list[str]:
    """Why a band or the gate is under 70%, with the ids and findings involved.

    Medium and Low findings are omitted: they do not change these percentages.
    A Critical/High finding is listed on every band it matches. Bands whose pass
    failed to package are listed first as UNVERIFIED.
    """
    missed = report.coverage.missed if report.coverage is not None else []
    bands = _scored_bands(report)
    lines: list[str] = unverified_band_notes(report)
    for label, prefix, score in bands:
        if score >= LOW_AUDIT_BELOW:
            continue
        lines.append(
            _band_sentence(
                label,
                score,
                missed=[item for item in missed if item.startswith(prefix)],
                issues=list(report.issues),
                pred=_band_predicate(prefix),
                detail=True,
                pass_note=_pass_failure_note(report, prefix),
            )
        )
    gate = _gate_sentence(report, bands)
    if gate is not None:
        lines.append(gate)
    return lines


def low_audit_brief(report: FindingReport) -> list[str]:
    """Same deductions as the report, without the checklist-id list."""
    missed = report.coverage.missed if report.coverage is not None else []
    bands = _scored_bands(report)
    lines: list[str] = unverified_band_notes(report)
    for label, prefix, score in bands:
        if score >= LOW_AUDIT_BELOW:
            continue
        lines.append(
            _band_sentence(
                label,
                score,
                missed=[item for item in missed if item.startswith(prefix)],
                issues=list(report.issues),
                pred=_band_predicate(prefix),
                detail=False,
                pass_note=_pass_failure_note(report, prefix),
            )
        )
    gate = _gate_sentence(report, bands)
    if gate is not None:
        lines.append(gate)
    return lines
