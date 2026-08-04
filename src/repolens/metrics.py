"""Audit confidence metrics (gate + security / architecture / reliability).

Formulas (Phase 5.1; tune via config later if needed):

- Per missed coverage id in band: −4 (cap −40)
- Per invalid/lazy N/A remapped in band: −3 (cap −30)
- Scanners all ``ran``: +5 on security band only (cap 100)
- ``gate_confidence`` = min(band confidences, pass confidences)
  − global missed penalty (−4/id, cap −40)
  − global invalid-N/A penalty (−3/id, cap −30)

None of these metrics is a “% secure” grade of the product under review.
Gate confidence reflects adequacy of *this review package* for a commit/push decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from repolens.coverage import CoverageResult
from repolens.schema import ScannerRun

_MISSED_PENALTY = 4
_MISSED_CAP = 40
_INVALID_NA_PENALTY = 3
_INVALID_NA_CAP = 30
_SCANNER_ALL_RAN_BONUS = 5


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


def compute_band_confidence(
    *,
    prefix: str,
    base_confidence: int,
    coverage: CoverageResult,
    scanner_bonus: int = 0,
) -> int:
    """Compute audit confidence for one checklist band (sec. / arch. / rel.)."""
    missed = _band_ids(coverage.missed, prefix)
    invalid = _band_ids(list(coverage.invalid_na.keys()), prefix)
    missed_pen = min(_MISSED_CAP, _MISSED_PENALTY * len(missed))
    invalid_pen = min(_INVALID_NA_CAP, _INVALID_NA_PENALTY * len(invalid))
    return _clamp(base_confidence - missed_pen - invalid_pen + scanner_bonus)


def _scanners_all_ran(scanner_runs: list[ScannerRun]) -> bool:
    if not scanner_runs:
        return False
    return all(run.status == "ran" for run in scanner_runs)


def compute_audit_metrics(
    *,
    pass_confidences: dict[str, int],
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun],
) -> AuditMetrics:
    """Derive gate + per-band audit confidences after deep merge."""
    scanner_bonus = _SCANNER_ALL_RAN_BONUS if _scanners_all_ran(scanner_runs) else 0

    p1 = pass_confidences.get("p1", pass_confidences.get("security", 0))
    p2 = pass_confidences.get("p2", pass_confidences.get("reliability", 0))
    p3 = pass_confidences.get("p3", pass_confidences.get("architecture", 0))

    security = compute_band_confidence(
        prefix="sec.",
        base_confidence=p1,
        coverage=coverage,
        scanner_bonus=scanner_bonus,
    )
    reliability = compute_band_confidence(
        prefix="rel.",
        base_confidence=p2,
        coverage=coverage,
        scanner_bonus=0,
    )
    architecture = compute_band_confidence(
        prefix="arch.",
        base_confidence=p3,
        coverage=coverage,
        scanner_bonus=0,
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
