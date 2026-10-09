"""Audit confidence metrics (gate + security / architecture / reliability).

Formulas (Phase 5.1; tune via config later if needed):

- Per missed coverage id in band: −4 (cap −40)
- Per invalid/lazy N/A remapped in band: −3 (cap −30)
- Scanners all ``ran``: +5 on security band only (cap 100)
- **Open Critical/High findings** in that band further reduce band confidence
  (security: ``sec.*`` or a scanner category; reliability: ``rel.*``;
  architecture: ``arch.*`` or ``heuristic.*``). Priority alone does not
  choose the band. Model prose is excluded.
- ``gate_confidence`` = min(**ran** pass confidences + **scored** band confidences)
  − global missed penalty (−4/id, cap −40)
  − global invalid-N/A penalty (−3/id, cap −30)

Passes that did not run (e.g. sentinel = P1 only) contribute **neither** a 0%
band score nor a floor for the gate. Unscored bands are ``None`` (N/A), not 0%.

**Security audit confidence is not “% secure”** and is not a CleanVibes-style
posture score. It combines checklist honesty with a penalty for open Critical/High
security findings so 100% is impossible while High/Critical `sec.*` or scanner issues remain.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from repolens.coverage import CoverageResult
from repolens.schema import Issue, ScannerRun, Severity

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
    audit_incomplete: bool = False


_PASS_LABEL_FROM_KEY = {
    "p1": "p1",
    "security": "p1",
    "p2": "p2",
    "reliability": "p2",
    "p3": "p3",
    "architecture": "p3",
}
_PASS_KEY_BAND = {"security": "p1", "reliability": "p2", "architecture": "p3"}
_PASS_LABEL = {"p1": "Security", "p2": "Reliability", "p3": "Architecture"}

_SCHEMA_INVALID_PASS_PREFIX = re.compile(
    r"^llm\.schema_invalid\s*\(pass:\s*([^)]+)\)\s*:",
    re.IGNORECASE,
)


def _normalize_pass_label(raw: str) -> str | None:
    return _PASS_LABEL_FROM_KEY.get(raw.strip().lower())


def _pass_from_degraded_gap(text: str) -> str | None:
    """Extract p1/p2/p3 from structured gap prefixes only (not free-text bodies)."""
    if text.startswith("pass_degraded:"):
        label = text.split(":", 2)[1]
        return _normalize_pass_label(label)

    if (
        text.startswith("metrics.vacuous_pass_floor_skipped:")
        and "pass_degraded" in text
    ):
        rest = text.removeprefix("metrics.vacuous_pass_floor_skipped:")
        if "=" not in rest:
            return None
        label, _code = rest.split("=", 1)
        return _normalize_pass_label(label)

    if text.startswith("llm.schema_invalid (pass:"):
        match = _SCHEMA_INVALID_PASS_PREFIX.match(text)
        if match:
            return _normalize_pass_label(match.group(1))
        return None

    if text.startswith("llm.schema_invalid:"):
        rest = text.removeprefix("llm.schema_invalid:")
        if not rest or rest[0].isspace():
            return None
        label = rest.split(":", 1)[0].strip()
        return _normalize_pass_label(label)

    return None


def _is_degraded_gap(text: str) -> bool:
    return (
        text.startswith("llm.schema_invalid (pass:")
        or text.startswith("llm.schema_invalid:")
        or text.startswith("pass_degraded:")
        or (
            text.startswith("metrics.vacuous_pass_floor_skipped:")
            and "pass_degraded" in text
        )
    )


def degraded_passes_from_gaps(gaps: Iterable[str]) -> set[str]:
    """Return {'p1','p2','p3'} subsets marked packaging-degraded."""
    found: set[str] = set()
    for gap in gaps:
        text = str(gap)
        if not _is_degraded_gap(text):
            continue
        band = _pass_from_degraded_gap(text)
        if band:
            found.add(band)
    return found


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def _band_ids(ids: list[str], prefix: str) -> list[str]:
    return [i for i in ids if i.startswith(prefix)]


def _theme_id(issue: Issue) -> str:
    from repolens.themes import theme_id_for_category

    mapped = theme_id_for_category(issue.category or "")
    return (mapped or issue.category or "").lower()


def _is_security_issue(issue: Issue) -> bool:
    theme = _theme_id(issue)
    if theme.startswith("sec.") or theme.startswith("security"):
        return True
    cat = (issue.category or "").lower()
    return any(marker in cat for marker in _SCANNER_CAT_MARKERS)


def _is_reliability_issue(issue: Issue) -> bool:
    return _theme_id(issue).startswith("rel.")


def _is_architecture_issue(issue: Issue) -> bool:
    theme = _theme_id(issue)
    return theme.startswith("arch.") or theme.startswith("heuristic.")


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
    degraded_passes: Iterable[str] | None = None,
) -> AuditMetrics:
    """Derive gate + per-band audit confidences after deep merge.

    Only bands whose pass ran are scored. Sentinel (``p1`` only) yields a security
    audit % and gate based on that pass — architecture/reliability stay ``None``.

    A pass in ``degraded_passes`` (``p1``/``p2``/``p3``) failed to package its
    answer. Its band is unscored (``None``), it never enters the gate floor or the
    scoped checklist penalties, and ``audit_incomplete`` is set.
    """
    degraded = {str(p).lower() for p in (degraded_passes or ())} & {"p1", "p2", "p3"}
    scanner_bonus = _SCANNER_ALL_RAN_BONUS if _scanners_all_ran(scanner_runs) else 0
    issue_list = list(issues or [])
    scorable = {
        key: value
        for key, value in pass_confidences.items()
        if _PASS_KEY_BAND.get(key, key) not in degraded
    }
    security, reliability, architecture, p1, p2, p3 = _score_band_audits(
        pass_confidences=scorable,
        coverage=coverage,
        scanner_bonus=scanner_bonus,
        issue_list=issue_list,
    )
    present = [
        v
        for v in (p1, p2, p3, security, architecture, reliability)
        if v is not None
    ]
    floor = min(present) if present else 0
    gate = _gate_from_scored_bands(
        floor=floor,
        coverage=coverage,
        security=security,
        reliability=reliability,
        architecture=architecture,
    )
    return AuditMetrics(
        gate_confidence=gate,
        security_audit_confidence=security,
        architecture_audit_confidence=architecture,
        reliability_audit_confidence=reliability,
        audit_incomplete=bool(degraded),
    )


def _score_band_audits(
    *,
    pass_confidences: dict[str, int],
    coverage: CoverageResult,
    scanner_bonus: int,
    issue_list: list[Issue],
) -> tuple[int | None, int | None, int | None, int | None, int | None, int | None]:
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
    return security, reliability, architecture, p1, p2, p3


def _gate_from_scored_bands(
    *,
    floor: int,
    coverage: CoverageResult,
    security: int | None,
    reliability: int | None,
    architecture: int | None,
) -> int:
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
    return _clamp(floor - global_missed - global_invalid)


_EXPLAIN_EXPORTS = frozenset(
    {"low_audit_brief", "low_audit_explanations", "unverified_band_notes"}
)


def __getattr__(name: str):
    if name in _EXPLAIN_EXPORTS:
        from repolens import metrics_explain

        return getattr(metrics_explain, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
