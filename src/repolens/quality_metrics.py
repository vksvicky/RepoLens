"""Optional quality counts stored beside cyclicity in baseline.json (C4)."""

from __future__ import annotations

from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.graph.types import GraphResult, GraphStatus


def measure_quality_metrics(
    root: Path,
    cfg: RepoLensConfig,
    graph: GraphResult,
) -> dict[str, int]:
    """Count architecture violations, complexity issues, and near-clone clusters."""
    boundary = 0
    if graph.status is GraphStatus.OK:
        from repolens.architecture import (
            ArchitectureLoadError,
            discover_architecture_path,
            load_architecture,
            verify_boundaries,
        )

        arch_path = discover_architecture_path(root, explicit=None)
        if arch_path is not None:
            try:
                doc = load_architecture(arch_path)
                boundary = len(verify_boundaries(graph, doc))
            except ArchitectureLoadError:
                boundary = 0

    from repolens.complexity.runner import run_complexity
    from repolens.heuristics.near_clones import find_near_clones
    from repolens.inventory import scan_inventory

    inv = scan_inventory(
        root,
        mode="full",
        max_files=cfg.fast_brain.max_files,
        skip_globs=cfg.deep.skip_paths,
    )
    hotspots = len(
        run_complexity(
            root,
            inv.files,
            enabled=cfg.complexity.enabled,
            hotspot_limit=cfg.complexity.hotspot_limit,
        ).issues
    )
    clones = find_near_clones(inv.files, config=cfg.fast_brain.near_clones)
    return {
        "boundaryViolations": boundary,
        "complexityHotspots": hotspots,
        "nearClonePairs": int(clones.cluster_count),
    }
