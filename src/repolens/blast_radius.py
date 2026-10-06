"""Expand a git change-set with direct import neighbours (blast radius)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from repolens.inventory import FileEntry


def _rel_to_module(relative: str) -> str | None:
    norm = relative.replace("\\", "/").removesuffix(".py")
    if not norm or norm.endswith("/__init__"):
        norm = norm.removesuffix("/__init__")
    if not norm or any(part.startswith(".") for part in Path(norm).parts):
        return None
    return norm.replace("/", ".")


def _module_to_candidates(module: str) -> list[str]:
    parts = module.replace(".", "/")
    return [f"{parts}.py", f"{parts}/__init__.py"]


@dataclass(frozen=True)
class BlastRadiusResult:
    paths: list[str]
    note: str | None = None


def expand_blast_radius_paths(
    root: Path,
    changed_paths: Sequence[str],
    entries: Sequence[FileEntry],
    *,
    enabled: bool = True,
) -> list[str]:
    return expand_blast_radius(root, changed_paths, entries, enabled=enabled).paths


def expand_blast_radius(
    root: Path,
    changed_paths: Sequence[str],
    entries: Sequence[FileEntry],
    *,
    enabled: bool = True,
) -> BlastRadiusResult:
    """Return changed ∪ direct imports ∪ direct importers (Python via grimp).

    Non-Python changed paths are kept as-is. Failures keep the change-set and
    set ``note`` so operators see that expansion did not run.
    """
    base = [p.replace("\\", "/") for p in changed_paths]
    if not enabled or not base:
        return BlastRadiusResult(paths=list(base))
    try:
        from repolens.config import load_config
        from repolens.graph.build import analyse_python_graph
        from repolens.graph.query import direct_dependencies, direct_dependents
        from repolens.graph.types import GraphStatus
    except ImportError:
        return BlastRadiusResult(
            paths=list(base),
            note="blast-radius skipped: graph imports unavailable",
        )

    cfg = load_config(root)
    try:
        result = analyse_python_graph(root, config=cfg.graph)
    except Exception as exc:
        return BlastRadiusResult(
            paths=list(base),
            note=f"blast-radius skipped: graph failed ({exc})",
        )
    if result.status != GraphStatus.OK:
        gaps = "; ".join(result.durability_gaps[:3]) or result.status.value
        return BlastRadiusResult(
            paths=list(base),
            note=f"blast-radius skipped: graph {gaps}",
        )

    by_rel = {e.relative.replace("\\", "/"): e for e in entries}
    wanted: set[str] = set(base)
    for rel in list(base):
        mod = _rel_to_module(rel)
        if mod is None:
            continue
        neighbours = set(direct_dependencies(result, mod)) | set(
            direct_dependents(result, mod)
        )
        for neighbour in neighbours:
            for cand in _module_to_candidates(neighbour):
                if cand in by_rel:
                    wanted.add(cand)
    ordered: list[str] = []
    seen: set[str] = set()
    for path in list(base) + sorted(wanted):
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    extra = len(ordered) - len(base)
    note = None
    if extra:
        note = f"blast-radius added {extra} neighbour path(s)"
    return BlastRadiusResult(paths=ordered, note=note)


def filter_entries_blast_radius(
    entries: Sequence[FileEntry],
    paths: Iterable[str],
) -> list[FileEntry]:
    wanted = {p.replace("\\", "/") for p in paths}
    return [e for e in entries if e.relative.replace("\\", "/") in wanted]
