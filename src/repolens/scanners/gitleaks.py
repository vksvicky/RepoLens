"""gitleaks secrets adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.schema import Issue, ScannerRun, Severity


def run_gitleaks(root: Path) -> ScannerResult:
    binary = resolve_binary("gitleaks")
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="gitleaks", status="skipped", detail="not found on PATH or cache")
        )
    completed = subprocess.run(
        [
            str(binary),
            "detect",
            "--source",
            str(root),
            "--no-git",
            "-f",
            "json",
            "-r",
            "/dev/stdout",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    # gitleaks exits 1 when secrets found
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="gitleaks",
                status="failed",
                detail=(completed.stderr or completed.stdout or "gitleaks failed")[:300],
            )
        )
    raw = completed.stdout.strip()
    if not raw:
        return ScannerResult(run=ScannerRun(tool="gitleaks", status="ran", findingCount=0))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="gitleaks", status="failed", detail="invalid JSON output")
        )
    if not isinstance(data, list):
        data = []
    issues: list[Issue] = []
    for item in data:
        file_path = str(item.get("File") or item.get("file") or "unknown")
        line = int(item.get("StartLine") or item.get("line") or 1)
        rule = str(item.get("RuleID") or item.get("Description") or "secret")
        desc = str(item.get("Description") or rule)
        issues.append(
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="gitleaks",
                file=file_path,
                line=max(line, 1),
                title=f"Secret detected: {rule}",
                explanation=desc,
                impact="Credential exposure can enable account takeover or data theft.",
                recommendedFix=(
                    "Remove the secret, rotate it, and load from a secret manager / env."
                ),
                codeExample='value = os.environ["SECRET_NAME"]  # do not hardcode',
                fixTiming="immediately",
            )
        )
    return ScannerResult(
        run=ScannerRun(tool="gitleaks", status="ran", findingCount=len(issues)),
        issues=issues,
    )
