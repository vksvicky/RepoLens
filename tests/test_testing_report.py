# tests/test_testing_report.py
"""F1 — Markdown testing inventory section."""

from __future__ import annotations

from repolens.report import render_markdown
from repolens.schema import FindingReport, Summary, TestingInventoryBlock


def test_render_includes_testing_inventory() -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        testing=TestingInventoryBlock(
            testFileCount=5,
            testCaseCount=142,
            productionFunctionCount=80,
            testsPerProductionFunction=1.78,
        ),
    )
    md = render_markdown(report, mode="full", commit_go="go", push_go="go")
    assert "## Testing inventory (Fast Brain)" in md
    assert "| Test files | 5 |" in md
    assert "| Test cases | 142 |" in md
    assert "1.78" in md
