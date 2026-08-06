"""Anchored SARIF 2.1.0 export (Phase 6.4).

Only emits results with verified locations:
- ``source=scanner`` → trust reported file/line (still path-safe)
- otherwise → require resolvable ``anchorQuote``
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repolens import __version__
from repolens.anchor import AnchorLocation, resolve_anchor
from repolens.schema import FindingReport, Issue, Severity

_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
}


def _safe_rel(root: Path, relative: str) -> str | None:
    rel = relative.replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return rel


def verify_issue_location(root: Path, issue: Issue) -> AnchorLocation | None:
    """Return a verified location or None (and stamp ``locationVerified``)."""
    rel = _safe_rel(root, issue.file)
    if rel is None:
        issue.locationVerified = False
        return None

    if issue.source == "scanner":
        if issue.line < 1:
            issue.locationVerified = False
            return None
        # Prefer anchor quote when present (still scanner-trusted path)
        if issue.anchorQuote and issue.anchorQuote.strip():
            loc = resolve_anchor(
                root, rel, issue.anchorQuote, hint_line=issue.line
            )
            if loc is not None:
                issue.locationVerified = True
                return loc
        issue.locationVerified = True
        return AnchorLocation(
            relative=rel,
            start_line=issue.line,
            end_line=issue.line,
            start_column=1,
            quote=issue.anchorQuote or "",
        )

    quote = (issue.anchorQuote or "").strip()
    if not quote:
        issue.locationVerified = False
        return None
    loc = resolve_anchor(root, rel, quote, hint_line=issue.line)
    issue.locationVerified = loc is not None
    return loc


def _rule_id(issue: Issue) -> str:
    if issue.cwe:
        return issue.cwe.replace(" ", "")
    cat = (issue.category or "finding").replace(" ", ".")
    return f"repolens/{cat}"


def _result_for(issue: Issue, loc: AnchorLocation) -> dict[str, Any]:
    region: dict[str, Any] = {"startLine": loc.start_line}
    if loc.end_line != loc.start_line:
        region["endLine"] = loc.end_line
    if loc.start_column:
        region["startColumn"] = loc.start_column
    if loc.end_column is not None:
        region["endColumn"] = loc.end_column

    message = issue.title
    if issue.explanation:
        message = f"{issue.title}: {issue.explanation[:400]}"

    result: dict[str, Any] = {
        "ruleId": _rule_id(issue),
        "level": _LEVEL.get(issue.severity, "warning"),
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": loc.relative},
                    "region": region,
                }
            }
        ],
    }
    if issue.stableId or issue.runId:
        result["partialFingerprints"] = {
            k: v
            for k, v in {
                "repolens/stableId": issue.stableId,
                "repolens/runId": issue.runId,
            }.items()
            if v
        }
    return result


def build_sarif_log(report: FindingReport, root: Path) -> dict[str, Any]:
    """Build a SARIF 2.1.0 log; mutates issues' ``locationVerified`` flags."""
    results: list[dict[str, Any]] = []
    rules: dict[str, dict[str, Any]] = {}
    for issue in report.issues:
        loc = verify_issue_location(root, issue)
        if loc is None:
            continue
        rid = _rule_id(issue)
        if rid not in rules:
            rules[rid] = {
                "id": rid,
                "name": issue.category or rid,
                "shortDescription": {"text": issue.title[:200]},
                "fullDescription": {
                    "text": (issue.explanation or issue.title)[:2000]
                },
                "defaultConfiguration": {
                    "level": _LEVEL.get(issue.severity, "warning")
                },
            }
            if issue.cwe:
                rules[rid]["properties"] = {"cwe": issue.cwe}
        results.append(_result_for(issue, loc))

    return {
        "$schema": (
            "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
            "master/Schemata/sarif-schema-2.1.0.json"
        ),
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "RepoLens",
                        "version": __version__,
                        "informationUri": "https://github.com/vksvicky/RepoLens",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
                "properties": {
                    "repolensGateConfidence": report.confidence,
                    "repolensLlmBypassed": report.llmBypassed,
                },
            }
        ],
    }


def write_sarif_report(
    report: FindingReport,
    root: Path,
    *,
    out_dir: Path,
    mode: str = "review",
) -> Path | None:
    """Write anchored SARIF next to other reports. Returns path written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    dest = out_dir / f"gate_review_report_{mode}_{stamp}.sarif.json"
    log = build_sarif_log(report, root)
    dest.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    return dest
