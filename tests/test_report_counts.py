"""Gate counts stay separate from model notes and repeated scanner reports."""

from __future__ import annotations

from repolens.report import format_collapsed_duplicates, render_markdown
from repolens.schema import FindingReport, Issue, Severity, Summary


def test_collapsed_duplicates_note_only_when_tools_overlap() -> None:
    plain = FindingReport(
        confidence=50,
        summary=Summary(critical=0, high=2, medium=0, low=0),
    )
    assert format_collapsed_duplicates(plain) is None

    same = FindingReport(
        confidence=50,
        summary=Summary(critical=1, high=1, medium=0, low=0),
        rawCriticalHighCount=2,
    )
    assert format_collapsed_duplicates(same) is None

    collapsed = FindingReport(
        confidence=50,
        summary=Summary(critical=0, high=2, medium=0, low=0),
        rawCriticalHighCount=4,
        rawTotalFindings=6,
    )
    assert format_collapsed_duplicates(collapsed) == (
        "2 extra reports of issues already counted above"
    )
    once = FindingReport(
        confidence=50,
        summary=Summary(critical=0, high=1, medium=0, low=0),
        rawCriticalHighCount=2,
    )
    assert format_collapsed_duplicates(once) == (
        "1 extra report of an issue already counted above"
    )
    note = Issue(
        severity=Severity.HIGH,
        priority="P2",
        category="rel.edge_cases",
        file="src/repolens/na_truth.py",
        line=31,
        title="Complex control flow",
        explanation="The model described a long function.",
        impact="harder to change",
        recommendedFix="split",
        codeExample="def smaller():\n    return 1\n",
        source="llm",
    )
    notes_only = FindingReport(
        confidence=50,
        summary=Summary(),
        rawCriticalHighCount=2,
        issues=[note, note.model_copy(update={"file": "scripts/generate_learn_file_notes.py"})],
    )
    assert format_collapsed_duplicates(notes_only) is None


def test_render_markdown_mentions_merge_without_a_combined_severity() -> None:
    report = FindingReport(
        confidence=60,
        summary=Summary(critical=0, high=2, medium=1, low=0),
        rawCriticalHighCount=4,
        rawTotalFindings=6,
        securityAuditConfidence=70,
    )
    md = render_markdown(report, mode="review", commit_go="go", push_go="no-go")
    assert "Same issue, counted once" in md
    assert "2 extra reports of issues already counted above" in md
    assert "not retained" not in md
    assert "tool rows evaluated" not in md
    assert "Unique Critical/High" not in md
    assert "High 2" in md
    assert "Medium 1" in md


def test_model_note_is_visible_and_not_counted() -> None:
    measured = Issue(
        severity="MEDIUM",
        priority="P2",
        category="heuristic.mega_file",
        file="tests/test_deep.py",
        line=1,
        title="Mega-file",
        explanation="513 lines",
        recommendedFix="split",
        source="heuristic",
    )
    note = Issue(
        severity="HIGH",
        priority="P2",
        category="arch.readability_complexity",
        file="src/repolens/report.py",
        line=407,
        title="Function is overly complex",
        explanation="The model estimated a high score.",
        impact="harder to change",
        recommendedFix="split",
        codeExample="def smaller():\n    return 1\n",
        source="llm",
    )
    report = FindingReport(
        confidence=95,
        summary=Summary(),
        issues=[measured, note],
    )
    report.summary = report.recount_summary()
    md = render_markdown(report, mode="review", commit_go="go", push_go="go")
    assert report.summary.high == 0
    assert report.summary.medium == 1
    assert report.summary.low == 0
    assert "Function is overly complex" in md
    assert "## Model notes" in md
    assert "do not change Critical, High, Medium, or Low" in md
