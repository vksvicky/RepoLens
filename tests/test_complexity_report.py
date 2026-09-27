# tests/test_complexity_report.py
"""B6 — Markdown Top-10 complexity hotspots table."""

from __future__ import annotations

from repolens.report import render_markdown
from repolens.schema import (
    ComplexityBlock,
    ComplexityHotspot,
    FindingReport,
    Summary,
)


def test_render_markdown_includes_top10_complexity_table() -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        complexity=ComplexityBlock(
            functionsAnalysed=50,
            issueCount=2,
            maxCyclomatic=40,
            maxCognitive=30,
            p95Cyclomatic=18,
            p95Cognitive=20,
            hotspots=[
                ComplexityHotspot(
                    file="a.py",
                    function="big",
                    line=10,
                    cyclomatic=40,
                    cognitive=30,
                ),
                ComplexityHotspot(
                    file="b.py",
                    function="mid",
                    line=3,
                    cyclomatic=12,
                    cognitive=16,
                ),
            ],
        ),
    )
    md = render_markdown(report, mode="full", commit_go="go", push_go="go")
    assert "## Complexity (Fast Brain)" in md
    assert "| File | Function | Line | Cyclomatic | Cognitive |" in md
    assert "| `a.py` | `big` | 10 | 40 | 30 |" in md
    assert "p95 cyclomatic" in md.lower() or "| P95 cyclomatic |" in md
    assert "not a sonar server" in md.lower()
