"""Unset Fast Brain workers leave one core free and never exceed eight."""

from __future__ import annotations

from repolens.config import FastBrainConfig
from repolens.heuristics.workers import resolve_fast_brain_workers


def test_unset_workers_leave_one_core_free() -> None:
    assert resolve_fast_brain_workers(0, cpu_count=4) == 3
    assert resolve_fast_brain_workers(0, cpu_count=16) == 8
    assert resolve_fast_brain_workers(0, cpu_count=1) == 1
    assert resolve_fast_brain_workers(0, cpu_count=0) == 1


def test_explicit_worker_count_wins() -> None:
    assert resolve_fast_brain_workers(4, cpu_count=16) == 4
    assert FastBrainConfig().parallel_workers == 0
