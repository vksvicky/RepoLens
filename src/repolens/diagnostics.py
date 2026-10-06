"""Fast diagnostic stream for editors and CI (C1) — no LLM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repolens import __version__
from repolens.config import RepoLensConfig
from repolens.inventory import scan_inventory
from repolens.schema import Issue, Severity

_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
}


def collect_fast_issues(root: Path, cfg: RepoLensConfig) -> list[Issue]:
    """Heuristics + complexity + cycles + architecture violations. No model."""
    inv = scan_inventory(
        root,
        mode="full",
        max_files=cfg.fast_brain.max_files,
        skip_globs=cfg.deep.skip_paths,
    )
    from repolens.heuristics import run_heuristics

    heur = run_heuristics(
        root,
        inv.files,
        mega_file_lines=cfg.deep.mega_file_lines,
        mega_file_exclude_globs=cfg.deep.extra_skip_globs() or None,
        pack_ids=list(cfg.packs.enabled) or None,
        workers=cfg.fast_brain.parallel_workers,
        near_clones_config=cfg.fast_brain.near_clones,
    )
    issues: list[Issue] = list(heur.issues)
    from repolens.complexity.runner import run_complexity

    issues.extend(
        run_complexity(
            root,
            inv.files,
            enabled=cfg.complexity.enabled,
            hotspot_limit=cfg.complexity.hotspot_limit,
        ).issues
    )
    if any(Path(f.relative).suffix == ".py" for f in inv.files):
        from repolens.graph import analyse_repo_graph
        from repolens.graph.findings import cycles_to_issues
        from repolens.graph.types import GraphStatus

        gres = analyse_repo_graph(root, config=cfg.graph)
        if gres.status not in {GraphStatus.FAILED, GraphStatus.SKIPPED}:
            issues.extend(
                cycles_to_issues(
                    gres, critical_scc_size=cfg.graph.critical_scc_size
                )
            )
            from repolens.architecture import (
                ArchitectureLoadError,
                boundary_violations_to_issues,
                discover_architecture_path,
                load_architecture,
                verify_boundaries,
            )

            try:
                arch_path = discover_architecture_path(root, explicit=None)
            except ArchitectureLoadError:
                arch_path = None
            if arch_path is not None:
                try:
                    doc = load_architecture(arch_path)
                    issues.extend(
                        boundary_violations_to_issues(verify_boundaries(gres, doc))
                    )
                except ArchitectureLoadError:
                    pass
    return issues


def diagnostic_jsonl(issues: list[Issue]) -> str:
    lines: list[str] = []
    for issue in issues:
        row = {
            "path": issue.file,
            "line": issue.line,
            "ruleId": issue.category,
            "severity": str(issue.severity),
            "message": issue.title,
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def diagnostic_sarif(issues: list[Issue], *, root: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for issue in issues:
        rel = issue.file.replace("\\", "/").lstrip("./")
        results.append(
            {
                "ruleId": issue.category or "repolens",
                "level": _LEVEL.get(issue.severity, "warning"),
                "message": {"text": issue.title},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": rel, "uriBaseId": "%SRCROOT%"},
                            "region": {"startLine": max(1, issue.line)},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "RepoLens",
                        "version": __version__,
                        "informationUri": "https://github.com/vksvicky/RepoLens",
                    }
                },
                "originalUriBaseIds": {
                    "%SRCROOT%": {"uri": root.resolve().as_uri() + "/"}
                },
                "results": results,
            }
        ],
    }
