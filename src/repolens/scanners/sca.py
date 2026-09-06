"""SCA enrichment: CVE dedupe, CycloneDX SBOM, license summary (Phase 6.2)."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from repolens.scanners.base import resolve_binary
from repolens.schema import FindingReport, Issue, Severity, SupplyChainBlock

logger = logging.getLogger(__name__)

_ADVISORY_RE = re.compile(
    r"\b("
    r"CVE-\d{4}-\d{4,}"
    r"|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}"
    r"|RUSTSEC-\d{4}-\d+"
    r"|PYSEC-\d{4}-\d+"
    r"|GO-\d{4}-\d+"
    r")\b",
    re.I,
)
# Backward-compatible alias used by existing callers.
_CVE_RE = _ADVISORY_RE
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


def extract_advisory_id(text: str) -> str | None:
    """Return the first canonical advisory id in ``text``, or ``None``."""
    match = _ADVISORY_RE.search(text or "")
    if not match:
        return None
    return match.group(1).upper()


def advisory_id(title: str) -> str | None:
    return extract_advisory_id(title)


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


def _is_scanner_sca_issue(issue: Issue) -> bool:
    if (issue.source or "").strip().lower() == "scanner":
        return True
    return issue.category in {"osv", "trivy"}


def _is_llm_issue(issue: Issue) -> bool:
    if (issue.source or "").strip().lower() == "llm":
        return True
    # LLM deep passes often use sec.* categories without source stamped yet.
    if _is_scanner_sca_issue(issue):
        return False
    cat = (issue.category or "").strip().lower()
    return cat.startswith("sec.") or cat.startswith("rel.") or cat.startswith("arch.")


def _evidence_tag(issue: Issue) -> str:
    if issue.category in {"osv", "trivy"}:
        return issue.category
    source = (issue.source or "").strip().lower()
    if source in {"scanner", "llm", "heuristic"}:
        return source
    return (issue.category or "unknown").strip() or "unknown"


def _resolve_advisory(issue: Issue) -> str | None:
    if issue.advisoryId and issue.advisoryId.strip():
        return issue.advisoryId.strip().upper()
    return extract_advisory_id(f"{issue.title}\n{issue.explanation}")


def _resolve_package(issue: Issue) -> str:
    if issue.packageName and issue.packageName.strip():
        return issue.packageName.strip().lower()
    return _package_hint(issue.title)


def _resolve_ecosystem(issue: Issue) -> str:
    """Best-effort ecosystem for the cluster key (empty = unknown)."""
    adv = _resolve_advisory(issue) or ""
    if adv.startswith("RUSTSEC-"):
        return "crates"
    if adv.startswith("PYSEC-"):
        return "pypi"
    if adv.startswith("GO-"):
        return "go"
    path = (issue.file or "").replace("\\", "/").lower()
    base = path.rsplit("/", 1)[-1]
    if base in {"cargo.lock", "cargo.toml"} or path.endswith("/cargo.lock"):
        return "crates"
    if base in {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "package.json",
        "npm-shrinkwrap.json",
    }:
        return "npm"
    if base in {"go.mod", "go.sum"}:
        return "go"
    if (
        (base.startswith("requirements") and base.endswith(".txt"))
        or base in {"poetry.lock", "pipfile", "pipfile.lock", "setup.py"}
        or base == "pyproject.toml"
    ):
        return "pypi"
    if base in {"pom.xml", "build.gradle", "build.gradle.kts"}:
        return "maven"
    return ""


def _normalize_issue_path(path: str) -> str:
    return (path or "").strip().replace("\\", "/").lower().lstrip("./")


def _ecosystems_compatible(
    a: str,
    b: str,
    *,
    path_a: str = "",
    path_b: str = "",
) -> bool:
    """Equal ecosystems match; known↔unknown may pair; unknown↔unknown needs same path."""
    if a and b:
        return a == b
    if a or b:
        # One side resolved (e.g. package-lock.json → npm); other is source code.
        return True
    # Both unknown: only merge when the normalized file paths match.
    na = _normalize_issue_path(path_a)
    nb = _normalize_issue_path(path_b)
    if not na or not nb:
        return False
    return na == nb


def _prefer_cross_source_primary(candidate: Issue, existing: Issue) -> bool:
    """True if candidate should replace existing (scanner baseline wins)."""
    cand_scan = _is_scanner_sca_issue(candidate)
    exist_scan = _is_scanner_sca_issue(existing)
    if cand_scan and not exist_scan:
        return True
    if exist_scan and not cand_scan:
        return False
    if cand_scan and exist_scan:
        if candidate.category == "osv" and existing.category != "osv":
            return True
    return False


def _identity_key(issue: Issue) -> tuple[str, str, str] | None:
    advisory = _resolve_advisory(issue)
    if advisory is None:
        return None
    return (_resolve_ecosystem(issue), _resolve_package(issue), advisory)


def dedupe_cross_source_sca_issues(
    issues: list[Issue],
) -> tuple[list[Issue], int, int]:
    """Collapse scanner+LLM rows for the same ecosystem/package/advisory.

    Returns ``(deduped_issues, raw_critical_high, raw_total)``.
    Only collapses when a scanner row and an LLM row share a compatible
    identity; same-source duplicates are left alone (OSV↔Trivy already
    handled by :func:`dedupe_sca_issues`). Output preserves input order.
    """
    raw_total = len(issues)
    raw_critical_high = sum(
        1
        for issue in issues
        if issue.severity in {Severity.CRITICAL, Severity.HIGH}
    )

    slots: list[Issue | None] = list(issues)
    consumed: set[int] = set()

    for i, scanner in enumerate(issues):
        if i in consumed or not _is_scanner_sca_issue(scanner):
            continue
        s_key = _identity_key(scanner)
        if s_key is None:
            continue
        s_eco, s_pkg, s_adv = s_key
        evidence = [_evidence_tag(scanner)]
        primary = scanner
        merged_any = False

        for j, other in enumerate(issues):
            if j == i or j in consumed:
                continue
            if not _is_llm_issue(other):
                continue
            o_key = _identity_key(other)
            if o_key is None:
                continue
            o_eco, o_pkg, o_adv = o_key
            if o_adv != s_adv or o_pkg != s_pkg:
                continue
            if not _ecosystems_compatible(
                s_eco,
                o_eco,
                path_a=scanner.file,
                path_b=other.file,
            ):
                continue
            tag = _evidence_tag(other)
            if tag not in evidence:
                evidence.append(tag)
            if not s_eco and o_eco:
                s_eco = o_eco
            consumed.add(j)
            slots[j] = None
            merged_any = True

        if not merged_any:
            continue
        # Prefer osv over other scanners if somehow both present (rare here).
        if _prefer_cross_source_primary(scanner, primary):
            primary = scanner
        slots[i] = primary.model_copy(
            update={
                "evidenceSources": list(evidence),
                "advisoryId": primary.advisoryId or s_adv,
                "packageName": primary.packageName or (s_pkg or None),
            }
        )

    out = [issue for issue in slots if issue is not None]
    return out, raw_critical_high, raw_total


def apply_cross_source_sca_dedupe(report: FindingReport) -> FindingReport:
    """Collapse cross-source SCA rows on ``report`` and record raw tallies."""
    deduped, raw_ch, raw_total = dedupe_cross_source_sca_issues(list(report.issues))
    report.issues = deduped
    report.rawCriticalHighCount = raw_ch
    report.rawTotalFindings = raw_total
    report.summary = report.recount_summary()
    return report


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
