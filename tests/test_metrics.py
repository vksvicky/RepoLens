"""Audit confidence formulas (gate + band-specific)."""

from __future__ import annotations

from repolens.coverage import CoverageResult
from repolens.metrics import (
    AuditMetrics,
    compute_audit_metrics,
    compute_band_confidence,
    low_audit_brief,
    low_audit_explanations,
)
from repolens.schema import CoverageBlock, FindingReport, Issue, ScannerRun, Severity, Summary


def test_security_audit_confidence_drops_on_missed_sec_ids() -> None:
    coverage = CoverageResult(
        covered=["sec.secrets"],
        missed=["sec.injection", "sec.xss"],
        na={},
    )
    conf = compute_band_confidence(
        prefix="sec.",
        base_confidence=95,
        coverage=coverage,
        scanner_bonus=0,
    )
    # 2 missed × −4 = −8 → 87
    assert conf == 87


def test_security_audit_confidence_penalizes_invalid_na() -> None:
    coverage = CoverageResult(
        covered=[],
        missed=["sec.xss"],
        na={},
        invalid_na={"sec.xss": "not reviewed in this document"},
    )
    conf = compute_band_confidence(
        prefix="sec.",
        base_confidence=95,
        coverage=coverage,
        scanner_bonus=0,
    )
    # missed −4 + invalid_na −3 = −7 → 88
    assert conf == 88


def test_scanner_bonus_only_on_security_band() -> None:
    coverage = CoverageResult(covered=["sec.secrets"], missed=[], na={})
    with_bonus = compute_band_confidence(
        prefix="sec.",
        base_confidence=90,
        coverage=coverage,
        scanner_bonus=5,
    )
    assert with_bonus == 95

    arch = compute_band_confidence(
        prefix="arch.",
        base_confidence=90,
        coverage=CoverageResult(covered=["arch.testing"], missed=[], na={}),
        scanner_bonus=5,
    )
    # scanner_bonus applied by caller only for security; function still adds when passed
    assert arch == 95


def test_missed_penalty_capped_at_40() -> None:
    missed = [f"sec.item{i}" for i in range(20)]
    coverage = CoverageResult(covered=[], missed=missed, na={})
    conf = compute_band_confidence(
        prefix="sec.",
        base_confidence=100,
        coverage=coverage,
        scanner_bonus=0,
    )
    # 20 × −4 would be −80, capped at −40 → 60
    assert conf == 60


def test_gate_confidence_at_most_lowest_band() -> None:
    coverage = CoverageResult(
        covered=["arch.testing", "rel.error_handling"],
        missed=["sec.injection", "sec.xss", "sec.secrets", "sec.auth"],
        na={},
    )
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95, "p2": 90, "p3": 92},
        coverage=coverage,
        scanner_runs=[
            ScannerRun(tool="gitleaks", status="ran"),
            ScannerRun(tool="semgrep", status="ran"),
            ScannerRun(tool="osv", status="ran"),
        ],
    )
    assert isinstance(metrics, AuditMetrics)
    assert metrics.security_audit_confidence is not None
    assert metrics.architecture_audit_confidence is not None
    assert metrics.reliability_audit_confidence is not None
    assert metrics.security_audit_confidence < 95
    # Gate must not exceed the lowest band confidence
    bands = [
        metrics.security_audit_confidence,
        metrics.architecture_audit_confidence,
        metrics.reliability_audit_confidence,
    ]
    assert metrics.gate_confidence <= min(bands)
    assert metrics.gate_confidence <= min(95, 90, 92)


def test_sentinel_only_scores_security_band() -> None:
    """Missing P2/P3 must not become 0% architecture or drag gate to 0."""
    coverage = CoverageResult(
        covered=["sec.secrets", "sec.injection"],
        missed=[],
        na={"sec.xss_csrf": "No web surface in pack"},
    )
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95},
        coverage=coverage,
        scanner_runs=[
            ScannerRun(tool="gitleaks", status="ran"),
            ScannerRun(tool="semgrep", status="ran"),
            ScannerRun(tool="osv", status="ran"),
        ],
    )
    assert metrics.security_audit_confidence == 100  # 95 + scanner 5
    assert metrics.architecture_audit_confidence is None
    assert metrics.reliability_audit_confidence is None
    assert metrics.gate_confidence == 95  # min(p1=95, security=100)


def test_architecture_mode_only_scores_architecture_band() -> None:
    metrics = compute_audit_metrics(
        pass_confidences={"p3": 88},
        coverage=CoverageResult(
            covered=["arch.testing"],
            missed=[],
            na={},
        ),
        scanner_runs=[],
    )
    assert metrics.architecture_audit_confidence == 88
    assert metrics.security_audit_confidence is None
    assert metrics.reliability_audit_confidence is None
    assert metrics.gate_confidence == 88


def test_security_audit_penalized_by_high_p1_findings() -> None:
    """Open High P1 findings must pull security audit below 100 even with clean coverage."""
    from repolens.schema import Issue, Severity

    coverage = CoverageResult(
        covered=["sec.injection", "sec.secrets"],
        missed=[],
        na={"sec.xss_csrf": "No web surface in pack"},
    )
    issues = [
        Issue(
            severity=Severity.HIGH,
            priority="P1",
            category="sec.injection",
            file="a.swift",
            line=1,
            title="Injection risk",
            explanation="bad",
            impact="RCE risk",
            recommendedFix="sanitize",
            codeExample="fix()",
        ),
        Issue(
            severity=Severity.HIGH,
            priority="P1",
            category="sec.secrets",
            file="b.swift",
            line=1,
            title="Secret handling",
            explanation="bad",
            impact="leak",
            recommendedFix="keychain",
            codeExample="fix()",
        ),
    ]
    metrics = compute_audit_metrics(
        pass_confidences={"p1": 95, "p2": 90, "p3": 90},
        coverage=coverage,
        scanner_runs=[
            ScannerRun(tool="gitleaks", status="ran"),
            ScannerRun(tool="semgrep", status="ran"),
            ScannerRun(tool="osv", status="ran"),
        ],
        issues=issues,
    )
    # base 95 + scanner 5 − 2×HIGH(10) = 100 − 20 = 80 (clamped via steps)
    assert metrics.security_audit_confidence == 80
    assert metrics.security_audit_confidence < 100


def test_finding_report_optional_audit_confidence_fields() -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        securityAuditConfidence=70,
        architectureAuditConfidence=75,
        reliabilityAuditConfidence=None,
    )
    assert report.securityAuditConfidence == 70
    assert report.architectureAuditConfidence == 75
    assert report.reliabilityAuditConfidence is None

    legacy = FindingReport(confidence=80, summary=Summary())
    assert legacy.securityAuditConfidence is None
    assert legacy.architectureAuditConfidence is None
    assert legacy.reliabilityAuditConfidence is None


def test_cross_source_sca_dedupe_before_security_penalty() -> None:
    """#14: 2 advisories × (scanner High + LLM Critical) → 2 unique High → −20."""
    from repolens.metrics import severity_finding_penalty
    from repolens.scanners.sca import dedupe_cross_source_sca_issues
    from repolens.schema import Issue, Severity

    def row(
        *,
        category: str,
        title: str,
        severity: Severity,
        source: str,
        package: str,
    ) -> Issue:
        return Issue(
            severity=severity,
            priority="P1",
            category=category,
            file="Cargo.lock" if source == "scanner" else "src/lib.rs",
            line=1,
            title=title,
            explanation=title,
            impact="vulnerable dependency",
            recommendedFix="upgrade",
            codeExample="# upgrade",
            source=source,  # type: ignore[arg-type]
            packageName=package,
        )

    raw = [
        row(
            category="osv",
            title="RUSTSEC-2024-0436 in paste",
            severity=Severity.HIGH,
            source="scanner",
            package="paste",
        ),
        row(
            category="sec.supply_chain",
            title="RUSTSEC-2024-0436 paste Critical",
            severity=Severity.CRITICAL,
            source="llm",
            package="paste",
        ),
        row(
            category="osv",
            title="RUSTSEC-2026-0192 in ttf-parser",
            severity=Severity.HIGH,
            source="scanner",
            package="ttf-parser",
        ),
        row(
            category="sec.supply_chain",
            title="RUSTSEC-2026-0192 ttf-parser Critical",
            severity=Severity.CRITICAL,
            source="llm",
            package="ttf-parser",
        ),
    ]
    # The two LLM Critical rows do not add a penalty. The two scanner Highs do.
    assert severity_finding_penalty(raw, band="security") == 20

    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues(raw)
    assert raw_total == 4
    assert raw_ch == 4
    assert len(deduped) == 2
    assert all(i.severity == Severity.HIGH for i in deduped)
    assert severity_finding_penalty(deduped, band="security") == 20

    metrics = compute_audit_metrics(
        pass_confidences={"p1": 75, "p2": 75, "p3": 75},
        coverage=CoverageResult(covered=["sec.secrets"], missed=[], na={}),
        scanner_runs=[
            ScannerRun(tool="osv", status="ran"),
            ScannerRun(tool="gitleaks", status="ran"),
        ],
        issues=deduped,
    )
    # 75 + 5 scanner − 20 (2 High) = 60
    assert metrics.security_audit_confidence == 60


def _high(title: str, *, category: str, priority: str = "P2") -> Issue:
    return Issue(
        severity=Severity.HIGH,
        priority=priority,  # type: ignore[arg-type]
        category=category,
        file="src/example.py",
        line=1,
        title=title,
        explanation="complex",
        impact="harder to change safely",
        recommendedFix="split the function",
        codeExample="def smaller():\n    return 1\n",
    )


def test_model_high_does_not_lower_the_band() -> None:
    from repolens.metrics import severity_finding_penalty

    model = _high(
        "model said this is complex", category="arch.readability_complexity"
    ).model_copy(update={"source": "llm"})
    measured = _high("nested", category="heuristic.deep_nesting").model_copy(
        update={"source": "heuristic"}
    )
    assert severity_finding_penalty([model], band="architecture") == 0
    assert severity_finding_penalty([measured], band="architecture") == 10


def test_low_audit_notes_name_misses_and_highs() -> None:
    """A band under 70% lists the deductions; Medium findings do not."""
    missed = [f"arch.item{i}" for i in range(14)]
    report = FindingReport(
        confidence=0,
        summary=Summary(critical=0, high=4, medium=2, low=0),
        securityAuditConfidence=96,
        reliabilityAuditConfidence=55,
        architectureAuditConfidence=35,
        coverage=CoverageBlock(missed=["sec.repo_hygiene_secrets", *missed]),
        issues=[
            _high("memory in find_near_clones", category="rel.edge_cases"),
            _high("cleanup in _run_mode", category="rel.error_recovery"),
            _high("find_near_clones is complex", category="arch.kiss"),
            _high("dedupe is complex", category="arch.kiss"),
            Issue(
                severity=Severity.MEDIUM,
                priority="P3",
                category="arch.structure_size",
                file="src/repolens/report.py",
                line=1,
                title="mega-file",
                explanation="long",
                recommendedFix="split",
            ),
        ],
    )
    text = "\n".join(low_audit_explanations(report))
    assert "Security audit" not in text
    assert "Reliability audit 55%" in text
    assert "4 High findings" in text
    assert "(−" not in text
    assert "mega-file" not in text
    assert "Architecture audit 35%" in text
    assert "14 checklist ids were not counted" in text
    assert "Each unanswered question is explained under Checklist." in text
    assert "2 High findings" in text
    assert "find_near_clones is complex" in text
    assert "Gate 0%" in text
    assert "architecture is the lowest band at 35%" in text
    brief = low_audit_brief(report)
    assert any("Reliability audit 55%" in line for line in brief)
    assert all("`arch.item0`" not in line for line in brief)


def test_zero_architecture_names_a_timed_out_pass() -> None:
    """One missed id is not why the band is 0% when the pass itself timed out."""
    report = FindingReport(
        confidence=0,
        summary=Summary(),
        securityAuditConfidence=100,
        reliabilityAuditConfidence=95,
        architectureAuditConfidence=0,
        coverage=CoverageBlock(missed=["arch.scores"]),
        durabilityGaps=[
            "llm.schema_invalid (pass: p3): LLM timed out after 7200s talking to the model."
        ],
        issues=[],
    )
    text = "\n".join(low_audit_explanations(report))
    assert "Architecture audit 0%: the checklist pass timed out" in text
    assert "1 checklist id was not counted" in text
    assert "Architecture audit 0%: 1 checklist id was not counted" not in text


def test_low_audit_notes_stay_empty_when_scores_are_high() -> None:
    report = FindingReport(
        confidence=88,
        summary=Summary(),
        securityAuditConfidence=96,
        reliabilityAuditConfidence=90,
        architectureAuditConfidence=91,
        coverage=CoverageBlock(missed=[]),
        issues=[],
    )
    assert low_audit_explanations(report) == []
    assert low_audit_brief(report) == []
