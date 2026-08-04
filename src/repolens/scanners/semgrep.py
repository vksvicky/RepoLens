"""Semgrep SAST adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.schema import Issue, ScannerRun, Severity

_SEV = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}


def run_semgrep(root: Path) -> ScannerResult:
    binary = resolve_binary("semgrep")
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="semgrep", status="skipped", detail="not found on PATH or cache")
        )
    completed = subprocess.run(
        [str(binary), "scan", "--config", "auto", "--json", "--quiet", str(root)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="semgrep",
                status="failed",
                detail=(completed.stderr or completed.stdout or "semgrep failed")[:300],
            )
        )
    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="semgrep", status="failed", detail="invalid JSON output")
        )
    results = data.get("results") or []
    issues: list[Issue] = []
    for item in results:
        extra = item.get("extra") or {}
        severity = _SEV.get(str(extra.get("severity", "WARNING")).upper(), Severity.MEDIUM)
        path = str(item.get("path") or "unknown")
        line = int((item.get("start") or {}).get("line") or 1)
        check_id = str(item.get("check_id") or "semgrep")
        message = str(extra.get("message") or check_id)
        code = ""
        if severity in {Severity.CRITICAL, Severity.HIGH}:
            code = f"# Address Semgrep finding {check_id}\n# See: {message[:200]}"
        issues.append(
            Issue(
                severity=severity,
                priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
                category="semgrep",
                file=path,
                line=max(line, 1),
                title=f"Semgrep: {check_id}",
                explanation=message,
                impact="Rule-based SAST hit; confirm exploitability in this codebase."
                if severity in {Severity.CRITICAL, Severity.HIGH}
                else "",
                recommendedFix="Follow the Semgrep guidance and add a regression test if fixed.",
                codeExample=code,
                fixTiming="before launch"
                if severity in {Severity.CRITICAL, Severity.HIGH}
                else "if time permits",
                owasp=None,
            )
        )
    return ScannerResult(
        run=ScannerRun(tool="semgrep", status="ran", findingCount=len(issues)),
        issues=issues,
    )
