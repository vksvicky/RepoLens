"""G1: import-graph lane wired into run_review and Markdown report."""

from __future__ import annotations

from pathlib import Path

from repolens.pipeline import run_review
from repolens.progress import ReviewProgress
from repolens.report import render_markdown
from repolens.schema import FindingReport, GraphBlock, Summary

FIXTURES = Path(__file__).parent / "fixtures"


def test_scanners_only_includes_graph_findings(tmp_path: Path) -> None:
    root = FIXTURES / "graph_cycle_pkg"
    result = run_review(
        path=root,
        mode="sentinel",
        scanners="off",
        scanners_only=True,
        out_dir=tmp_path / "reports",
        fmt="json",
        progress=ReviewProgress(quiet=True),
    )
    assert result.report.graph is not None
    assert result.report.graph.cycleCount >= 1
    assert any(i.source == "graph" for i in result.report.issues)


def test_markdown_renders_import_graph_section() -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        graph=GraphBlock(
            status="ok",
            cyclicity=4,
            cycleCount=1,
            moduleCount=2,
            packageCount=1,
        ),
    )
    md = render_markdown(report, mode="sentinel", commit_go="go", push_go="go")
    assert "## Import graph" in md
    assert "| Cyclicity | 4 |" in md
    assert "not an architecture certification" in md
