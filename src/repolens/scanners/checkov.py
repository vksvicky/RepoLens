"""Checkov IaC policy adapter (Phase 6.1)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.schema import Issue, ScannerRun, Severity

_SEV = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "INFO": Severity.LOW,
    "UNKNOWN": Severity.LOW,
}


def _severity(raw: str | None) -> Severity:
    return _SEV.get((raw or "MEDIUM").upper(), Severity.MEDIUM)


def _rel_path(file_path: str, *, root: Path | None) -> str:
    raw = (file_path or "unknown").strip()
    if root is not None:
        try:
            return str(Path(raw).resolve().relative_to(root.resolve()))
        except (ValueError, OSError):
            pass
    if raw.startswith("/"):
        return raw.lstrip("/")
    return raw


def _failed_checks_from_payload(data: Any) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, dict):
            for item in results.get("failed_checks") or []:
                if isinstance(item, dict):
                    failed.append(item)
        return failed
    if isinstance(data, list):
        for block in data:
            if isinstance(block, dict):
                failed.extend(_failed_checks_from_payload(block))
    return failed


def parse_checkov_report(
    data: dict[str, Any] | list[Any],
    *,
    root: Path | None = None,
) -> list[Issue]:
    """Map Checkov JSON (``checkov -o json``) into RepoLens Issues."""
    issues: list[Issue] = []
    for item in _failed_checks_from_payload(data):
        check_id = str(item.get("check_id") or "CKV")
        name = str(item.get("check_name") or check_id)
        repo_path = str(item.get("repo_file_path") or item.get("file_path") or "unknown")
        file_path = _rel_path(repo_path, root=root)
        line = 1
        rng = item.get("file_line_range")
        if isinstance(rng, (list, tuple)) and rng:
            try:
                line = max(int(rng[0]), 1)
            except (TypeError, ValueError):
                line = 1
        guideline = str(item.get("guideline") or "").strip()
        issues.append(
            Issue(
                severity=_severity(str(item.get("severity") or "")),
                priority="P1",
                category="checkov",
                file=file_path or "unknown",
                line=line,
                title=f"{check_id}: {name}"[:200],
                explanation=name + (f"\n{guideline}" if guideline else ""),
                impact="IaC misconfiguration can expose cloud resources or weaken controls.",
                recommendedFix=(
                    f"Remediate {check_id} in {file_path}"
                    + (f" (see {guideline})" if guideline else ".")
                ),
                codeExample=(
                    f"# Fix Checkov finding {check_id}\n"
                    f"# File: {file_path}"
                    + (f"\n# Guideline: {guideline}" if guideline else "")
                ),
                fixTiming="before launch",
            )
        )
    return issues


def run_checkov(root: Path) -> ScannerResult:
    """Run Checkov against ``root`` and parse JSON output."""
    binary = resolve_binary("checkov", candidates=("checkov",))
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="checkov", status="skipped", detail="not found on PATH or cache")
        )
    completed = subprocess.run(
        [
            str(binary),
            "-d",
            str(root),
            "-o",
            "json",
            "--quiet",
            "--compact",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="checkov",
                status="failed",
                detail=(completed.stderr or completed.stdout or "checkov failed")[:300],
            )
        )
    raw = (completed.stdout or "").strip()
    if not raw:
        return ScannerResult(run=ScannerRun(tool="checkov", status="ran", findingCount=0))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="checkov", status="failed", detail="invalid JSON output")
        )
    issues = parse_checkov_report(data, root=root)
    return ScannerResult(
        run=ScannerRun(tool="checkov", status="ran", findingCount=len(issues)),
        issues=issues,
    )
