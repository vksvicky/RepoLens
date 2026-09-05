from repolens.coverage import CoverageResult
from repolens.metrics import compute_audit_metrics
from repolens.schema import FindingReport, Issue, ScannerRun, Severity, Summary
from repolens.vacuous_floor import (
    PassFloorInput,
    apply_vacuous_pass_floors,
    has_analysis_evidence,
    is_floor_candidate,
    resolve_floor_value,
    skip_reason,
)


def _empty(confidence: int = 0) -> FindingReport:
    return FindingReport(confidence=confidence, summary=Summary(), issues=[])


def test_candidate_only_when_confidence_zero_and_no_issues() -> None:
    assert is_floor_candidate(_empty(0)) is True
    assert is_floor_candidate(_empty(80)) is False
    issue = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="heuristic.mega_file",
        file="a.py",
        line=1,
        title="t",
        explanation="e",
        recommendedFix="f",
    )
    assert is_floor_candidate(
        FindingReport(confidence=0, summary=Summary(), issues=[issue])
    ) is False


def test_analysis_evidence_raw_length_and_future_string_fields() -> None:
    stub = '{"issues":[],"confidence":0}'
    assert has_analysis_evidence(_empty(), stub) is False
    assert has_analysis_evidence(_empty(), "x" * 100) is True
    # Summary counts must NOT count as prose
    assert has_analysis_evidence(_empty(), "") is False


def test_resolve_floor_value_auto_and_overrides() -> None:
    assert resolve_floor_value(scanners_all_ran=True, config_floor=None) == 75
    assert resolve_floor_value(scanners_all_ran=False, config_floor=None) == 55
    assert resolve_floor_value(scanners_all_ran=True, config_floor=0) is None
    assert resolve_floor_value(scanners_all_ran=False, config_floor=90) == 90


def test_skip_reason_precedence_degraded_wins() -> None:
    assert (
        skip_reason(degraded=True, has_evidence=False, checklist_complete=False)
        == "pass_degraded"
    )
    assert (
        skip_reason(degraded=False, has_evidence=False, checklist_complete=False)
        == "no_analysis_evidence"
    )
    assert (
        skip_reason(degraded=False, has_evidence=True, checklist_complete=False)
        == "checklist_incomplete"
    )
    assert (
        skip_reason(degraded=False, has_evidence=True, checklist_complete=True)
        is None
    )


def _ran() -> list[ScannerRun]:
    return [
        ScannerRun(tool="gitleaks", status="ran"),
        ScannerRun(tool="semgrep", status="ran"),
        ScannerRun(tool="osv", status="ran"),
    ]


def test_apply_floors_logviewer_shape_gate_75_sec_80() -> None:
    raw = "x" * 100
    empty = _empty(0)
    passes = [
        PassFloorInput("p1", empty, raw, False),
        PassFloorInput("p2", empty, raw, False),
        PassFloorInput("p3", empty, raw, False),
    ]
    coverage = CoverageResult(
        covered=["sec.injection", "rel.edge_cases", "arch.testing"],
        missed=[],
        na={},
    )
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.pass_confidences == {"p1": 75, "p2": 75, "p3": 75}
    assert any("floored:p1=75" in n for n in result.notes)
    metrics = compute_audit_metrics(
        pass_confidences=result.pass_confidences,
        coverage=coverage,
        scanner_runs=_ran(),
        issues=[],
    )
    assert metrics.gate_confidence == 75
    assert metrics.security_audit_confidence == 80
    assert metrics.reliability_audit_confidence == 75
    assert metrics.architecture_audit_confidence == 75


def test_stub_raw_skips_with_no_analysis_evidence() -> None:
    passes = [PassFloorInput("p2", _empty(0), '{"issues":[],"confidence":0}', False)]
    coverage = CoverageResult(covered=["rel.edge_cases"], missed=[], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.pass_confidences["p2"] == 0
    assert result.notes == [
        "metrics.vacuous_pass_floor_skipped:p2=no_analysis_evidence"
    ]


def test_degraded_skip_precedes_no_evidence() -> None:
    passes = [PassFloorInput("p1", _empty(0), "", True)]
    coverage = CoverageResult(covered=["sec.injection"], missed=["sec.xss_csrf"], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.notes == [
        "metrics.vacuous_pass_floor_skipped:p1=pass_degraded"
    ]


def test_non_candidate_emits_no_note() -> None:
    passes = [PassFloorInput("p1", _empty(80), "x" * 100, False)]
    coverage = CoverageResult(covered=["sec.injection"], missed=[], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.notes == []
    assert result.pass_confidences["p1"] == 80
