"""SCA enrichment: CVE dedupe, CycloneDX SBOM, license summary (Phase 6.2)."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from repolens.scanners.base import resolve_binary
from repolens.schema import Issue, SupplyChainBlock

logger = logging.getLogger(__name__)

_CVE_RE = re.compile(r"\b(CVE-\d{4}-\d{4,}|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4})\b", re.I)
_PKG_IN_TITLE_RE = re.compile(
    r"\b(?:in|for)\s+([A-Za-z0-9_.@/+\-]+)",
    re.I,
)
_COPYLEFT_MARKERS = (
    "GPL",
    "AGPL",
    "LGPL",
    "SSPL",
    "OSL",
    "CPAL",
    "EUPL",
)


def advisory_id(title: str) -> str | None:
    match = _CVE_RE.search(title or "")
    return match.group(1).upper() if match else None


def _package_hint(title: str) -> str:
    match = _PKG_IN_TITLE_RE.search(title or "")
    if not match:
        return ""
    return match.group(1).strip().lower()


def _sca_key(issue: Issue) -> str | None:
    if issue.category not in {"osv", "trivy"}:
        return None
    adv = advisory_id(issue.title)
    if not adv:
        return None
    pkg = _package_hint(issue.title)
    return f"{adv}|{pkg}"


def dedupe_sca_issues(issues: list[Issue]) -> list[Issue]:
    """Drop duplicate OSV/Trivy rows for the same advisory (+ package hint).

    Prefer ``osv`` over ``trivy`` when both report the same CVE. Non-SCA
    categories (checkov, gitleaks, semgrep, …) are always kept.
    """
    # First pass: prefer osv for each key
    best: dict[str, Issue] = {}
    order: list[str] = []
    passthrough: list[Issue] = []
    for issue in issues:
        key = _sca_key(issue)
        if key is None:
            passthrough.append(issue)
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = issue
            order.append(key)
            continue
        # Prefer osv; otherwise keep the first
        if existing.category != "osv" and issue.category == "osv":
            best[key] = issue
    return passthrough + [best[k] for k in order]


def parse_cyclonedx_license_summary(
    bom: dict[str, Any],
    *,
    limit: int = 40,
) -> list[str]:
    """Compact license lines from a CycloneDX JSON document."""
    notes: list[str] = []
    components = bom.get("components") or []
    if not isinstance(components, list):
        return notes
    for comp in components:
        if not isinstance(comp, dict):
            continue
        name = str(comp.get("name") or "package")
        version = str(comp.get("version") or "").strip()
        label = f"{name}@{version}" if version else name
        licenses = comp.get("licenses") or []
        if not isinstance(licenses, list) or not licenses:
            continue
        ids: list[str] = []
        for entry in licenses:
            if not isinstance(entry, dict):
                continue
            lic = entry.get("license") or entry.get("expression")
            if isinstance(lic, str):
                ids.append(lic)
            elif isinstance(lic, dict):
                ids.append(str(lic.get("id") or lic.get("name") or "unknown"))
        if not ids:
            continue
        joined = ", ".join(ids)
        risk = ""
        upper = joined.upper()
        if any(marker in upper for marker in _COPYLEFT_MARKERS):
            risk = " [copyleft — review distribution obligations]"
        notes.append(f"{label}: {joined}{risk}")
        if len(notes) >= limit:
            break
    return notes


def write_trivy_sbom(
    root: Path,
    out_dir: Path,
    *,
    filename: str = "sbom.cdx.json",
) -> tuple[Path | None, str]:
    """Write a CycloneDX SBOM via ``trivy fs --format cyclonedx``.

    Returns ``(path, detail)``. Path is None when skipped/failed.
    """
    binary = resolve_binary("trivy")
    if binary is None:
        return None, "trivy not found on PATH or cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / filename
    completed = subprocess.run(
        [
            str(binary),
            "fs",
            "--format",
            "cyclonedx",
            "--quiet",
            "-o",
            str(dest),
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    if completed.returncode not in {0, 1} or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "trivy sbom failed")[:300]
        return None, detail
    return dest, f"CycloneDX SBOM written ({dest.name})"


def load_license_summary_from_sbom(sbom_path: Path) -> list[str]:
    """Read license notes from an on-disk CycloneDX JSON SBOM."""
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return []
    if not isinstance(data, dict):
        return []
    return parse_cyclonedx_license_summary(data)


def collect_license_ids(bom: dict[str, Any], *, limit: int = 80) -> list[str]:
    """Distinct license ids/names from a CycloneDX document (sorted)."""
    seen: set[str] = set()
    components = bom.get("components") or []
    if not isinstance(components, list):
        return []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        licenses = comp.get("licenses") or []
        if not isinstance(licenses, list):
            continue
        for entry in licenses:
            if not isinstance(entry, dict):
                continue
            lic = entry.get("license") or entry.get("expression")
            if isinstance(lic, str) and lic.strip():
                seen.add(lic.strip())
            elif isinstance(lic, dict):
                label = str(lic.get("id") or lic.get("name") or "").strip()
                if label:
                    seen.add(label)
            if len(seen) >= limit:
                break
        if len(seen) >= limit:
            break
    return sorted(seen)


def build_supply_chain(
    root: Path,
    out_dir: Path,
    *,
    sbom: bool = True,
    licenses: bool = True,
) -> tuple[SupplyChainBlock | None, list[str]]:
    """Write SBOM (when Trivy available) and populate license summary.

    Returns ``(block, gaps)``. Block is None when both features are off or
    nothing could be produced.
    """
    if not sbom and not licenses:
        return None, []
    gaps: list[str] = []
    notes: list[str] = []
    license_ids: list[str] = []
    sbom_path: Path | None = None
    detail = ""

    if sbom or licenses:
        sbom_path, detail = write_trivy_sbom(root, out_dir)
        if sbom_path is None:
            if sbom:
                gaps.append(f"SBOM skipped: {detail}")
                logger.info("SBOM skipped: %s", detail)
        else:
            notes.append(detail)

    if licenses and sbom_path is not None:
        try:
            data = json.loads(sbom_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            gaps.append(f"License summary failed: {exc}")
            data = None
        if isinstance(data, dict):
            license_ids = collect_license_ids(data)
            notes.extend(parse_cyclonedx_license_summary(data))
            if not license_ids and not any(":" in n for n in notes):
                notes.append("No component licenses found in SBOM")

    if sbom_path is None and not notes and not license_ids:
        return None, gaps

    rel = sbom_path.name if sbom_path is not None else None
    return (
        SupplyChainBlock(
            sbomPath=rel if sbom else None,
            sbomFormat="cyclonedx" if sbom and sbom_path is not None else None,
            licenses=license_ids if licenses else [],
            notes=notes,
        ),
        gaps,
    )
