"""``repolens view`` local HTML report viewer (#111)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.report_view import build_view_html
from repolens.schema import (
    FindingReport,
    GraphBlock,
    Issue,
    Severity,
    Summary,
)

runner = CliRunner()


def _report() -> FindingReport:
    return FindingReport(
        confidence=80,
        summary=Summary(high=1),
        securityAuditConfidence=80,
        reliabilityAuditConfidence=90,
        architectureAuditConfidence=85,
        graph=GraphBlock(status="ok", cyclicity=4, cycleCount=1, moduleCount=5),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="sec.x",
                file="a.py",
                line=1,
                title="Leak",
                explanation="e",
                impact="bad",
                recommendedFix="fix it",
                codeExample="fixed()",
                stableId="fp1",
            )
        ],
    )


def test_build_view_html_filterable_and_cycles() -> None:
    html = build_view_html(_report())
    assert "Leak" in html
    assert "filter" in html.lower() or "data-severity" in html
    assert "cyclicity" in html.lower() or "cycle" in html.lower()
    assert "<svg" in html.lower() or "graph" in html.lower()
    assert "fixed()" in html or "remediation" in html.lower()


def test_cli_view_writes_html(tmp_path: Path) -> None:
    report = _report()
    json_path = tmp_path / "gate_review_report_review_2026-10-10_1000.json"
    json_path.write_text(report.model_dump_json(), encoding="utf-8")
    out = tmp_path / "view.html"
    result = runner.invoke(
        app,
        ["view", str(json_path), "--out", str(out), "--no-open"],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert "Leak" in out.read_text(encoding="utf-8")
