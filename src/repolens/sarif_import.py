# src/repolens/sarif_import.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from repolens.schema import Issue, ScannerRun, Severity

_LEVEL = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "note": Severity.LOW,
    "none": Severity.LOW,
}

_URI_BASE_PREFIXES = ("%SRCROOT%/", "%PROJECTROOT%/", "%SRCROOT%", "%PROJECTROOT%")


@dataclass(frozen=True)
class SarifImportResult:
    tool_name: str
    issues: list[Issue]
    skipped: int
    detail: str = ""


def _strip_uri_base_prefix(raw: str) -> str:
    text = raw.strip()
    upper = text.upper()
    for prefix in _URI_BASE_PREFIXES:
        if upper.startswith(prefix.upper()):
            return text[len(prefix) :].lstrip("/")
    return text


def _norm_uri_to_rel(uri: str, *, root: Path) -> str | None:
    raw = _strip_uri_base_prefix((uri or "").strip())
    if not raw:
        return None
    if raw.startswith("file:"):
        parsed = urlparse(raw)
        raw = unquote(parsed.path)
        # Windows file:///C:/... → path may start with /C:/
        if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
            raw = raw[1:]
    path = Path(raw)
    root_res = root.resolve()
    if path.is_absolute():
        try:
            rel = path.resolve().relative_to(root_res)
        except ValueError:
            return None
    else:
        rel = PurePosixPath(raw.replace("\\", "/"))
        if ".." in rel.parts:
            return None
        candidate = (root_res / Path(*rel.parts)).resolve()
        try:
            candidate.relative_to(root_res)
        except ValueError:
            return None
        rel = candidate.relative_to(root_res)
    out = rel.as_posix().lstrip("./")
    return out or None


def _message(result: dict[str, Any]) -> str:
    msg = result.get("message") or {}
    if isinstance(msg, dict):
        return str(msg.get("text") or msg.get("markdown") or "").strip()
    return str(msg).strip()


def _rule_id(result: dict[str, Any]) -> str:
    nested = result.get("rule")
    nested_id = nested.get("id") if isinstance(nested, dict) else None
    return str(result.get("ruleId") or nested_id or "rule")


def _level(result: dict[str, Any]) -> Severity:
    level = str(result.get("level") or "warning").lower()
    return _LEVEL.get(level, Severity.MEDIUM)


def _region_line(loc: dict[str, Any]) -> int:
    region = (loc.get("physicalLocation") or {}).get("region") or {}
    line = int(region.get("startLine") or 1)
    return max(line, 1)


def _snippet(loc: dict[str, Any]) -> str:
    region = (loc.get("physicalLocation") or {}).get("region") or {}
    snip = region.get("snippet") or {}
    if isinstance(snip, dict):
        return str(snip.get("text") or "").strip()
    return ""


def _issues_from_run(
    run: dict[str, Any], *, root: Path, path_name: str
) -> tuple[str, list[Issue], int]:
    driver = ((run.get("tool") or {}).get("driver") or {})
    tool_name = str(driver.get("name") or "sarif")
    issues: list[Issue] = []
    skipped = 0
    for result in run.get("results") or []:
        if not isinstance(result, dict):
            skipped += 1
            continue
        locations = result.get("locations") or []
        if not locations:
            skipped += 1
            continue
        loc0 = locations[0] if isinstance(locations[0], dict) else {}
        uri = ((loc0.get("physicalLocation") or {}).get("artifactLocation") or {}).get(
            "uri"
        ) or ""
        rel = _norm_uri_to_rel(str(uri), root=root)
        if rel is None:
            skipped += 1
            continue
        severity = _level(result)
        rule_id = _rule_id(result)
        message = _message(result) or rule_id
        snippet = _snippet(loc0)
        impact = ""
        code = ""
        if severity in {Severity.CRITICAL, Severity.HIGH}:
            impact = (
                f"Imported {tool_name} finding ({rule_id}); "
                "confirm exploitability in this codebase."
            )
            code = (
                f"# Address {tool_name} / {rule_id}\n"
                f"# {message[:200]}\n"
                + (f"# snippet: {snippet[:120]}\n" if snippet else "")
            )
        issues.append(
            Issue(
                severity=severity,
                priority="P1"
                if severity in {Severity.CRITICAL, Severity.HIGH}
                else "P2",
                category=f"sarif.{tool_name}".replace(" ", "_")[:80],
                file=rel,
                line=_region_line(loc0),
                title=f"{tool_name}: {rule_id}",
                explanation=message,
                impact=impact,
                recommendedFix=(
                    f"Remediate per {tool_name} rule `{rule_id}`, then re-scan."
                ),
                codeExample=code,
                fixTiming="before launch"
                if severity in {Severity.CRITICAL, Severity.HIGH}
                else "if time permits",
                source="scanner",
                anchorQuote=snippet or None,
                evidenceSources=[f"sarif:{tool_name}", path_name],
            )
        )
    return tool_name, issues, skipped


def load_sarif_issues(path: Path, *, root: Path) -> list[SarifImportResult]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [
            SarifImportResult(
                tool_name="sarif", issues=[], skipped=0, detail=str(exc)[:300]
            )
        ]

    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list) or not runs:
        return [
            SarifImportResult(
                tool_name="sarif", issues=[], skipped=0, detail="no runs"
            )
        ]

    out: list[SarifImportResult] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        tool_name, issues, skipped = _issues_from_run(
            run, root=root, path_name=path.name
        )
        out.append(
            SarifImportResult(
                tool_name=tool_name, issues=issues, skipped=skipped
            )
        )
    return out or [
        SarifImportResult(tool_name="sarif", issues=[], skipped=0, detail="no runs")
    ]


def load_many_sarif(paths: list[Path], *, root: Path) -> list[SarifImportResult]:
    merged: list[SarifImportResult] = []
    for p in paths:
        merged.extend(load_sarif_issues(p, root=root))
    return merged


def scanner_runs_from_imports(results: list[SarifImportResult]) -> list[ScannerRun]:
    return [
        ScannerRun(
            tool=f"sarif:{r.tool_name}",
            status="ran" if r.issues or not r.detail else "failed",
            findingCount=len(r.issues),
            detail=r.detail or (f"skipped {r.skipped}" if r.skipped else ""),
        )
        for r in results
    ]
