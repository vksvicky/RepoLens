"""Markdown report writer."""

from __future__ import annotations

from pathlib import Path

from repolens.report import write_markdown_report
from repolens.schema import FindingReport, Issue, ScannerRun, Severity, Summary


def test_write_markdown_report_includes_sections(tmp_path: Path) -> None:
    report = FindingReport(
        schemaVersion="1.0",
        confidence=70,
        summary=Summary(critical=0, high=1, medium=0, low=0),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="Secrets",
                file="app.py",
                line=3,
                title="Hardcoded API key",
                explanation="Key embedded in source.",
                impact="Credential theft.",
                recommendedFix="Move to environment variable.",
                codeExample='key = os.environ["API_KEY"]',
                fixTiming="immediately",
            )
        ],
        durabilityGaps=["ci"],
        scannerRuns=[ScannerRun(tool="gitleaks", status="ran", findingCount=1)],
    )
    path = write_markdown_report(report, tmp_path, mode="sentinel")
    text = path.read_text(encoding="utf-8")
    assert path.name.startswith("gate_review_report_")
    assert "## Gate verdict" in text
    assert "Confidence:** 70%" in text or "**Confidence:** 70%" in text
    assert "Hardcoded API key" in text
    assert "key = os.environ" in text
    assert "## Durability gaps" in text
    assert "## Automated scanners" in text
    assert "gitleaks" in text
