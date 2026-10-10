"""Client-ready audit-diff Markdown/HTML (#108)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.diff_audit import (
    diff_audit_reports,
    render_diff_audit_html,
    render_diff_audit_md,
)
from repolens.schema import (
    ComplexityBlock,
    FindingReport,
    GraphBlock,
    Issue,
    Severity,
    Summary,
)

runner = CliRunner()


def _issue(title: str, *, sev: Severity = Severity.MEDIUM) -> Issue:
    high = sev in (Severity.CRITICAL, Severity.HIGH)
    return Issue(
        severity=sev,
        priority="P1" if high else "P2",
        category="sec.x" if high else "rel.x",
        file="a.py",
        line=1,
        title=title,
        explanation="e",
        impact="Business impact" if high else "",
        recommendedFix="fix",
        codeExample="fixed()" if high else "",
    )


def _pair() -> tuple[FindingReport, FindingReport]:
    left = FindingReport(
        confidence=70,
        summary=Summary(medium=2, high=1),
        issues=[_issue("Old"), _issue("Stay"), _issue("Leak", sev=Severity.HIGH)],
        graph=GraphBlock(status="ok", cyclicity=4, cycleCount=1),
        complexity=ComplexityBlock(issueCount=10, maxCyclomatic=20),
    )
    right = FindingReport(
        confidence=80,
        summary=Summary(medium=2),
        issues=[_issue("Stay"), _issue("New")],
        graph=GraphBlock(status="ok", cyclicity=0, cycleCount=0),
        complexity=ComplexityBlock(issueCount=6, maxCyclomatic=14),
    )
    return left, right


def test_markdown_has_closed_new_debt_sections() -> None:
    left, right = _pair()
    result = diff_audit_reports(left, right)
    md = render_diff_audit_md(result, left=left, right=right)
    assert "Closed findings" in md
    assert "New regressions" in md
    assert "Debt drift" in md
    assert "Old" in md
    assert "New" in md
    assert "cyclicity" in md.lower()
    assert "4 → 0" in md or "4 -> 0" in md
    assert "complexity" in md.lower()


def test_html_is_one_page_client_update() -> None:
    left, right = _pair()
    result = diff_audit_reports(left, right)
    html = render_diff_audit_html(result, left=left, right=right)
    assert "Closed findings" in html
    assert "New regressions" in html
    assert "Debt drift" in html
    assert "<html" in html.lower()


def test_cli_diff_audit_markdown_out(tmp_path: Path) -> None:
    left, right = _pair()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(left.model_dump_json(), encoding="utf-8")
    b.write_text(right.model_dump_json(), encoding="utf-8")
    out = tmp_path / "diff.md"
    result = runner.invoke(
        app, ["diff-audit", str(a), str(b), "--format", "md", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Closed findings" in text
