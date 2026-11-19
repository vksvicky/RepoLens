"""Self-contained HTML for the full gate report (#163)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.executive_summary import render_executive_summary_html
from repolens.schema import FindingReport, Issue, Severity, Summary

runner = CliRunner()


def _issue(priority: str, title: str) -> Issue:
    return Issue(
        severity=Severity.HIGH if priority == "P1" else Severity.MEDIUM,
        priority=priority,  # type: ignore[arg-type]
        category="demo",
        file="src/app.py",
        line=4,
        title=title,
        explanation=f"{title} needs a change",
        impact=f"{title} can fail the gate",
        recommendedFix="Change the code",
        codeExample="print(1)\n",
        source="scanner",
    )


def _report() -> FindingReport:
    return FindingReport(
        confidence=80,
        summary=Summary(high=1, medium=1),
        issues=[
            _issue("P1", "Secret in a log line"),
            _issue("P2", "Unchecked return value"),
        ],
    )


def _write_pair(tmp_path: Path) -> Path:
    report = _report()
    stem = tmp_path / "gate_review_report_review_2026-11-19_1700"
    stem.with_suffix(".json").write_text(report.model_dump_json(), encoding="utf-8")
    stem.with_suffix(".md").write_text("# Gate review\n", encoding="utf-8")
    return stem.with_suffix(".json")


def test_full_report_html_shows_two_priorities_without_network() -> None:
    from repolens.report_html import render_full_report_html

    html = render_full_report_html(_report())
    assert "P1 — Security" in html
    assert "P2 — Bugs, reliability, performance" in html
    assert "Secret in a log line" in html
    assert "Unchecked return value" in html
    assert "<style>" in html
    assert "<link" not in html
    assert "<script" not in html
    assert "http://" not in html
    assert "https://" not in html
    board = render_executive_summary_html(_report())
    assert "RepoLens executive summary" in board
    assert "RepoLens gate report" not in board


def test_export_report_html_accepts_markdown_sibling(tmp_path: Path) -> None:
    json_path = _write_pair(tmp_path)
    dest = tmp_path / "out" / "gate.html"
    result = runner.invoke(
        app,
        ["export", str(json_path.with_suffix(".md")), "--report-html", str(dest)],
    )
    assert result.exit_code == 0, result.output
    text = dest.read_text(encoding="utf-8")
    assert "Secret in a log line" in text
    assert "Unchecked return value" in text


def test_report_html_cannot_combine_with_evidence_pack(tmp_path: Path) -> None:
    json_path = _write_pair(tmp_path)
    result = runner.invoke(
        app,
        [
            "export", str(json_path),
            "--report-html", str(tmp_path / "gate.html"),
            "--evidence-pack",
        ],
    )
    assert result.exit_code == 2
    assert "cannot be combined" in result.output
    assert not (tmp_path / "gate.html").exists()
