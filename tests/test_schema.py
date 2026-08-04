"""Finding schema validation — Critical/High require impact + codeExample."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from repolens.schema import FindingReport, Issue, Severity


def _issue(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "severity": "HIGH",
        "priority": "P1",
        "category": "Authentication",
        "file": "src/auth.py",
        "line": 42,
        "title": "Missing authorization check",
        "explanation": "Route lacks role check.",
        "impact": "Any user can call admin actions.",
        "recommendedFix": "Add require_role('admin').",
        "codeExample": "def admin():\n    require_role('admin')\n",
        "fixTiming": "immediately",
    }
    base.update(overrides)
    return base


def test_valid_high_finding_accepted() -> None:
    report = FindingReport.model_validate(
        {
            "schemaVersion": "1.0",
            "confidence": 82,
            "summary": {"critical": 0, "high": 1, "medium": 0, "low": 0},
            "issues": [_issue()],
            "durabilityGaps": ["tests"],
            "scores": None,
        }
    )
    assert report.confidence == 82
    assert report.issues[0].severity == Severity.HIGH
    assert report.issues[0].codeExample


def test_critical_without_code_example_rejected() -> None:
    with pytest.raises(ValidationError):
        Issue.model_validate(_issue(severity="CRITICAL", codeExample=""))


def test_critical_without_impact_rejected() -> None:
    with pytest.raises(ValidationError):
        Issue.model_validate(_issue(severity="CRITICAL", impact=""))


def test_low_may_omit_code_example() -> None:
    issue = Issue.model_validate(
        _issue(severity="LOW", priority="P3", codeExample="", impact="Minor info leak.")
    )
    assert issue.severity == Severity.LOW


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        FindingReport.model_validate(
            {
                "schemaVersion": "1.0",
                "confidence": 101,
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "issues": [],
            }
        )
