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
        from repolens.graph.query import direct_dependencies, direct_dependents
        from repolens.graph.repo import analyse_repo_graph
        from repolens.graph.types import GraphStatus
    except ImportError:
        return BlastRadiusResult(
            paths=list(base),
            note="blast-radius skipped: graph imports unavailable",
        )

    cfg = load_config(root)
    try:
        result = analyse_repo_graph(root, config=cfg.graph)
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


@dataclass(frozen=True)
class BlastRadiusSimulation:
    """Standalone query: transitive consumers of a path or module."""

    seed: str
    seed_module: str
    consumers: list[str]
    consumer_count: int
    graph_module_count: int
    percent_of_graph: float
    boundary_violations: list[str]
    test_file_count: int
    test_case_count: int
    test_density_note: str
    note: str | None = None


def _resolve_seed_module(seed: str) -> str:
    raw = seed.strip().replace("\\", "/")
    if raw.endswith(".py") or "/" in raw:
        mod = _rel_to_module(raw)
        if mod is None:
            raise ValueError(f"Cannot map path to module: {seed}")
        return mod
    return raw.replace("/", ".")


def _graph_module_set(result: object) -> set[str]:
    modules: set[str] = set()
    for edge in getattr(result, "gated_edges", []) or []:
        modules.add(edge.importer)
        modules.add(edge.imported)
    count = int(getattr(result, "module_count", 0) or 0)
    if count and len(modules) < count:
        # Prefer declared count when larger than edge-derived set.
        return modules
    return modules


def simulate_blast_radius(root: Path, seed: str) -> BlastRadiusSimulation:
    """Transitive importers of *seed* (path or dotted module) + boundary/test signals."""
    from repolens.architecture.load import discover_architecture_path, load_architecture
    from repolens.architecture.verify import verify_boundaries
    from repolens.config import load_config
    from repolens.graph.query import reachable_dependents
    from repolens.graph.repo import analyse_repo_graph
    from repolens.graph.types import GraphStatus
    from repolens.inventory import list_files
    from repolens.testing.inventory import run_testing_inventory

    root = root.resolve()
    seed_module = _resolve_seed_module(seed)
    cfg = load_config(root)
    result = analyse_repo_graph(root, config=cfg.graph)
    if result.status != GraphStatus.OK:
        gaps = "; ".join(result.durability_gaps[:3]) or result.status.value
        raise RuntimeError(f"graph unavailable: {gaps}")

    consumers = reachable_dependents(result, seed_module)
    modules = _graph_module_set(result)
    module_count = max(1, result.module_count or len(modules) or 1)
    percent = round(100.0 * len(consumers) / module_count, 2)

    violations: list[str] = []
    arch_path = discover_architecture_path(root)
    if arch_path is not None:
        doc = load_architecture(arch_path)
        radius = {seed_module, *consumers}
        for v in verify_boundaries(result, doc):
            if v.importer in radius or v.imported in radius:
                violations.append(
                    f"{v.importer} → {v.imported} ({v.from_boundary}→{v.to_boundary}: "
                    f"{v.reason})"
                )

    entries = list_files(root, max_files=0)
    testing = run_testing_inventory(root, entries, enabled=True)
    # Density in radius: test files that import any radius module (best-effort path match)
    radius_paths = set()
    for mod in [seed_module, *consumers]:
        radius_paths.update(_module_to_candidates(mod))
    test_files = 0
    test_cases = 0
    for entry in entries:
        rel = entry.relative.replace("\\", "/")
        if not rel.endswith(".py"):
            continue
        name = Path(rel).name
        if not (
            name.startswith("test_")
            or name.endswith("_test.py")
            or "/tests/" in f"/{rel.lower()}/"
        ):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(
            cand.replace(".py", "").replace("/", ".") in text
            or cand in text
            for cand in radius_paths
        ) or any(mod in text for mod in [seed_module, *consumers]):
            test_files += 1
            test_cases += sum(
                1
                for line in text.splitlines()
                if line.lstrip().startswith("def test")
            )

    block = testing.block if testing is not None else None
    note = None
    if block is not None and test_files == 0:
        note = (
            f"repo-wide tests: {block.testFileCount} files / {block.testCaseCount} cases; "
            "none matched radius imports by text"
        )
    density = (
        f"{test_files} test file(s), ~{test_cases} test case(s) referencing radius"
        if test_files
        else (note or "no test inventory matched in radius")
    )
    return BlastRadiusSimulation(
        seed=seed,
        seed_module=seed_module,
        consumers=consumers,
        consumer_count=len(consumers),
        graph_module_count=module_count,
        percent_of_graph=percent,
        boundary_violations=violations,
        test_file_count=test_files,
        test_case_count=test_cases,
        test_density_note=density,
        note=note,
    )
