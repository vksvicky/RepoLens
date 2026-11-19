"""Bitbucket Code Insights JSON for one FindingReport. No HTTP client."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.host_export import counts_as_trusted, export_path
from repolens.issue_ids import stable_id
from repolens.schema import FindingReport

BITBUCKET_INSIGHTS_NAME = "bitbucket-insights.json"


def bitbucket_insights_payload(report: FindingReport) -> dict:
    """One object with a report body and the annotation list CI will post."""
    annotations: list[dict] = []
    for issue in report.issues:
        path = export_path(issue.file)
        if path is None or issue.line < 1 or not counts_as_trusted(issue):
            continue
        annotations.append({
            "external_id": issue.stableId or stable_id(
                category=issue.category,
                file=issue.file,
                title=issue.title,
            ),
            "annotation_type": "BUG",
            "summary": issue.title,
            "severity": issue.severity.value,
            "path": path,
            "line": issue.line,
        })
    argv = report.provenance.expandedArgv if report.provenance is not None else []
    scanners_only = "--scanners-only" in argv
    failed = any(row["severity"] in {"CRITICAL", "HIGH"} for row in annotations)
    return {
        "report": {
            "title": "RepoLens",
            "details": "RepoLens gate report",
            "report_type": "SECURITY" if scanners_only else "BUG",
            "reporter": "RepoLens",
            "result": "FAILED" if failed else "PASSED",
        },
        "annotations": annotations,
    }


def write_bitbucket_insights(report: FindingReport, dest: Path) -> Path:
    """Write the Insights object. The same report always produces the same bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bitbucket_insights_payload(report), indent=2) + "\n"
    dest.write_text(text, encoding="utf-8")
    return dest
