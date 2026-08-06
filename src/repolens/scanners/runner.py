"""Run enabled scanners and collect results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from repolens.scanners.base import MANUAL_HINTS, ScannerResult
from repolens.scanners.checkov import run_checkov
from repolens.scanners.gitleaks import run_gitleaks
from repolens.scanners.osv import run_osv
from repolens.scanners.semgrep import run_semgrep
from repolens.scanners.trivy import run_trivy
from repolens.schema import Issue, ScannerRun
from repolens.triage import stamp_issue_sources

_RUNNERS = {
    "gitleaks": run_gitleaks,
    "semgrep": run_semgrep,
    "osv": run_osv,
    "trivy": run_trivy,
    "checkov": run_checkov,
}


def parse_scanners_flag(value: str | None, *, config_enabled: list[str]) -> list[str] | None:
    """Return tool list, or None to mean 'off'."""
    if value is None or value.strip().lower() == "auto":
        return list(config_enabled)
    if value.strip().lower() == "off":
        return None
    tools = [part.strip().lower() for part in value.split(",") if part.strip()]
    unknown = [t for t in tools if t not in _RUNNERS]
    if unknown:
        raise ValueError(f"Unknown scanner(s): {', '.join(unknown)}")
    return tools


def _run_one(tool: str, root: Path) -> tuple[str, ScannerResult | None, str | None]:
    runner = _RUNNERS.get(tool)
    if runner is None:
        return tool, None, "unknown tool"
    return tool, runner(root), None


def run_scanners(root: Path, tools: list[str]) -> tuple[list[ScannerRun], list[Issue], list[str]]:
    """Run scanners (in parallel when multiple) and stamp ``source=scanner``."""
    runs: list[ScannerRun] = []
    issues: list[Issue] = []
    gaps: list[str] = []
    if not tools:
        return runs, issues, gaps

    results_by_tool: dict[str, tuple[ScannerResult | None, str | None]] = {}
    if len(tools) == 1:
        tool, result, err = _run_one(tools[0], root)
        results_by_tool[tool] = (result, err)
    else:
        workers = min(len(tools), 5)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_one, tool, root): tool for tool in tools}
            for fut in as_completed(futures):
                tool, result, err = fut.result()
                results_by_tool[tool] = (result, err)

    for tool in tools:
        result, err = results_by_tool.get(tool, (None, "unknown tool"))
        if result is None:
            runs.append(
                ScannerRun(tool=tool, status="skipped", detail=err or "unknown tool")
            )
            gaps.append(f"scanner:{tool} missing — {MANUAL_HINTS.get(tool, 'install manually')}")
            continue
        runs.append(result.run)
        issues.extend(result.issues)
        if result.run.status == "skipped":
            gaps.append(
                f"scanner:{tool} missing — {MANUAL_HINTS.get(tool, 'install manually')}"
            )
        elif result.run.status == "failed":
            gaps.append(f"scanner:{tool} failed — {result.run.detail}")

    issues = stamp_issue_sources(issues)
    return runs, issues, gaps


def missing_required(tools: list[str], runs: list[ScannerRun]) -> list[str]:
    skipped = {r.tool for r in runs if r.status == "skipped"}
    return [t for t in tools if t in skipped]
