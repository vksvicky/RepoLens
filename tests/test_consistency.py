"""Phase 6.7: Critical/High self-consistency."""

from __future__ import annotations

from repolens.config import DeepConfig
from repolens.consistency import apply_heuristic_consistency
from repolens.schema import Issue, Severity


def _issue(
    *,
    severity: Severity = Severity.CRITICAL,
    source: str = "llm",
    verified: bool | None = False,
) -> Issue:
    return Issue(
        severity=severity,
        priority="P1",
        category="sec.injection",
        file="a.py",
        line=1,
        title="Bad",
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="fix",
        codeExample="return safe()",
        source=source,  # type: ignore[arg-type]
        locationVerified=verified,
    )


def test_heuristic_demotes_unverified_critical_llm() -> None:
    cfg = DeepConfig(critical_consistency="heuristic")
    out = apply_heuristic_consistency([_issue()], cfg)
    assert out[0].severity == Severity.HIGH
    assert "[unconfirmed: location]" in out[0].explanation


def test_heuristic_skips_verified_and_scanners() -> None:
    cfg = DeepConfig(critical_consistency="heuristic")
    issues = [
        _issue(verified=True),
        _issue(source="scanner", verified=False),
    ]
    out = apply_heuristic_consistency(issues, cfg)
    assert out[0].severity == Severity.CRITICAL
    assert out[1].severity == Severity.CRITICAL


def test_heuristic_off_is_noop() -> None:
    cfg = DeepConfig(critical_consistency="off")
    out = apply_heuristic_consistency([_issue()], cfg)
    assert out[0].severity == Severity.CRITICAL


def test_include_high() -> None:
    cfg = DeepConfig(
        critical_consistency="heuristic",
        critical_consistency_include_high=True,
    )
    out = apply_heuristic_consistency(
        [_issue(severity=Severity.HIGH, verified=False)], cfg
    )
    assert out[0].severity == Severity.MEDIUM
