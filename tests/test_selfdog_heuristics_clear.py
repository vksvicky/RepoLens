"""Regression: the 29 selfdog heuristic finding locations stay clear."""

from __future__ import annotations

from pathlib import Path

from repolens.config import FastBrainConfig
from repolens.heuristics.deep_nesting import find_deep_nesting
from repolens.heuristics.large_functions import find_large_functions
from repolens.heuristics.mega_files import find_mega_files
from repolens.heuristics.near_clones import find_near_clones
from repolens.heuristics.transport_tls import find_transport_tls
from repolens.inventory import FileEntry

_ROOT = Path(__file__).resolve().parents[1]


def _entries(relatives: list[str]) -> list[FileEntry]:
    out: list[FileEntry] = []
    for rel in relatives:
        path = _ROOT / rel
        assert path.is_file(), rel
        out.append(
            FileEntry(
                path=path,
                relative=rel,
                size=path.stat().st_size,
                priority_band=3,
            )
        )
    return out


def test_selfdog_29_heuristic_locations_remain_clear() -> None:
    relatives = [
        "src/repolens/deep.py",
        "src/repolens/deep_types.py",
        "src/repolens/deep_budget.py",
        "src/repolens/pack_sniff.py",
        "src/repolens/deep_plan.py",
        "src/repolens/deep_merge.py",
        "src/repolens/deep_prompt.py",
        "src/repolens/cli/app.py",
        "src/repolens/cli/commands_check.py",
        "src/repolens/cli/commands_modes.py",
        "src/repolens/cli/commands_plan.py",
        "src/repolens/cli/commands_review.py",
        "src/repolens/explain.py",
        "src/repolens/explain_prompt.py",
        "src/repolens/graph/build.py",
        "src/repolens/metrics.py",
        "src/repolens/pipeline/deep_exec.py",
        "src/repolens/pipeline/deep_exec_support.py",
        "src/repolens/pipeline/deep_exec_plan.py",
        "src/repolens/pipeline/deep_exec_merge.py",
        "src/repolens/pipeline/deep_exec_coverage.py",
        "src/repolens/pipeline/pass_resume.py",
        "src/repolens/pipeline/run.py",
        "src/repolens/pipeline/run_collect.py",
        "src/repolens/pipeline/run_finish.py",
        "src/repolens/plan_forecast.py",
        "src/repolens/plugins.py",
        "src/repolens/report_metrics.py",
        "src/repolens/scanners/trivy.py",
        "src/repolens/heuristics/transport_tls.py",
        "src/repolens/llm/model_lock.py",
        "tests/test_architecture.py",
        "tests/test_quality_metrics.py",
    ]
    entries = _entries(relatives)
    mega, _ = find_mega_files(entries, mega_file_lines=500)
    large = find_large_functions(entries)
    nest = find_deep_nesting(entries)
    tls = find_transport_tls(entries)
    clones = find_near_clones(entries, config=FastBrainConfig().near_clones)
    assert mega == []
    assert large == []
    assert nest == []
    assert tls == []
    assert clones.issues == []
