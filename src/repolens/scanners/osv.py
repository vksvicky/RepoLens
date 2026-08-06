"""OSV-Scanner dependency CVE adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.schema import Issue, ScannerRun, Severity


def run_osv(root: Path) -> ScannerResult:
    binary = resolve_binary("osv", candidates=("osv-scanner", "osv"))
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="osv", status="skipped", detail="not found on PATH or cache")
        )
    completed = subprocess.run(
        [str(binary), "scan", "--format", "json", "-r", str(root)],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    # osv-scanner exits 1 when vulns found
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="osv",
                status="failed",
                detail=(completed.stderr or completed.stdout or "osv-scanner failed")[:300],
            )
        )
    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="osv", status="failed", detail="invalid JSON output")
        )
    issues: list[Issue] = []
    results = data.get("results") or []
    for result in results:
        source = (result.get("source") or {}).get("path") or "dependencies"
        for pkg in result.get("packages") or []:
            package = pkg.get("package") or {}
            pkg_name = str(package.get("name") or "package")
            for vuln in pkg.get("vulnerabilities") or []:
                vuln_id = str(vuln.get("id") or "CVE")
                summary = str(vuln.get("summary") or vuln_id)
                issues.append(
                    Issue(
                        severity=Severity.HIGH,
                        priority="P1",
                        category="osv",
                        file=str(source),
                        line=1,
                        title=f"{vuln_id} in {pkg_name}",
                        explanation=summary,
                        impact="Known vulnerable dependency may be exploitable in production.",
                        recommendedFix=(
                            f"Upgrade {pkg_name} to a non-vulnerable version "
                            f"(see {vuln_id})."
                        ),
                        codeExample=(
                            f"# Upgrade dependency {pkg_name}\n"
                            f"# Refer to advisory {vuln_id} for fixed versions"
                        ),
                        fixTiming="before launch",
                        cwe=None,
                        packageName=pkg_name,
                        advisoryId=vuln_id,
                    )
                )
    return ScannerResult(
        run=ScannerRun(tool="osv", status="ran", findingCount=len(issues)),
        issues=issues,
    )
