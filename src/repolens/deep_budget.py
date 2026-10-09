"""File budgeting and ordering for deep passes."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from repolens.deep_types import entry_matches_cycle, estimate_outline_chars
from repolens.inventory import FileEntry


def budget_files(
    entries: Sequence[FileEntry],
    *,
    max_chars: int,
    cost_fn: Callable[[FileEntry], int] | None = None,
) -> list[FileEntry]:
    """Greedily select files in order without exceeding ``max_chars``.

    Default cost per file is ``FileEntry.size`` (documented size-based estimate).
    Files larger than the remaining budget are skipped (later smaller files
    may still fit).
    """
    if max_chars <= 0:
        return []
    measure = cost_fn or (lambda entry: entry.size)
    selected: list[FileEntry] = []
    used = 0
    for entry in entries:
        cost = int(measure(entry))
        if cost > max_chars:
            continue
        if used + cost > max_chars:
            continue
        selected.append(entry)
        used += cost
    return selected


def _order_entries(
    entries: Sequence[FileEntry],
    *,
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
) -> list[FileEntry]:
    preferred = set(hot_paths) | set(adaptive_paths)
    by_rel = {e.relative: e for e in entries}
    ordered: list[FileEntry] = []
    seen: set[str] = set()

    for rel in list(hot_paths) + list(adaptive_paths):
        if rel in seen:
            continue
        entry = by_rel.get(rel)
        if entry is None:
            continue
        ordered.append(entry)
        seen.add(rel)

    for entry in entries:
        if entry.relative in seen:
            continue
        if entry.relative in preferred:
            continue
        ordered.append(entry)
        seen.add(entry.relative)
    return ordered


def _order_for_band(
    entries: Sequence[FileEntry],
    *,
    band: str,
    hot_paths: Iterable[str],
    adaptive_paths: Iterable[str],
    cycle_modules: set[str] | None = None,
) -> list[FileEntry]:
    from repolens.pack_sniff import is_demoted_asset, sniff_score

    if band in {"p1", "p2"}:
        entries = [e for e in entries if not is_demoted_asset(e.relative)]
    base = _order_entries(
        entries, hot_paths=hot_paths, adaptive_paths=adaptive_paths
    )
    if band == "p3" and cycle_modules:
        cycle_hits = [e for e in base if entry_matches_cycle(e, cycle_modules)]
        rest = [e for e in base if e not in cycle_hits]
        return cycle_hits + rest
    if band not in {"p1", "p2"}:
        return base

    def sort_key(entry: FileEntry) -> tuple[int, int, str]:
        return (
            -sniff_score(band, entry),
            entry.priority_band,
            entry.relative,
        )

    return sorted(base, key=sort_key)


def _budget_hybrid_p3(
    ordered: Sequence[FileEntry],
    *,
    max_chars: int,
    cycle_modules: set[str],
) -> tuple[list[FileEntry], str, dict[str, str]]:
    selected: list[FileEntry] = []
    modes: dict[str, str] = {}
    used = 0
    for entry in ordered:
        is_cycle = entry_matches_cycle(entry, cycle_modules)
        cost = int(entry.size) if is_cycle else estimate_outline_chars(entry)
        mode = "full" if is_cycle else "outline"
        if max_chars <= 0 or cost > max_chars:
            continue
        if used + cost > max_chars:
            continue
        selected.append(entry)
        modes[entry.relative] = mode
        used += cost
    if any(mode == "full" for mode in modes.values()):
        return selected, "hybrid", modes
    return selected, "outline", {rel: "outline" for rel in modes}
