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
