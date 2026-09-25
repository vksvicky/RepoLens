"""Build import graph via grimp, tag edges, and compute gated SCCs."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import grimp

from repolens.config import GraphConfig
from repolens.graph.cycles import cyclicity, strongly_connected_components
from repolens.graph.discover import discover_packages
from repolens.graph.scope_tags import ScopeRanges, file_scope_ranges, line_in_ranges
from repolens.graph.types import (
    CycleGroup,
    EdgeKind,
    GraphResult,
    GraphStatus,
    ImportEdge,
    ImportScope,
)


def analyse_python_graph(root: Path, *, config: GraphConfig | None = None) -> GraphResult:
    cfg = config or GraphConfig()
    if not cfg.enabled:
        return GraphResult(status=GraphStatus.SKIPPED, durability_gaps=["graph: disabled"])

    root = root.resolve()
    configured = cfg.packages if cfg.packages else None
    packages, gaps = discover_packages(root, configured=configured)
    if not packages:
        return GraphResult(status=GraphStatus.FAILED, durability_gaps=list(gaps))

    path_extra: list[str] = []
    if (root / "src").is_dir():
        path_extra.append(str(root / "src"))
    path_extra.append(str(root))

    prepended: list[str] = []
    for entry in reversed(path_extra):
        if entry not in sys.path:
            sys.path.insert(0, entry)
            prepended.append(entry)

    try:
        graph = grimp.build_graph(
            *packages,
            exclude_type_checking_imports=(cfg.type_only == "ignore"),
            cache_dir=None,
        )
    except Exception as exc:
        return GraphResult(
            status=GraphStatus.FAILED,
            packages=packages,
            durability_gaps=[*gaps, f"graph.analysis_failed: {exc}"],
        )
    finally:
        for entry in prepended:
            sys.path.remove(entry)

    scope_cache: dict[str, ScopeRanges] = {}
    edges: list[ImportEdge] = []
    analysis_gaps: list[str] = []

    for importer in sorted(graph.modules):
        for imported in sorted(graph.find_modules_directly_imported_by(importer)):
            details = graph.get_import_details(importer=importer, imported=imported)
            edge = _edge_from_details(
                importer,
                imported,
                details,
                root=root,
                packages=packages,
                scope_cache=scope_cache,
                gaps=analysis_gaps,
            )
            edges.append(edge)

    gated_edges = [e for e in edges if _passes_gate(e, cfg)]
    edge_pairs = [(e.importer, e.imported) for e in gated_edges]
    all_sccs = strongly_connected_components(edge_pairs)
    cyclic_sccs = [s for s in all_sccs if len(s) >= 2]

    cycles: list[CycleGroup] = []
    for scc in cyclic_sccs:
        scc_set = set(scc)
        representative: ImportEdge | None = None
        for edge in gated_edges:
            if edge.importer in scc_set and edge.imported in scc_set:
                representative = edge
                break
        cycles.append(CycleGroup(modules=scc, representative_edge=representative))

    all_gaps = [*gaps, *analysis_gaps]
    status = GraphStatus.PARTIAL if all_gaps else GraphStatus.OK

    return GraphResult(
        status=status,
        packages=packages,
        edges=edges,
        gated_edges=gated_edges,
        cycles=cycles,
        cyclicity=cyclicity(cyclic_sccs),
        module_count=len(graph.modules),
        durability_gaps=all_gaps,
    )


def _passes_gate(edge: ImportEdge, cfg: GraphConfig) -> bool:
    if edge.kind is EdgeKind.TYPE_ONLY and cfg.type_only == "ignore":
        return False
    if edge.scope is ImportScope.FUNCTION_LOCAL and cfg.local_imports == "exclude":
        return False
    return True


def _edge_from_details(
    importer: str,
    imported: str,
    details: list,
    *,
    root: Path,
    packages: list[str],
    scope_cache: dict[str, ScopeRanges],
    gaps: list[str],
) -> ImportEdge:
    if not details:
        return ImportEdge(
            importer=importer,
            imported=imported,
            kind=EdgeKind.RUNTIME,
            scope=ImportScope.MODULE,
        )

    ranges = _scope_ranges_for_importer(
        importer, root=root, packages=packages, scope_cache=scope_cache, gaps=gaps
    )

    detail_scopes: list[ImportScope] = []
    detail_kinds: list[EdgeKind] = []
    first_line: int | None = None
    first_contents: str | None = None

    for detail in details:
        line = _detail_field(detail, "line_number")
        contents = _detail_field(detail, "line_contents")
        if first_line is None and line is not None:
            first_line = line
            first_contents = contents

        if line is None:
            detail_scopes.append(ImportScope.MODULE)
            detail_kinds.append(EdgeKind.RUNTIME)
            continue

        in_function = line_in_ranges(line, ranges.function_ranges)
        in_type_check = line_in_ranges(line, ranges.type_checking_ranges)
        detail_scopes.append(
            ImportScope.FUNCTION_LOCAL if in_function else ImportScope.MODULE
        )
        detail_kinds.append(EdgeKind.TYPE_ONLY if in_type_check else EdgeKind.RUNTIME)

    scope = (
        ImportScope.FUNCTION_LOCAL
        if detail_scopes and all(s is ImportScope.FUNCTION_LOCAL for s in detail_scopes)
        else ImportScope.MODULE
    )
    kind = (
        EdgeKind.TYPE_ONLY
        if detail_kinds and all(k is EdgeKind.TYPE_ONLY for k in detail_kinds)
        else EdgeKind.RUNTIME
    )

    return ImportEdge(
        importer=importer,
        imported=imported,
        kind=kind,
        scope=scope,
        line=first_line,
        line_contents=first_contents,
    )


def _detail_field(detail: object, name: str):
    if isinstance(detail, dict):
        return detail.get(name)
    return getattr(detail, name, None)


def _scope_ranges_for_importer(
    importer: str,
    *,
    root: Path,
    packages: list[str],
    scope_cache: dict[str, ScopeRanges],
    gaps: list[str],
) -> ScopeRanges:
    if importer in scope_cache:
        return scope_cache[importer]

    path = _module_source_path(importer, root=root, packages=packages)
    if path is None:
        scope_cache[importer] = ScopeRanges(function_ranges=(), type_checking_ranges=())
        return scope_cache[importer]

    ranges = _load_scope_ranges(path, gaps)
    scope_cache[importer] = ranges
    return ranges


def _load_scope_ranges(path: Path, gaps: list[str]) -> ScopeRanges:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        gaps.append(f"graph.analysis_failed: could not read {path} ({exc})")
        return ScopeRanges(function_ranges=(), type_checking_ranges=())

    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        gaps.append(f"graph.analysis_failed: SyntaxError in {path} — {exc}")
        return ScopeRanges(function_ranges=(), type_checking_ranges=())

    return file_scope_ranges(path)


def _module_source_path(importer: str, *, root: Path, packages: list[str]) -> Path | None:
    if not any(importer == pkg or importer.startswith(f"{pkg}.") for pkg in packages):
        return None

    rel = importer.replace(".", "/")
    candidates: list[Path] = []

    src = root / "src"
    if src.is_dir():
        candidates.append(src / f"{rel}.py")
        candidates.append(src / rel / "__init__.py")
    candidates.append(root / f"{rel}.py")
    candidates.append(root / rel / "__init__.py")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
