"""Trivy filesystem / config scanner adapter (Phase 6.1)."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.scanners.trivy_env import (
    INCOMPLETE_AUTH_DETAIL,
    redact_secrets,
    registry_auth_incomplete,
    trivy_child_env,
)
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


def _trivy_config(root: Path, trivy_cfg: Any) -> Any:
    if trivy_cfg is not None:
        return trivy_cfg
    from repolens.config import load_config

    return load_config(root).scanners.trivy


def _run_trivy_fs(
    *,
    binary: Path,
    root: Path,
    child: dict[str, str],
    env_src: Mapping[str, str],
) -> ScannerResult | list[Issue]:
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
        env=child,
    )
    if completed.returncode not in {0, 1}:
        raw = (completed.stderr or completed.stdout or "trivy failed")[:300]
        return ScannerResult(
            run=ScannerRun(
                tool="trivy",
                status="failed",
                detail=redact_secrets(raw, env_src),
            )
        )
    raw = (completed.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(
                tool="trivy",
                status="failed",
                detail="invalid JSON output",
            )
        )
    if not isinstance(data, dict):
        data = {}
    return parse_trivy_report(data)


def _run_trivy_images(
    *,
    binary: Path,
    root: Path,
    images: list,
    child: dict[str, str],
    env_src: Mapping[str, str],
) -> tuple[list[Issue], list[str]]:
    issues: list[Issue] = []
    details: list[str] = []
    for ref in images:
        image = str(ref).strip()
        if not image:
            continue
        img = subprocess.run(
            [
                str(binary),
                "image",
                "--format",
                "json",
                "--quiet",
                image,
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=root,
            env=child,
        )
        if img.returncode not in {0, 1}:
            fail = redact_secrets(
                (img.stderr or img.stdout or "trivy image failed")[:300], env_src
            )
            details.append(f"{image}: {fail}")
            continue
        payload = (img.stdout or "").strip()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            details.append(f"{image}: invalid JSON output")
            continue
        if isinstance(data, dict):
            issues.extend(parse_trivy_report(data))
    return issues, details


def run_trivy(
    root: Path,
    *,
    trivy_cfg: Any | None = None,
    environ: Mapping[str, str] | None = None,
) -> ScannerResult:
    """Run ``trivy fs`` (and optional ``trivy image``) as JSON against ``root``."""
    env_src = environ if environ is not None else os.environ
    cfg = _trivy_config(root, trivy_cfg)
    if cfg.pass_registry_env and registry_auth_incomplete(env_src):
        return ScannerResult(
            run=ScannerRun(
                tool="trivy",
                status="failed",
                detail=INCOMPLETE_AUTH_DETAIL,
            )
        )
    binary = resolve_binary("trivy")
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="trivy", status="skipped", detail="not found on PATH or cache")
        )
    child = trivy_child_env(env_src, pass_registry_env=cfg.pass_registry_env)
    fs_result = _run_trivy_fs(binary=binary, root=root, child=child, env_src=env_src)
    if isinstance(fs_result, ScannerResult):
        return fs_result
    issues = list(fs_result)
    image_issues, details = _run_trivy_images(
        binary=binary,
        root=root,
        images=cfg.images,
        child=child,
        env_src=env_src,
    )
    issues.extend(image_issues)
    detail = redact_secrets("; ".join(details), env_src) if details else ""
    return ScannerResult(
        run=ScannerRun(
            tool="trivy",
            status="ran",
            findingCount=len(issues),
            detail=detail,
        ),
        issues=issues,
    )
