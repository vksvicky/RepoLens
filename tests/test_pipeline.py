"""Pipeline helpers without network."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.config import ModelConfig, RepoLensConfig
from repolens.pipeline import fail_on_triggered, run_review
from repolens.playbooks import playbooks_for_mode
from repolens.schema import FindingReport, Issue, Severity, Summary


def test_fail_on_high_triggers() -> None:
    report = FindingReport(
        confidence=60,
        summary=Summary(high=1),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="Auth",
                file="a.py",
                line=1,
                title="t",
                explanation="e",
                impact="i",
                recommendedFix="f",
                codeExample="x=1",
            )
        ],
    )
    assert fail_on_triggered(report, "HIGH") is True
    assert fail_on_triggered(report, "CRITICAL") is False
    assert fail_on_triggered(report, None) is False


def test_playbooks_sentinel_security_only() -> None:
    books = playbooks_for_mode("sentinel")
    assert len(books) == 1
    assert books[0][0] == "P1 security"
    assert "security" in books[0][1].lower() or "P1" in books[0][1] or len(books[0][1]) > 50


def test_playbooks_review_has_three_bands() -> None:
    books = playbooks_for_mode("review", full_audit=False)
    assert len(books) == 3


def test_dry_run_pipeline(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(model=ModelConfig(provider=None))
    result = run_review(
        path=tmp_path,
        mode="sentinel",
        dry_run=True,
        config=cfg,
        out_dir=tmp_path / "r",
    )
    assert result.dry_run is True
    assert result.files_scanned >= 1
    assert result.markdown_path is not None


def test_fail_on_invalid_severity_raises() -> None:
    report = FindingReport(confidence=50, summary=Summary(), issues=[])
    with pytest.raises(ValueError):
        fail_on_triggered(report, "URGENT")
