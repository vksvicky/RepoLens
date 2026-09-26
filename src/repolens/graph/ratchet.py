"""Rule 1 cyclicity ratchet comparison (G2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from repolens.config import GraphConfig
from repolens.graph.baseline import (
    config_snapshot_from_graph_config,
    fingerprint_cycles,
)
from repolens.graph.types import GraphResult

_CONFIG_MISMATCH_NOTE = (
    "ratchet.config_mismatch: graph settings changed since baseline "
    "(e.g. local_imports exclude→include); re-run `repolens baseline set` "
    "after intentional config changes"
)


@dataclass
class RatchetResult:
    breached: bool
    baseline_cyclicity: int
    current_cyclicity: int
    delta: int
    fingerprints_added: list[list[str]] = field(default_factory=list)
    fingerprints_removed: list[list[str]] = field(default_factory=list)
    config_mismatch: bool = False
    config_mismatch_detail: str = ""
    notes: list[str] = field(default_factory=list)
    message: str = ""


def _fingerprint_set(fps: list[list[str]]) -> set[tuple[str, ...]]:
    return {tuple(fp) for fp in fps}


def _sorted_fps(fps: set[tuple[str, ...]]) -> list[list[str]]:
    out = [list(t) for t in fps]
    out.sort()
    return out


def _config_mismatch_detail(
    baseline_snap: dict[str, str],
    active_snap: dict[str, str],
) -> str:
    parts: list[str] = []
    for key in sorted(set(baseline_snap) | set(active_snap)):
        old = baseline_snap.get(key)
        new = active_snap.get(key)
        if old != new:
            parts.append(f"{key} {old}→{new}")
    return ", ".join(parts)


def _ratchet_message(*, baseline: int, current: int, delta: int) -> str:
    if delta > 0:
        return (
            f"Ratchet breach: runtime cyclicity increased from {baseline} "
            f"to {current} (+{delta})."
        )
    if delta < 0:
        return f"Cyclicity reduced from {baseline} to {current} (−{-delta})."
    return f"Cyclicity unchanged at {current}."


def evaluate_ratchet(
    *,
    current: GraphResult,
    baseline: dict,
    config: GraphConfig,
) -> RatchetResult:
    graph = baseline["graph"]
    baseline_cyclicity = int(graph["cyclicity"])
    current_cyclicity = current.cyclicity
    delta = current_cyclicity - baseline_cyclicity
    breached = current_cyclicity > baseline_cyclicity

    baseline_fps = list(graph.get("fingerprints", []))
    current_fps = fingerprint_cycles(current)
    base_set = _fingerprint_set(baseline_fps)
    cur_set = _fingerprint_set(current_fps)
    fingerprints_added = _sorted_fps(cur_set - base_set)
    fingerprints_removed = _sorted_fps(base_set - cur_set)

    baseline_snap = dict(baseline.get("configSnapshot", {}))
    active_snap = config_snapshot_from_graph_config(config)
    config_mismatch = baseline_snap != active_snap
    mismatch_detail = ""
    notes: list[str] = []
    if config_mismatch:
        mismatch_detail = _config_mismatch_detail(baseline_snap, active_snap)
        notes.append(_CONFIG_MISMATCH_NOTE)

    message = _ratchet_message(
        baseline=baseline_cyclicity,
        current=current_cyclicity,
        delta=delta,
    )

    return RatchetResult(
        breached=breached,
        baseline_cyclicity=baseline_cyclicity,
        current_cyclicity=current_cyclicity,
        delta=delta,
        fingerprints_added=fingerprints_added,
        fingerprints_removed=fingerprints_removed,
        config_mismatch=config_mismatch,
        config_mismatch_detail=mismatch_detail,
        notes=notes,
        message=message,
    )
