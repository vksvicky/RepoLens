"""Audit confidence formulas (gate + band-specific)."""

from __future__ import annotations

from repolens.coverage import CoverageResult
from repolens.metrics import AuditMetrics, compute_audit_metrics, compute_band_confidence
from repolens.schema import FindingReport, ScannerRun, Summary


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
    assert metrics.security_audit_confidence < 95
    # Gate must not exceed the lowest band confidence
    bands = [
        metrics.security_audit_confidence,
        metrics.architecture_audit_confidence,
        metrics.reliability_audit_confidence,
    ]
    assert metrics.gate_confidence <= min(bands)
    assert metrics.gate_confidence <= min(95, 90, 92)


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
