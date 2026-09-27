# src/repolens/complexity/thresholds.py
"""Default complexity thresholds → severity / Issue eligibility (B1)."""

from __future__ import annotations

from dataclasses import dataclass

from repolens.schema import Severity

# Cyclomatic (McCabe) defaults
CYCLO_CLEAN_MAX = 10
CYCLO_MEDIUM_MAX = 20  # 11–20 MEDIUM
CYCLO_HIGH_MAX = 50  # 21–50 HIGH; >50 CRITICAL

# Cognitive (Sonar-behavioural) defaults
COGNITIVE_CLEAN_MAX = 15
COGNITIVE_MEDIUM_MAX = 25  # 16–25 MEDIUM; >25 HIGH

_SEVERITY_RANK = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class ComplexityBand:
    """Resolved band for a function's cyclo + cognitive scores."""

    severity: Severity | None
    priority: str | None
    cyclo_triggered: bool
    cognitive_triggered: bool


def _cyclo_band(cyclomatic: int) -> tuple[Severity | None, str | None]:
    if cyclomatic <= CYCLO_CLEAN_MAX:
        return None, None
    if cyclomatic <= CYCLO_MEDIUM_MAX:
        return Severity.MEDIUM, "P2"
    if cyclomatic <= CYCLO_HIGH_MAX:
        return Severity.HIGH, "P1"
    return Severity.CRITICAL, "P1"


def _cognitive_band(cognitive: int) -> tuple[Severity | None, str | None]:
    if cognitive <= COGNITIVE_CLEAN_MAX:
        return None, None
    if cognitive <= COGNITIVE_MEDIUM_MAX:
        return Severity.MEDIUM, "P2"
    return Severity.HIGH, "P1"


def _worse(
    a: tuple[Severity | None, str | None],
    b: tuple[Severity | None, str | None],
) -> tuple[Severity | None, str | None]:
    sa, pa = a
    sb, pb = b
    if sa is None:
        return b
    if sb is None:
        return a
    if _SEVERITY_RANK[sa] >= _SEVERITY_RANK[sb]:
        return a
    return b


def band_for_scores(*, cyclomatic: int, cognitive: int) -> ComplexityBand:
    cyclo = _cyclo_band(cyclomatic)
    cog = _cognitive_band(cognitive)
    worst = _worse(cyclo, cog)
    return ComplexityBand(
        severity=worst[0],
        priority=worst[1],
        cyclo_triggered=cyclo[0] is not None,
        cognitive_triggered=cog[0] is not None,
    )


def should_emit_issue(band: ComplexityBand) -> bool:
    return band.severity is not None
