"""Trivy filesystem / config scanner adapter (Phase 6.1)."""

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
    "UNKNOWN": Severity.LOW,
}


def _severity(raw: str | None) -> Severity:
    return _SEV.get((raw or "MEDIUM").upper(), Severity.MEDIUM)


def _vulnerability_fix(pkg: str, installed: str, fixed: str, vuln_id: str) -> str:
    upgrade = f"Upgrade {pkg}"
    if installed:
        upgrade += f" from {installed}"
    if fixed:
        upgrade += f" to {fixed}"
    else:
        upgrade += " to a non-vulnerable version"
    return f"{upgrade} (see {vuln_id})."


def _vulnerability_issue(target: str, vuln: dict[str, Any]) -> Issue:
    vuln_id = str(vuln.get("VulnerabilityID") or "CVE")
    pkg = str(vuln.get("PkgName") or "package")
    title = str(vuln.get("Title") or vuln_id)
    fixed = str(vuln.get("FixedVersion") or "").strip()
    installed = str(vuln.get("InstalledVersion") or "").strip()
    desc = str(vuln.get("Description") or title)
    return Issue(
        severity=_severity(str(vuln.get("Severity") or "")),
        priority="P1",
        category="trivy",
        file=target,
        line=1,
        title=f"{vuln_id} in {pkg}: {title}"[:200],
        explanation=desc[:2000],
        impact=(
            "Known vulnerable dependency or package may be exploitable in production."
        ),
        recommendedFix=_vulnerability_fix(pkg, installed, fixed, vuln_id),
        codeExample=(
            f"# Upgrade {pkg}"
            + (f" to {fixed}" if fixed else "")
            + f"\n# Advisory: {vuln_id}"
        ),
        fixTiming="before launch",
        cwe=None,
        packageName=pkg,
        installedVersion=installed or None,
        fixedVersion=fixed or None,
        advisoryId=vuln_id,
    )


def _misconfig_line(mis: dict[str, Any]) -> int:
    cause = mis.get("CauseMetadata") or {}
    if not isinstance(cause, dict):
        return 1
    try:
        return max(int(cause.get("StartLine") or 1), 1)
    except (TypeError, ValueError):
        return 1


def _misconfig_issue(target: str, mis: dict[str, Any]) -> Issue:
    mis_id = str(mis.get("ID") or mis.get("AvdID") or "misconfig")
    title = str(mis.get("Title") or mis_id)
    desc = str(mis.get("Description") or title)
    url = str(mis.get("PrimaryURL") or "").strip()
    return Issue(
        severity=_severity(str(mis.get("Severity") or "")),
        priority="P1",
        category="trivy",
        file=target,
        line=_misconfig_line(mis),
        title=f"{mis_id}: {title}"[:200],
        explanation=desc[:2000] + (f"\n{url}" if url else ""),
        impact="Infrastructure or container misconfiguration increases attack surface.",
        recommendedFix=(
            f"Remediate {mis_id} in {target}" + (f" (see {url})" if url else ".")
        ),
        codeExample=(
            f"# Fix misconfiguration {mis_id} in {target}\n"
            f"# Follow scanner guidance"
            + (f": {url}" if url else "")
        ),
        fixTiming="before launch",
    )


def parse_trivy_report(data: dict[str, Any]) -> list[Issue]:
    """Map Trivy JSON (``trivy fs --format json``) into RepoLens Issues."""
    issues: list[Issue] = []
    for result in data.get("Results") or []:
        if not isinstance(result, dict):
            continue
        target = str(result.get("Target") or "unknown")
        for vuln in result.get("Vulnerabilities") or []:
            if isinstance(vuln, dict):
                issues.append(_vulnerability_issue(target, vuln))
        for mis in result.get("Misconfigurations") or []:
            if isinstance(mis, dict):
                issues.append(_misconfig_issue(target, mis))
    return issues


def run_trivy(root: Path) -> ScannerResult:
    """Run ``trivy fs`` (vulns + misconfig) as JSON against ``root``."""
    binary = resolve_binary("trivy")
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="trivy", status="skipped", detail="not found on PATH or cache")
        )
    completed = subprocess.run(
        [
            str(binary),
            "fs",
            "--scanners",
            "vuln,misconfig,secret",
            "--format",
            "json",
            "--quiet",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    # Trivy exits 0 normally; some versions use non-zero on findings — accept 0/1.
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="trivy",
                status="failed",
                detail=(completed.stderr or completed.stdout or "trivy failed")[:300],
            )
        )
    raw = (completed.stdout or "").strip()
    if not raw:
        return ScannerResult(run=ScannerRun(tool="trivy", status="ran", findingCount=0))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="trivy", status="failed", detail="invalid JSON output")
        )
    if not isinstance(data, dict):
        data = {}
    issues = parse_trivy_report(data)
    return ScannerResult(
        run=ScannerRun(tool="trivy", status="ran", findingCount=len(issues)),
        issues=issues,
    )
