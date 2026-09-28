"""Small review helpers shared by the phase modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repolens.heuristics.runner import HeuristicResult

from pathlib import Path

from repolens.progress import ReviewProgress
from repolens.schema import (
    FindingReport,
)


def _attach_quality(
    report: FindingReport,
    *,
    heur_result: HeuristicResult | None,
    files_scanned: int,
) -> None:
    from repolens.quality import build_quality_scorecard_from_issues

    if files_scanned <= 0 or heur_result is None:
        return
    report.quality = build_quality_scorecard_from_issues(
        report.issues,
        near_clone_clusters=heur_result.near_clone_clusters,
        near_clone_occurrences=heur_result.near_clone_occurrences,
        files_scanned=files_scanned,
        notes=list(heur_result.near_clone_notes),
    )


def _attach_complexity(report: FindingReport, complexity_result) -> None:
    if complexity_result is None:
        return
    report.complexity = complexity_result.block


def _attach_testing(report: FindingReport, testing_result) -> None:
    if testing_result is None:
        return
    report.testing = testing_result.block


def _complexity_ai_prefix(root: Path, complexity_result, cfg) -> str:
    if complexity_result is None or not cfg.complexity.enabled:
        return ""
    from repolens.complexity.ai_pack import (
        format_complexity_ai_section,
        select_complexity_ai_targets,
    )

    targets = select_complexity_ai_targets(
        complexity_result.functions,
        top_n=cfg.complexity.top_n_ai_explanations,
    )
    return format_complexity_ai_section(root, targets)


def _extend_from_import_sarif(
    import_sarif: list[Path] | None,
    root: Path,
    scanner_issues: list,
    scanner_runs: list,
    prog: ReviewProgress,
    *,
    require: bool = False,
) -> None:
    if not import_sarif:
        return
    from repolens.sarif_import import load_many_sarif, scanner_runs_from_imports

    imported = load_many_sarif(list(import_sarif), root=root, require=require)
    for block in imported:
        scanner_issues.extend(block.issues)
        if block.skipped:
            prog.detail(
                f"SARIF import ({block.tool_name}): "
                f"skipped {block.skipped} result(s)"
            )
    scanner_runs.extend(scanner_runs_from_imports(imported))


def _git_sha(root: Path) -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    sha = (completed.stdout or "").strip()
    return sha or None
