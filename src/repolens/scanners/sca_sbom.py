"""CycloneDX SBOM write and license summary."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from repolens.scanners.base import resolve_binary
from repolens.schema import SupplyChainBlock

logger = logging.getLogger(__name__)

_COPYLEFT_MARKERS = (
    "GPL",
    "AGPL",
    "LGPL",
    "SSPL",
    "OSL",
    "CPAL",
    "EUPL",
)


def _summary_license_ids(licenses: Any) -> list[str]:
    if not isinstance(licenses, list):
        return []
    ids: list[str] = []
    for entry in licenses:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license") or entry.get("expression")
        if isinstance(lic, str):
            ids.append(lic)
        elif isinstance(lic, dict):
            ids.append(str(lic.get("id") or lic.get("name") or "unknown"))
    return ids


def _license_note(comp: dict[str, Any]) -> str | None:
    name = str(comp.get("name") or "package")
    version = str(comp.get("version") or "").strip()
    label = f"{name}@{version}" if version else name
    ids = _summary_license_ids(comp.get("licenses") or [])
    if not ids:
        return None
    joined = ", ".join(ids)
    risk = ""
    if any(marker in joined.upper() for marker in _COPYLEFT_MARKERS):
        risk = " [copyleft — review distribution obligations]"
    return f"{label}: {joined}{risk}"


def parse_cyclonedx_license_summary(
    bom: dict[str, Any],
    *,
    limit: int = 40,
) -> list[str]:
    """Compact license lines from a CycloneDX JSON document."""
    components = bom.get("components") or []
    if not isinstance(components, list):
        return []
    notes: list[str] = []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        note = _license_note(comp)
        if note is None:
            continue
        notes.append(note)
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


def _remember_license(entry: Any, seen: set[str]) -> None:
    if not isinstance(entry, dict):
        return
    lic = entry.get("license") or entry.get("expression")
    if isinstance(lic, str) and lic.strip():
        seen.add(lic.strip())
        return
    if isinstance(lic, dict):
        label = str(lic.get("id") or lic.get("name") or "").strip()
        if label:
            seen.add(label)


def collect_license_ids(bom: dict[str, Any], *, limit: int = 80) -> list[str]:
    """Distinct license ids/names from a CycloneDX document (sorted)."""
    components = bom.get("components") or []
    if not isinstance(components, list):
        return []
    seen: set[str] = set()
    for comp in components:
        if not isinstance(comp, dict):
            continue
        licenses = comp.get("licenses") or []
        if not isinstance(licenses, list):
            continue
        for entry in licenses:
            _remember_license(entry, seen)
            if len(seen) >= limit:
                return sorted(seen)
        if len(seen) >= limit:
            return sorted(seen)
    return sorted(seen)


def _licenses_from_sbom(sbom_path: Path) -> tuple[list[str], list[str], str | None]:
    """Return ``(license ids, notes, error)`` from an on-disk CycloneDX file."""
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return [], [], f"License summary failed: {exc}"
    if not isinstance(data, dict):
        return [], [], None
    license_ids = collect_license_ids(data)
    notes = parse_cyclonedx_license_summary(data)
    if not license_ids and not any(":" in note for note in notes):
        notes.append("No component licenses found in SBOM")
    return license_ids, notes, None


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
        ids, extra_notes, error = _licenses_from_sbom(sbom_path)
        if error:
            gaps.append(error)
        license_ids = ids
        notes.extend(extra_notes)

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
