"""Self-contained HTML for the full P1–P3 gate report. No pandoc. No network."""

from __future__ import annotations

from html import escape
from pathlib import Path

from repolens.schema import FindingReport, Issue

_BANDS = (
    ("P1", "P1 — Security"),
    ("P2", "P2 — Bugs, reliability, performance"),
    ("P3", "P3 — Architecture & quality"),
)


def _finding(issue: Issue) -> str:
    return (
        '<article class="finding">'
        f"<h3>{escape(issue.severity.value)} — {escape(issue.title)}</h3>"
        f"<p><code>{escape(issue.file)}:{issue.line}</code></p>"
        f"<p>{escape(issue.explanation)}</p>"
        f"<p><strong>Impact:</strong> {escape(issue.impact)}</p>"
        f"<p><strong>Fix:</strong> {escape(issue.recommendedFix)}</p>"
        f"<pre>{escape(issue.codeExample)}</pre>"
        "</article>"
    )


def _band(report: FindingReport, priority: str, label: str) -> str:
    rows = [
        issue
        for issue in report.issues
        if issue.priority == priority and issue.source != "llm"
    ]
    body = (
        "".join(_finding(issue) for issue in rows)
        if rows
        else "<p><em>No findings in this band.</em></p>"
    )
    return f"<section><h2>{escape(label)}</h2>{body}</section>"


def render_full_report_html(report: FindingReport) -> str:
    """One HTML document for the full gate report. The style is embedded."""
    sections = "".join(_band(report, priority, label) for priority, label in _BANDS)
    counts = report.summary
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>RepoLens gate report</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto;
       line-height: 1.45; }}
h1, h2 {{ font-family: system-ui, sans-serif; }}
h2 {{ border-bottom: 1px solid #ccc; }}
article {{ margin: 1rem 0; padding: 0.75rem 0; }}
pre {{ white-space: pre-wrap; font-family: ui-monospace, monospace; }}
@media print {{ body {{ margin: 1rem; }} }}
</style></head><body>
<h1>RepoLens gate report</h1>
<p>Gate confidence {report.confidence}%. Critical {counts.critical}, High {counts.high},
Medium {counts.medium}, Low {counts.low}.</p>
{sections}
</body></html>
"""


def write_full_report_html(report: FindingReport, dest: Path) -> Path:
    """Write the full gate report to ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_full_report_html(report), encoding="utf-8")
    return dest
