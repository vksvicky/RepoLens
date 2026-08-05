"""Audit confidence metrics (gate + security / architecture / reliability).

Formulas (Phase 5.1; tune via config later if needed):

- Per missed coverage id in band: −4 (cap −40)
- Per invalid/lazy N/A remapped in band: −3 (cap −30)
- Scanners all ``ran``: +5 on security band only (cap 100)
- **Open Critical/High findings** in that band further reduce band confidence
  (security: P1 or ``sec.*`` / scanner cats; reliability: P2 or ``rel.*``;
  architecture: P3 or ``arch.*`` / ``heuristic.*``)
- ``gate_confidence`` = min(band confidences, pass confidences)
  − global missed penalty (−4/id, cap −40)
  − global invalid-N/A penalty (−3/id, cap −30)

**Security audit confidence is not “% secure”** and is not a CleanVibes-style
posture score. It combines checklist honesty with a penalty for open Critical/High
security findings so 100% is impossible while High/Critical P1/`sec.*` issues remain.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from repolens.coverage import CoverageResult
from repolens.schema import Issue, ScannerRun, Severity

_MISSED_PENALTY = 4
_MISSED_CAP = 40
_INVALID_NA_PENALTY = 3
_INVALID_NA_CAP = 30
_SCANNER_ALL_RAN_BONUS = 5

_CRITICAL_PENALTY = 20
_CRITICAL_CAP = 60
_HIGH_PENALTY = 10
_HIGH_CAP = 50

_SCANNER_CAT_MARKERS = ("gitleaks", "semgrep", "osv")


@dataclass(frozen=True)
class AuditMetrics:
    gate_confidence: int
    security_audit_confidence: int
    architecture_audit_confidence: int
    reliability_audit_confidence: int


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
        if not pred(issue):
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


def compute_audit_metrics(
    *,
    pass_confidences: dict[str, int],
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun],
    issues: Iterable[Issue] | None = None,
) -> AuditMetrics:
    """Derive gate + per-band audit confidences after deep merge."""
    scanner_bonus = _SCANNER_ALL_RAN_BONUS if _scanners_all_ran(scanner_runs) else 0
    issue_list = list(issues or [])

    p1 = pass_confidences.get("p1", pass_confidences.get("security", 0))
    p2 = pass_confidences.get("p2", pass_confidences.get("reliability", 0))
    p3 = pass_confidences.get("p3", pass_confidences.get("architecture", 0))

    security = compute_band_confidence(
        prefix="sec.",
        base_confidence=p1,
        coverage=coverage,
        scanner_bonus=scanner_bonus,
        finding_penalty=severity_finding_penalty(issue_list, band="security"),
    )
    reliability = compute_band_confidence(
        prefix="rel.",
        base_confidence=p2,
        coverage=coverage,
        scanner_bonus=0,
        finding_penalty=severity_finding_penalty(issue_list, band="reliability"),
    )
    architecture = compute_band_confidence(
        prefix="arch.",
        base_confidence=p3,
        coverage=coverage,
        scanner_bonus=0,
        finding_penalty=severity_finding_penalty(issue_list, band="architecture"),
    )

    present_pass = [v for v in (p1, p2, p3) if v is not None]
    band_vals = [security, architecture, reliability]
    floor = min([*present_pass, *band_vals]) if (present_pass or band_vals) else 0

    global_missed = min(_MISSED_CAP, _MISSED_PENALTY * len(coverage.missed))
    global_invalid = min(
        _INVALID_NA_CAP, _INVALID_NA_PENALTY * len(coverage.invalid_na)
    )
    gate = _clamp(floor - global_missed - global_invalid)

    return AuditMetrics(
        gate_confidence=gate,
        security_audit_confidence=security,
        architecture_audit_confidence=architecture,
        reliability_audit_confidence=reliability,
    )
