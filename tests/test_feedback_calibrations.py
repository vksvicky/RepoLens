"""Phase 6.7 + #30: feed FP calibrations from local feedback events."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.feedback_store import (
    apply_feedback_calibrations,
    derive_path_pattern,
    normalize_title,
    record_feedback,
)
from repolens.schema import Issue, Severity


def _issue(
    *,
    category: str = "sec.injection",
    file: str = "src/a.py",
    title: str = "demo",
    source: str = "llm",
    severity: Severity = Severity.HIGH,
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category=category,
        file=file,
        line=1,
        title=title,
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
    assert "feedback_false_positive" in out[0].explanation
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


def test_derive_path_pattern_dev_prefix() -> None:
    assert derive_path_pattern("scripts/dev_foo.py") == "scripts/dev_*.py"
    assert derive_path_pattern("src/util.py") is None


def test_path_pattern_demotes_sibling_files(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        category="sec.injection",
        file="scripts/dev_legacy.py",
        title="shell=True in helper",
    )
    # Auto-derived scripts/dev_*.py should demote sibling
    out = apply_feedback_calibrations(
        [
            _issue(file="scripts/dev_new.py", category="sec.injection"),
            _issue(file="src/prod.py", category="sec.injection"),
            _issue(file="scripts/dev_other.py", category="sec.xss"),
        ],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.LOW
    assert "path_pattern:" in out[0].explanation
    assert out[1].severity == Severity.HIGH  # wrong path
    assert out[2].severity == Severity.HIGH  # wrong category


def test_explicit_path_pattern(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        category="quality.nesting",
        file="tests/fixtures/deep.py",
        path_pattern="tests/fixtures/*.py",
    )
    out = apply_feedback_calibrations(
        [_issue(category="quality.nesting", file="tests/fixtures/other.py")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.LOW


def test_title_cluster_needs_two(tmp_path: Path) -> None:
    assert normalize_title("Shell injection on line 12") == normalize_title(
        "Shell injection on line 40"
    )
    record_feedback(
        tmp_path,
        stable_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        reason="false_positive",
        category="sec.injection",
        file="a.py",
        title="Shell injection on line 12",
    )
    out = apply_feedback_calibrations(
        [_issue(category="sec.injection", file="b.py", title="Shell injection on line 99")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.HIGH  # one title event insufficient

    record_feedback(
        tmp_path,
        stable_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        reason="false_positive",
        category="sec.injection",
        file="c.py",
        title="Shell injection on line 40",
    )
    out = apply_feedback_calibrations(
        [
            _issue(
                category="sec.injection",
                file="d.py",
                title="Shell injection on line 7",
            ),
            # Unrelated category must not be suppressed by injection title cluster
            _issue(category="sec.xss", file="e.py", title="Shell injection on line 7"),
        ],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.LOW
    assert "title_cluster" in out[0].explanation or "category_cluster" in out[0].explanation
    assert out[1].severity == Severity.HIGH


def test_scanner_never_pattern_demoted(tmp_path: Path) -> None:
    record_feedback(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        category="sec.injection",
        file="scripts/dev_a.py",
        path_pattern="scripts/dev_*.py",
    )
    out = apply_feedback_calibrations(
        [_issue(source="scanner", file="scripts/dev_b.py")],
        tmp_path,
        DeepConfig(),
    )
    assert out[0].severity == Severity.HIGH
