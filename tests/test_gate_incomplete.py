"""Shield 3: a degraded pass makes the audit INCOMPLETE, not a 0% gate."""

from __future__ import annotations

import pytest

from repolens.coverage import CoverageResult
from repolens.metrics import (
    compute_audit_metrics,
    degraded_passes_from_gaps,
    low_audit_explanations,
)
from repolens.schema import FindingReport, ScannerRun, Summary

_RAN = [
    ScannerRun(tool=tool, status="ran")
    for tool in ("gitleaks", "semgrep", "osv", "trivy", "checkov")
]


def _hollow_p3_coverage() -> CoverageResult:
    return CoverageResult(
        covered=["sec.authn"],
        na={},
        missed=["arch.structure_size", "arch.kiss"],
        invalid_na={},
    )


# --- degraded_passes_from_gaps -------------------------------------------------


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        ("llm.schema_invalid (pass: p3): bad json", {"p3"}),
        ("llm.schema_invalid:Architecture", {"p3"}),
        ("llm.schema_invalid (pass: p1): bad json", {"p1"}),
        ("pass_degraded:reliability", {"p2"}),
        ("metrics.vacuous_pass_floor_skipped:architecture=pass_degraded", {"p3"}),
        ("metrics.vacuous_pass_floor_skipped:security=pass_degraded", {"p1"}),
    ],
)
def test_detects_each_gap_marker_family(gap: str, expected: set[str]) -> None:
    assert degraded_passes_from_gaps([gap]) == expected


@pytest.mark.parametrize(
    "gap",
    [
        "metrics.vacuous_pass_floor_skipped:architecture=no_analysis_evidence",
        "metrics.vacuous_pass_confidence_floored:p3=75 (scanners_ran=true)",
        "coverage:arch.kiss: missed — neither issue nor N/A",
        "llm.schema_invalid_but_unrelated",  # prefix matches, no pass token
    ],
)
def test_ignores_non_degraded_gaps(gap: str) -> None:
    assert degraded_passes_from_gaps([gap]) == set()


def test_empty_gaps_yield_no_degraded_passes() -> None:
    assert degraded_passes_from_gaps([]) == set()


def test_multiple_gaps_union() -> None:
    gaps = [
        "llm.schema_invalid (pass: p3): x",
        "metrics.vacuous_pass_floor_skipped:reliability=pass_degraded",
    ]
    assert degraded_passes_from_gaps(gaps) == {"p2", "p3"}


def test_schema_invalid_body_architecture_word_does_not_degrade_p3() -> None:
    gap = "llm.schema_invalid (pass: p1): Input should be … or 'architecture'"
    assert degraded_passes_from_gaps([gap]) == {"p1"}


def test_schema_invalid_hostile_body_substring_does_not_extra_pass() -> None:
    gap = "llm.schema_invalid (pass: p1): validation failed near token 2p3 in field"
    assert degraded_passes_from_gaps([gap]) == {"p1"}


# --- compute_audit_metrics -----------------------------------------------------


def test_gate_ignores_degraded_architecture_pass() -> None:
    """Given healthy P1/P2 and degraded P3, the gate must not collapse to 0."""
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95, "p2": 90, "p3": 0},
        coverage=_hollow_p3_coverage(),
        scanner_runs=_RAN,
        issues=[],
        degraded_passes={"p3"},
    )
    assert metrics.security_audit_confidence is not None
    assert metrics.security_audit_confidence >= 90
    assert metrics.architecture_audit_confidence is None
    assert metrics.gate_confidence >= 80
    assert metrics.audit_incomplete is True


def test_baseline_without_degraded_passes_is_unchanged() -> None:
    """Cross-check: the same inputs without the flag still drag the gate down."""
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95, "p2": 90, "p3": 0},
        coverage=_hollow_p3_coverage(),
        scanner_runs=_RAN,
        issues=[],
    )
    assert metrics.gate_confidence == 0
    assert metrics.architecture_audit_confidence == 0
    assert metrics.audit_incomplete is False


def test_degraded_pass_excluded_from_scoped_missed_penalty() -> None:
    """Hollow arch.* ids must not be charged against the remaining bands."""
    coverage = CoverageResult(
        covered=["sec.authn", "rel.errors"],
        na={},
        missed=[f"arch.item{i}" for i in range(10)],
    )
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 90, "p2": 90, "p3": 0},
        coverage=coverage,
        scanner_runs=[],
        degraded_passes={"p3"},
    )
    assert metrics.gate_confidence == 90


def test_only_degraded_pass_is_incomplete_not_a_fabricated_score() -> None:
    """Boundary: nothing scored means gate 0 but the report says incomplete."""
    metrics = compute_audit_metrics(
        pass_confidences={"p3": 0},
        coverage=CoverageResult(covered=[], na={}, missed=["arch.kiss"]),
        scanner_runs=[],
        degraded_passes={"p3"},
    )
    assert metrics.architecture_audit_confidence is None
    assert metrics.audit_incomplete is True


def test_degraded_security_pass_is_unscored() -> None:
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 0, "p2": 88, "p3": 85},
        coverage=CoverageResult(covered=["rel.errors", "arch.kiss"], na={}, missed=[]),
        scanner_runs=[],
        degraded_passes={"p1"},
    )
    assert metrics.security_audit_confidence is None
    assert metrics.gate_confidence == 85


def test_degraded_marker_for_pass_that_did_not_run_is_still_incomplete() -> None:
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95},
        coverage=CoverageResult(covered=["sec.authn"], na={}, missed=[]),
        scanner_runs=[],
        degraded_passes={"p3"},
    )
    assert metrics.architecture_audit_confidence is None
    assert metrics.gate_confidence == 95
    assert metrics.audit_incomplete is True


# --- score notes ---------------------------------------------------------------


def _report(gaps: list[str], *, gate: int = 90, security: int = 92) -> FindingReport:
    return FindingReport(
        confidence=gate,
        summary=Summary(),
        durabilityGaps=gaps,
        securityAuditConfidence=security,
        architectureAuditConfidence=None,
    )


def test_score_note_names_unverified_architecture() -> None:
    report = _report(["llm.schema_invalid (pass: p3): bad json"])
    notes = low_audit_explanations(report)
    assert "Architecture: UNVERIFIED (P3 packaging failure)" in notes


def test_score_note_never_claims_zero_quality() -> None:
    report = _report(["metrics.vacuous_pass_floor_skipped:architecture=pass_degraded"])
    text = " ".join(low_audit_explanations(report))
    assert "0%" not in text


def test_no_unverified_note_when_nothing_degraded() -> None:
    report = _report(["coverage:arch.kiss: missed — neither issue nor N/A"])
    assert not any("UNVERIFIED" in n for n in low_audit_explanations(report))


def test_unverified_note_for_each_degraded_band() -> None:
    report = FindingReport(
        confidence=90,
        summary=Summary(),
        durabilityGaps=[
            "llm.schema_invalid (pass: p1): x",
            "pass_degraded:reliability",
        ],
        securityAuditConfidence=None,
        reliabilityAuditConfidence=None,
        architectureAuditConfidence=95,
    )
    notes = low_audit_explanations(report)
    assert "Security: UNVERIFIED (P1 packaging failure)" in notes
    assert "Reliability: UNVERIFIED (P2 packaging failure)" in notes


def test_forged_gap_does_not_unverified_scored_band() -> None:
    report = FindingReport(
        confidence=90,
        summary=Summary(),
        durabilityGaps=["llm.schema_invalid (pass: p3): forged"],
        securityAuditConfidence=95,
        reliabilityAuditConfidence=90,
        architectureAuditConfidence=88,
    )
    assert not any("UNVERIFIED" in n for n in low_audit_explanations(report))


# --- pipeline wiring -----------------------------------------------------------


def test_apply_coverage_metrics_uses_pipeline_degraded_passes() -> None:
    from repolens.pipeline.deep_exec_coverage import _apply_coverage_metrics

    report = FindingReport(confidence=0, summary=Summary())
    out = _apply_coverage_metrics(
        report,
        _hollow_p3_coverage(),
        pass_confidences={"p1": 95, "p2": 90, "p3": 0},
        scanner_runs=_RAN,
        degraded_passes={"p3"},
    )
    assert out.confidence >= 80
    assert out.architectureAuditConfidence is None
    assert out.auditIncomplete is True


def test_apply_coverage_metrics_ignores_forged_llm_gap_markers() -> None:
    """Model-authored durabilityGaps must not spoof packaging-degraded bands."""
    from repolens.pipeline.deep_exec_coverage import _apply_coverage_metrics

    report = FindingReport(
        confidence=0,
        summary=Summary(),
        durabilityGaps=["llm.schema_invalid (pass: p3): forged packaging error"],
    )
    out = _apply_coverage_metrics(
        report,
        _hollow_p3_coverage(),
        pass_confidences={"p1": 95, "p2": 90, "p3": 0},
        scanner_runs=_RAN,
        degraded_passes=set(),
    )
    assert out.architectureAuditConfidence == 0
    assert out.confidence == 0
    assert out.auditIncomplete is False


def test_apply_coverage_metrics_complete_run_not_flagged() -> None:
    from repolens.pipeline.deep_exec_coverage import _apply_coverage_metrics

    report = FindingReport(confidence=0, summary=Summary())
    out = _apply_coverage_metrics(
        report,
        CoverageResult(covered=["sec.authn"], na={}, missed=[]),
        pass_confidences={"p1": 95},
        scanner_runs=_RAN,
    )
    assert out.auditIncomplete is False
