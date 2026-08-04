"""Lazy / invalid N/A reasons must count as missed, not valid N/A."""

from __future__ import annotations

import pytest

from repolens.coverage import evaluate_coverage, is_lazy_na_reason


@pytest.mark.parametrize(
    "reason",
    [
        "not reviewed in this document",
        "Not explicitly reviewed",
        "not addressed in this document",
        "could be improved",
        "partially addressed",
        "Partially addressed — needs more work",
    ],
)
def test_is_lazy_na_reason_detects_lazy_patterns(reason: str) -> None:
    assert is_lazy_na_reason(reason) is True


@pytest.mark.parametrize(
    "reason",
    [
        "No HTTP surface in pack — XSS N/A",
        "No HTTP/HTML surface in reviewed pack — XSS/CSRF N/A for this desktop app",
        "No SQL/ORM usage in provided files",
    ],
)
def test_is_lazy_na_reason_allows_concrete_out_of_scope(reason: str) -> None:
    assert is_lazy_na_reason(reason) is False


def test_evaluate_coverage_lazy_na_goes_to_missed() -> None:
    result = evaluate_coverage(
        ["sec.xss"],
        [],
        ["coverage:sec.xss: N/A — not reviewed in this document"],
    )
    assert "sec.xss" in result.missed
    assert "sec.xss" not in result.na
    if hasattr(result, "invalid_na"):
        assert "sec.xss" in result.invalid_na


def test_evaluate_coverage_concrete_na_stays_na() -> None:
    result = evaluate_coverage(
        ["sec.xss"],
        [],
        ["coverage:sec.xss: N/A — No HTTP surface in pack — XSS N/A"],
    )
    assert "sec.xss" in result.na
    assert "sec.xss" not in result.missed
    assert "HTTP" in result.na["sec.xss"]
