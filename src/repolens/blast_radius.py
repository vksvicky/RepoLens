"""Expand a git change-set with direct import neighbours (blast radius)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
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


def expand_blast_radius_paths(
    root: Path,
    changed_paths: Sequence[str],
    entries: Sequence[FileEntry],
    *,
    enabled: bool = True,
) -> list[str]:
    """Return changed ∪ direct imports ∪ direct importers (Python via grimp).

    Non-Python changed paths are kept as-is. Failures soft-skip expansion.
    """
    base = [p.replace("\\", "/") for p in changed_paths]
    if not enabled or not base:
        return list(base)
    try:
        from repolens.config import load_config
        from repolens.graph.build import analyse_python_graph
        from repolens.graph.query import direct_dependencies, direct_dependents
        from repolens.graph.types import GraphStatus
    except ImportError:
        return list(base)

    cfg = load_config(root)
    try:
        result = analyse_python_graph(root, config=cfg.graph)
    except Exception:
        return list(base)
    if result.status != GraphStatus.OK:
        return list(base)

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
    # Preserve changed-first order, then sorted extras.
    ordered: list[str] = []
    seen: set[str] = set()
    for path in list(base) + sorted(wanted):
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def filter_entries_blast_radius(
    entries: Sequence[FileEntry],
    paths: Iterable[str],
) -> list[FileEntry]:
    wanted = {p.replace("\\", "/") for p in paths}
    return [e for e in entries if e.relative.replace("\\", "/") in wanted]
