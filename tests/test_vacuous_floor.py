from pathlib import Path

from types import SimpleNamespace

from repolens.config import load_config
from repolens.coverage import CoverageResult
from repolens.metrics import compute_audit_metrics
from repolens.schema import FindingReport, Issue, ScannerRun, Severity, Summary
from repolens.vacuous_floor import (
    PassFloorInput,
    apply_vacuous_pass_floors,
    has_analysis_evidence,
    is_finding_like_gap,
    is_floor_candidate,
    is_vacuous_for_floor,
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


def test_analysis_evidence_future_report_string_field() -> None:
    report = _empty()
    object.__setattr__(report, "analysisNotes", "x" * 20)
    assert has_analysis_evidence(report, "") is True
    assert has_analysis_evidence(report, "short") is True

    duck = SimpleNamespace(confidence=0, issues=[], analysisNotes="y" * 20)
    assert has_analysis_evidence(duck, "") is True  # type: ignore[arg-type]


def test_is_finding_like_gap_filters_noise_and_keeps_real_gaps() -> None:
    assert is_finding_like_gap("Two-Lane: transport noise") is False
    assert is_finding_like_gap("metrics.vacuous_pass_confidence_floored:p1=75") is False
    assert is_finding_like_gap("coverage: sec.injection missed") is True
    assert is_finding_like_gap("llm.schema_invalid: bad json") is True
    assert is_finding_like_gap("other.gap: something") is False


def test_is_vacuous_for_floor_eligibility() -> None:
    base = _empty(0)
    assert is_vacuous_for_floor(base, degraded=True) is False
    assert is_vacuous_for_floor(_empty(80), degraded=False) is False
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
    with_issues = FindingReport(confidence=0, summary=Summary(), issues=[issue])
    assert is_vacuous_for_floor(with_issues, degraded=False) is False

    finding_like = FindingReport(
        confidence=0,
        summary=Summary(),
        issues=[],
        durabilityGaps=["coverage: sec.injection missed"],
    )
    assert is_vacuous_for_floor(finding_like, degraded=False) is False

    two_lane_only = FindingReport(
        confidence=0,
        summary=Summary(),
        issues=[],
        durabilityGaps=["Two-Lane: lane mismatch"],
    )
    assert is_vacuous_for_floor(two_lane_only, degraded=False) is True


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


def _not_all_ran() -> list[ScannerRun]:
    return [
        ScannerRun(tool="gitleaks", status="ran"),
        ScannerRun(tool="semgrep", status="skipped"),
        ScannerRun(tool="osv", status="ran"),
    ]


def test_scanners_not_ran_uses_floor_55() -> None:
    raw = "x" * 100
    empty = _empty(0)
    passes = [PassFloorInput("p1", empty, raw, False)]
    coverage = CoverageResult(
        covered=["sec.injection", "rel.edge_cases", "arch.testing"],
        missed=[],
        na={},
    )
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_not_all_ran(), config_floor=None
    )
    assert result.pass_confidences["p1"] == 55
    assert any("floored:p1=55" in n for n in result.notes)
    assert any("scanners_ran=false" in n for n in result.notes)
    metrics = compute_audit_metrics(
        pass_confidences=result.pass_confidences,
        coverage=coverage,
        scanner_runs=_not_all_ran(),
        issues=[],
    )
    assert metrics.security_audit_confidence == 55
    assert metrics.gate_confidence == 55


def test_config_floor_override_90() -> None:
    raw = "x" * 100
    empty = _empty(0)
    passes = [PassFloorInput("p1", empty, raw, False)]
    coverage = CoverageResult(
        covered=["sec.injection", "rel.edge_cases", "arch.testing"],
        missed=[],
        na={},
    )
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=90
    )
    assert result.pass_confidences["p1"] == 90
    assert any("floored:p1=90" in n for n in result.notes)


def test_critical_scanner_issue_still_penalises_after_floor() -> None:
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
    floor_result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert floor_result.pass_confidences == {"p1": 75, "p2": 75, "p3": 75}
    crit = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="semgrep",
        file="leak.py",
        line=10,
        title="Hardcoded secret",
        explanation="Secret in source",
        impact="Credential exposure",
        recommendedFix="Remove secret",
        codeExample='os.environ["KEY"]',
        source="scanner",
    )
    metrics = compute_audit_metrics(
        pass_confidences=floor_result.pass_confidences,
        coverage=coverage,
        scanner_runs=_ran(),
        issues=[crit],
    )
    assert metrics.security_audit_confidence == 60
    assert metrics.gate_confidence == 60
    assert metrics.reliability_audit_confidence == 75
    assert metrics.architecture_audit_confidence == 75


def test_two_lane_gap_does_not_block_vacuous() -> None:
    report = _empty(0)
    report.durabilityGaps = [
        "Two-Lane: Fast Brain sees 10000 file(s); LLM sample pool is 200"
    ]
    assert is_vacuous_for_floor(report, degraded=False) is True


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


def test_config_floor_zero_leaves_confidence_unchanged_no_notes() -> None:
    passes = [PassFloorInput("p1", _empty(0), "x" * 100, False)]
    coverage = CoverageResult(covered=["sec.injection"], missed=[], na={})
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=0
    )
    assert result.pass_confidences["p1"] == 0
    assert result.notes == []


def test_checklist_incomplete_skips_floor_with_note() -> None:
    passes = [PassFloorInput("p1", _empty(0), "x" * 100, False)]
    coverage = CoverageResult(
        covered=["rel.edge_cases"],
        missed=["sec.injection"],
        na={},
    )
    result = apply_vacuous_pass_floors(
        passes, coverage=coverage, scanner_runs=_ran(), config_floor=None
    )
    assert result.pass_confidences["p1"] == 0
    assert result.notes == [
        "metrics.vacuous_pass_floor_skipped:p1=checklist_incomplete"
    ]


def test_deep_vacuous_floor_config_default_none(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text("", encoding="utf-8")

    cfg = load_config(project, trust_project=False)
    assert cfg.deep.vacuous_pass_confidence_floor is None


def test_deep_vacuous_floor_config_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        "[deep]\nvacuous_pass_confidence_floor = 0\n", encoding="utf-8"
    )

    cfg = load_config(project, trust_project=False)
    assert cfg.deep.vacuous_pass_confidence_floor == 0


def test_deep_vacuous_floor_config_loads_pinned_value(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        "[deep]\nvacuous_pass_confidence_floor = 75\n", encoding="utf-8"
    )

    cfg = load_config(project, trust_project=False)
    assert cfg.deep.vacuous_pass_confidence_floor == 75


def test_build_pass_confidences_with_floors_appends_notes() -> None:
    """Wire helper: floors pass bases and appends notes onto the merged report."""
    from repolens.pipeline.deep_exec import build_pass_confidences_with_floors

    raw = "x" * 100
    empty = _empty(0)
    outcomes = [
        PassFloorInput("p1", empty, raw, False),
        PassFloorInput("p2", empty, raw, False),
    ]
    coverage = CoverageResult(
        covered=["sec.injection", "rel.edge_cases"],
        missed=[],
        na={},
    )
    report = FindingReport(
        confidence=0,
        summary=Summary(),
        issues=[],
        durabilityGaps=["Two-Lane: pack truncated"],
    )
    updated, pass_confidences = build_pass_confidences_with_floors(
        outcomes,
        coverage=coverage,
        scanner_runs=_ran(),
        config_floor=None,
        report=report,
    )
    assert pass_confidences == {"p1": 75, "p2": 75}
    assert "Two-Lane: pack truncated" in updated.durabilityGaps
    assert any(
        "metrics.vacuous_pass_confidence_floored:p1=75" in g
        for g in updated.durabilityGaps
    )
    assert any(
        "metrics.vacuous_pass_confidence_floored:p2=75" in g
        for g in updated.durabilityGaps
    )
    # Re-applying must not duplicate notes
    again, _ = build_pass_confidences_with_floors(
        outcomes,
        coverage=coverage,
        scanner_runs=_ran(),
        config_floor=None,
        report=updated,
    )
    floored = [
        g
        for g in again.durabilityGaps
        if g.startswith("metrics.vacuous_pass_confidence_floored:")
    ]
    assert len(floored) == 2
