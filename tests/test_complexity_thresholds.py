# tests/test_complexity_thresholds.py
"""B1 — complexity thresholds → severity / Issue eligibility."""

from __future__ import annotations

import pytest

from repolens.complexity.thresholds import (
    ComplexityBand,
    band_for_scores,
    should_emit_issue,
)
from repolens.schema import Severity


@pytest.mark.parametrize(
    ("cyclo", "cognitive", "expect_emit", "expect_severity", "expect_priority"),
    [
        (1, 1, False, None, None),
        (10, 15, False, None, None),
        (11, 5, True, Severity.MEDIUM, "P2"),
        (20, 15, True, Severity.MEDIUM, "P2"),
        (21, 10, True, Severity.HIGH, "P1"),
        (50, 0, True, Severity.HIGH, "P1"),
        (51, 0, True, Severity.CRITICAL, "P1"),
        (5, 16, True, Severity.MEDIUM, "P2"),
        (5, 25, True, Severity.MEDIUM, "P2"),
        (5, 26, True, Severity.HIGH, "P1"),
        # both trip → worst severity wins (CRITICAL > HIGH)
        (51, 26, True, Severity.CRITICAL, "P1"),
        (21, 26, True, Severity.HIGH, "P1"),
        (11, 16, True, Severity.MEDIUM, "P2"),
    ],
)
def test_band_for_scores(
    cyclo: int,
    cognitive: int,
    expect_emit: bool,
    expect_severity: Severity | None,
    expect_priority: str | None,
) -> None:
    band = band_for_scores(cyclomatic=cyclo, cognitive=cognitive)
    assert should_emit_issue(band) is expect_emit
    if expect_emit:
        assert band.severity == expect_severity
        assert band.priority == expect_priority
    else:
        assert band.severity is None
        assert isinstance(band, ComplexityBand)
