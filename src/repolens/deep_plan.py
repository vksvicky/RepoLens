"""Deep multi-pass planner."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from repolens.coverage import coverage_ids_for_pass
from repolens.deep_budget import (
    _budget_hybrid_p3,
    _order_entries,
    _order_for_band,
    budget_files,
)
from repolens.deep_types import DeepPass, estimate_outline_chars
from repolens.inventory import FileEntry
from repolens.rules.registry import Rule

if TYPE_CHECKING:
    from repolens.graph.types import GraphResult

_MODE_BANDS: dict[str, tuple[str, ...]] = {
    "sentinel": ("p1",),
    "architecture": ("p3",),
    "review": ("p1", "p2", "p3"),
}


def _enabled_by_band(rules: Sequence[Rule], band: str) -> list[Rule]:
    band_norm = band.lower()
    return [r for r in rules if r.enabled and r.band.lower() == band_norm]


def _resolve_bands(mode: str, max_passes: int | None) -> tuple[str, ...]:
    bands = _MODE_BANDS.get(mode)
    if bands is None:
        raise ValueError(f"Unknown mode: {mode}")
    if max_passes is not None and max_passes > 0:
        return bands[:max_passes]
    return bands


def _collect_cycle_modules(
    graph: GraphResult | None,
) -> tuple[set[str], bool]:
    from repolens.graph.types import GraphStatus

    cycle_modules: set[str] = set()
    graph_usable = (
        graph is not None
        and graph.status not in {GraphStatus.FAILED, GraphStatus.SKIPPED}
    )
    if graph_usable and graph is not None:
        for group in graph.cycles:
            cycle_modules.update(group.modules)
    return cycle_modules, graph_usable


def _pack_p3_role(
    ordered: Sequence[FileEntry],
    *,
    chars_per_pass: int,
    cycle_modules: set[str],
    graph_usable: bool,
    graph: GraphResult | None,
    durability_gaps_out: list[str] | None,
) -> tuple[list[FileEntry], str, dict[str, str]]:
    if not graph_usable:
        if durability_gaps_out is not None:
            reason = (
                "graph unavailable"
                if graph is None
                else f"status={graph.status.value}"
            )
            durability_gaps_out.append(f"graph.p3_outline_only: {reason}")
        packed = budget_files(
            ordered,
            max_chars=chars_per_pass,
            cost_fn=estimate_outline_chars,
        )
        return packed, "outline", {}
    if cycle_modules:
        return _budget_hybrid_p3(
            ordered,
            max_chars=chars_per_pass,
            cycle_modules=cycle_modules,
        )
    packed = budget_files(
        ordered,
        max_chars=chars_per_pass,
        cost_fn=estimate_outline_chars,
    )
    return packed, "outline", {}


def _pack_role_band(
    band: str,
    *,
    entries: Sequence[FileEntry],
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
    chars_per_pass: int,
    cycle_modules: set[str],
    graph_usable: bool,
    graph: GraphResult | None,
    durability_gaps_out: list[str] | None,
) -> tuple[list[FileEntry], str, dict[str, str]]:
    ordered = _order_for_band(
        entries,
        band=band,
        hot_paths=hot_paths,
        adaptive_paths=adaptive_paths,
        cycle_modules=cycle_modules if band == "p3" else None,
    )
    if band != "p3":
        return budget_files(ordered, max_chars=chars_per_pass), "full", {}
    return _pack_p3_role(
        ordered,
        chars_per_pass=chars_per_pass,
        cycle_modules=cycle_modules,
        graph_usable=graph_usable,
        graph=graph,
        durability_gaps_out=durability_gaps_out,
    )


def plan_deep_passes(
    mode: str,
    *,
    full_audit: bool,
    entries: Sequence[FileEntry],
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
    chars_per_pass: int,
    rules: list[Rule],
    max_passes: int | None = None,
    role_packs: bool = False,
    graph: GraphResult | None = None,
    durability_gaps_out: list[str] | None = None,
) -> list[DeepPass]:
    """Plan band-ordered deep passes from enabled rules for ``mode``.

    ``max_passes`` caps how many band passes run (1 = first band only, e.g. P1
    for ``review``). ``None`` or ``<= 0`` keeps the full mode band list.

    When ``role_packs`` is true, each band gets its own ordered budget and P3
    uses outline-cost estimates, or hybrid full bodies for import-cycle modules
    when ``graph`` is available.
    """
    bands = _resolve_bands(mode, max_passes)

    shared: list[FileEntry] | None = None
    if not role_packs:
        ordered_files = _order_entries(
            entries, hot_paths=hot_paths, adaptive_paths=adaptive_paths
        )
        shared = budget_files(ordered_files, max_chars=chars_per_pass)

    cycle_modules, graph_usable = _collect_cycle_modules(graph)

    passes: list[DeepPass] = []
    for band in bands:
        band_rules = _enabled_by_band(rules, band)
        if not band_rules:
            continue
        rule_ids = [r.id for r in band_rules]
        cov_ids = coverage_ids_for_pass(
            band,
            full_audit=full_audit,
            enabled_rule_ids=rule_ids,
        )
        if role_packs:
            packed, pack_mode, file_pack_modes = _pack_role_band(
                band,
                entries=entries,
                hot_paths=hot_paths,
                adaptive_paths=adaptive_paths,
                chars_per_pass=chars_per_pass,
                cycle_modules=cycle_modules,
                graph_usable=graph_usable,
                graph=graph,
                durability_gaps_out=durability_gaps_out,
            )
        else:
            packed = list(shared or [])
            pack_mode = "full"
            file_pack_modes = {}
        passes.append(
            DeepPass(
                name=band,
                rule_ids=rule_ids,
                coverage_ids=cov_ids,
                files=list(packed),
                pack_mode=pack_mode,
                file_pack_modes=file_pack_modes,
            )
        )
    return passes
