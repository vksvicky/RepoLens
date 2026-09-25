from __future__ import annotations

from repolens.config import GraphConfig
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import CycleGroup, GraphResult, GraphStatus

_CONFIG_MISMATCH_NOTE_PREFIX = "ratchet.config_mismatch:"


def _baseline(
    *,
    cyclicity: int,
    fingerprints: list[list[str]],
    config_snapshot: dict[str, str] | None = None,
) -> dict:
    return {
        "graph": {
            "cyclicity": cyclicity,
            "fingerprints": fingerprints,
        },
        "configSnapshot": config_snapshot
        or {"type_only": "ignore", "local_imports": "exclude"},
    }


def _result(
    *,
    cyclicity: int,
    cycles: list[CycleGroup],
) -> GraphResult:
    return GraphResult(
        status=GraphStatus.OK,
        cyclicity=cyclicity,
        cycles=cycles,
    )


def test_breach_when_cyclicity_rises():
    baseline = _baseline(
        cyclicity=16,
        fingerprints=[["app.a", "app.b"], ["app.c", "app.d", "app.e"]],
    )
    current = _result(
        cyclicity=25,
        cycles=[
            CycleGroup(modules=("app.a", "app.b")),
            CycleGroup(modules=("app.c", "app.d", "app.e")),
            CycleGroup(modules=("app.x", "app.y")),
        ],
    )
    out = evaluate_ratchet(current=current, baseline=baseline, config=GraphConfig())
    assert out.breached is True
    assert out.baseline_cyclicity == 16
    assert out.current_cyclicity == 25
    assert out.delta == 9
    assert out.fingerprints_added == [["app.x", "app.y"]]
    assert out.message == (
        "Ratchet breach: runtime cyclicity increased from 16 to 25 (+9)."
    )


def test_no_breach_when_debt_falls_even_if_fingerprints_change():
    # 6-module SCC (36) decoupled into 3+2 (9+4=13) — new fingerprints, lower debt.
    baseline = _baseline(
        cyclicity=36,
        fingerprints=[
            ["m1", "m2", "m3", "m4", "m5", "m6"],
        ],
    )
    current = _result(
        cyclicity=13,
        cycles=[
            CycleGroup(modules=("m1", "m2", "m3")),
            CycleGroup(modules=("m4", "m5")),
        ],
    )
    out = evaluate_ratchet(current=current, baseline=baseline, config=GraphConfig())
    assert out.breached is False
    assert out.delta == -23
    assert out.fingerprints_added
    assert out.fingerprints_removed
    assert out.message == "Cyclicity reduced from 36 to 13 (−23)."


def test_config_mismatch_note_still_breaches():
    baseline = _baseline(
        cyclicity=16,
        fingerprints=[["app.a", "app.b"]],
        config_snapshot={"type_only": "ignore", "local_imports": "exclude"},
    )
    current = _result(
        cyclicity=24,
        cycles=[CycleGroup(modules=("app.a", "app.b", "app.c"))],
    )
    cfg = GraphConfig(local_imports="include")
    out = evaluate_ratchet(current=current, baseline=baseline, config=cfg)
    assert out.breached is True
    assert out.config_mismatch is True
    assert "local_imports" in out.config_mismatch_detail
    assert any(n.startswith(_CONFIG_MISMATCH_NOTE_PREFIX) for n in out.notes)


def test_unchanged_cyclicity_flat_message():
    baseline = _baseline(cyclicity=10, fingerprints=[["a", "b"]])
    current = _result(cyclicity=10, cycles=[CycleGroup(modules=("a", "b"))])
    out = evaluate_ratchet(current=current, baseline=baseline, config=GraphConfig())
    assert out.breached is False
    assert out.delta == 0
    assert out.message == "Cyclicity unchanged at 10."
    assert out.config_mismatch is False
