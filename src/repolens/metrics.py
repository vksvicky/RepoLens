"""Audit confidence metrics (gate + security / architecture / reliability).

Formulas (Phase 5.1; tune via config later if needed):

- Per missed coverage id in band: −4 (cap −40)
- Per invalid/lazy N/A remapped in band: −3 (cap −30)
- Scanners all ``ran``: +5 on security band only (cap 100)
- **Open Critical/High findings** in that band further reduce band confidence
  (security: P1 or ``sec.*`` / scanner cats; reliability: P2 or ``rel.*``;
  architecture: P3 or ``arch.*`` / ``heuristic.*``)
- ``gate_confidence`` = min(**ran** pass confidences + **scored** band confidences)
  − global missed penalty (−4/id, cap −40)
  − global invalid-N/A penalty (−3/id, cap −30)

Passes that did not run (e.g. sentinel = P1 only) contribute **neither** a 0%
band score nor a floor for the gate. Unscored bands are ``None`` (N/A), not 0%.

**Security audit confidence is not “% secure”** and is not a CleanVibes-style
posture score. It combines checklist honesty with a penalty for open Critical/High
security findings so 100% is impossible while High/Critical P1/`sec.*` issues remain.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from repolens.coverage import CoverageResult
from repolens.schema import FindingReport, Issue, ScannerRun, Severity

_MISSED_PENALTY = 4
_MISSED_CAP = 40
_INVALID_NA_PENALTY = 3
_INVALID_NA_CAP = 30
_SCANNER_ALL_RAN_BONUS = 5
# Bands and the gate below this get a plain-language breakdown in the report.
LOW_AUDIT_BELOW = 70

_CRITICAL_PENALTY = 20
_CRITICAL_CAP = 60
_HIGH_PENALTY = 10
_HIGH_CAP = 50

_SCANNER_CAT_MARKERS = ("gitleaks", "semgrep", "osv", "trivy", "checkov")


@dataclass(frozen=True)
class AuditMetrics:
    gate_confidence: int
    security_audit_confidence: int | None
    architecture_audit_confidence: int | None
    reliability_audit_confidence: int | None


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def _band_ids(ids: list[str], prefix: str) -> list[str]:
    return [i for i in ids if i.startswith(prefix)]


def _is_security_issue(issue: Issue) -> bool:
    cat = (issue.category or "").lower()
    if issue.priority == "P1":
        return True
    if cat.startswith("sec.") or cat.startswith("security"):
        return True
    return any(m in cat for m in _SCANNER_CAT_MARKERS)


def _is_reliability_issue(issue: Issue) -> bool:
    cat = (issue.category or "").lower()
    return issue.priority == "P2" or cat.startswith("rel.")


def _is_architecture_issue(issue: Issue) -> bool:
    cat = (issue.category or "").lower()
    return (
        issue.priority == "P3"
        or cat.startswith("arch.")
        or cat.startswith("heuristic.")
    )


def severity_finding_penalty(issues: Iterable[Issue], *, band: str) -> int:
    """Penalty from open Critical/High findings attributed to ``band``.

    ``band`` is one of ``security``, ``reliability``, ``architecture``.
    """
    pred = {
        "security": _is_security_issue,
        "reliability": _is_reliability_issue,
        "architecture": _is_architecture_issue,
    }[band]
    critical = 0
    high = 0
    for issue in issues:
        if issue.source == "llm" or not pred(issue):
            continue
        if issue.severity == Severity.CRITICAL:
            critical += 1
        elif issue.severity == Severity.HIGH:
            high += 1
    crit_pen = min(_CRITICAL_CAP, _CRITICAL_PENALTY * critical)
    high_pen = min(_HIGH_CAP, _HIGH_PENALTY * high)
    return crit_pen + high_pen


def compute_band_confidence(
    *,
    prefix: str,
    base_confidence: int,
    coverage: CoverageResult,
    scanner_bonus: int = 0,
    finding_penalty: int = 0,
) -> int:
    """Compute audit confidence for one checklist band (sec. / arch. / rel.)."""
    missed = _band_ids(coverage.missed, prefix)
    invalid = _band_ids(list(coverage.invalid_na.keys()), prefix)
    missed_pen = min(_MISSED_CAP, _MISSED_PENALTY * len(missed))
    invalid_pen = min(_INVALID_NA_CAP, _INVALID_NA_PENALTY * len(invalid))
    return _clamp(
        base_confidence - missed_pen - invalid_pen + scanner_bonus - finding_penalty
    )


def _scanners_all_ran(scanner_runs: list[ScannerRun]) -> bool:
    if not scanner_runs:
        return False
    return all(run.status == "ran" for run in scanner_runs)


def _lookup_pass(pass_confidences: dict[str, int], *keys: str) -> int | None:
    """Return confidence for the first key present; missing keys are not 0%."""
    for key in keys:
        if key in pass_confidences:
            return pass_confidences[key]
    return None


def compute_audit_metrics(
    *,
    pass_confidences: dict[str, int],
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun],
    issues: Iterable[Issue] | None = None,
) -> AuditMetrics:
    """Derive gate + per-band audit confidences after deep merge.

    Only bands whose pass ran are scored. Sentinel (``p1`` only) yields a security
    audit % and gate based on that pass — architecture/reliability stay ``None``.
    """
    scanner_bonus = _SCANNER_ALL_RAN_BONUS if _scanners_all_ran(scanner_runs) else 0
    issue_list = list(issues or [])

    p1 = _lookup_pass(pass_confidences, "p1", "security")
    p2 = _lookup_pass(pass_confidences, "p2", "reliability")
    p3 = _lookup_pass(pass_confidences, "p3", "architecture")

    security: int | None = None
    if p1 is not None:
        security = compute_band_confidence(
            prefix="sec.",
            base_confidence=p1,
            coverage=coverage,
            scanner_bonus=scanner_bonus,
            finding_penalty=severity_finding_penalty(issue_list, band="security"),
        )

    reliability: int | None = None
    if p2 is not None:
        reliability = compute_band_confidence(
            prefix="rel.",
            base_confidence=p2,
            coverage=coverage,
            scanner_bonus=0,
            finding_penalty=severity_finding_penalty(issue_list, band="reliability"),
        )

    architecture: int | None = None
    if p3 is not None:
        architecture = compute_band_confidence(
            prefix="arch.",
            base_confidence=p3,
            coverage=coverage,
            scanner_bonus=0,
            finding_penalty=severity_finding_penalty(issue_list, band="architecture"),
        )

    present = [
        v
        for v in (p1, p2, p3, security, architecture, reliability)
        if v is not None
    ]
    floor = min(present) if present else 0

    # Global coverage penalties only for ids belonging to scored bands.
    scored_prefixes: list[str] = []
    if security is not None:
        scored_prefixes.append("sec.")
    if reliability is not None:
        scored_prefixes.append("rel.")
    if architecture is not None:
        scored_prefixes.append("arch.")

    def _in_scope(cid: str) -> bool:
        return any(cid.startswith(p) for p in scored_prefixes)

    scoped_missed = [m for m in coverage.missed if _in_scope(m)]
    scoped_invalid = [i for i in coverage.invalid_na if _in_scope(i)]
    global_missed = min(_MISSED_CAP, _MISSED_PENALTY * len(scoped_missed))
    global_invalid = min(_INVALID_NA_CAP, _INVALID_NA_PENALTY * len(scoped_invalid))
    gate = _clamp(floor - global_missed - global_invalid)

    return AuditMetrics(
        gate_confidence=gate,
        security_audit_confidence=security,
        architecture_audit_confidence=architecture,
        reliability_audit_confidence=reliability,
    )


def _titles(issues: Iterable[Issue], pred, severity: Severity) -> list[str]:
    return [
        issue.title
        for issue in issues
        if pred(issue) and issue.severity == severity
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
    """A timed-out band did not answer the checklist. That is separate from one miss."""
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


def low_audit_explanations(report: FindingReport) -> list[str]:
    """Why a band or the gate is under 70%, with the ids and findings involved.

    Medium and Low findings are omitted: they do not change these percentages.
    A Critical/High finding is listed on every band it matches.
    """
    missed = report.coverage.missed if report.coverage is not None else []
    bands = _scored_bands(report)
    lines: list[str] = []
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
    lines: list[str] = []
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
