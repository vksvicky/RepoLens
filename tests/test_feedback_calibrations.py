"""Phase 6.7: feed FP calibrations from local feedback events."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.feedback_store import apply_feedback_calibrations, record_feedback
from repolens.schema import Issue, Severity


def _issue(
    *,
    category: str = "sec.injection",
    file: str = "src/a.py",
    source: str = "llm",
    severity: Severity = Severity.HIGH,
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category=category,
        file=file,
        line=1,
        title="demo",
        explanation="x",
        recommendedFix="fix",
        source=source,  # type: ignore[arg-type]
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "Attacker may exploit this."
        kwargs["codeExample"] = "return safe()"
    return Issue(**kwargs)


def test_file_category_false_positive_demotes_llm(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        category="sec.injection",
        file="src/a.py",
        title="demo",
    )
    out = apply_feedback_calibrations(
        [_issue(), _issue(source="scanner")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.LOW
    assert "[calibrated: feedback_false_positive]" in out[0].explanation
    assert out[1].severity == Severity.HIGH  # scanner untouched


def test_category_needs_two_events(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        reason="false_positive",
        category="sec.xss",
        file="other.py",
    )
    # Only one category-level event → no demote for different file
    out = apply_feedback_calibrations(
        [_issue(category="sec.xss", file="src/b.py")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.HIGH

    record_feedback(
        tmp_path,
        stable_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        reason="false_positive",
        category="sec.xss",
        file="third.py",
    )
    out = apply_feedback_calibrations(
        [_issue(category="sec.xss", file="src/b.py")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.LOW


def test_feedback_calibrations_can_disable(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        category="sec.injection",
        file="src/a.py",
    )
    out = apply_feedback_calibrations(
        [_issue()],
        tmp_path,
        DeepConfig(feedback_calibrations=False),
    )
    assert out[0].severity == Severity.HIGH
