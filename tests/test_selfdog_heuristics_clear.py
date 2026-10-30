"""Regression: the 29 selfdog heuristic finding locations stay clear."""

from __future__ import annotations

from pathlib import Path

from repolens.config import FastBrainConfig
from repolens.heuristics.boolean_flags import find_boolean_flags
from repolens.heuristics.deep_nesting import find_deep_nesting
from repolens.heuristics.large_functions import find_large_functions
from repolens.heuristics.logging_hygiene import find_logging_hygiene
from repolens.heuristics.magic_numbers import find_magic_numbers
from repolens.heuristics.mega_files import find_mega_files
from repolens.heuristics.near_clones import find_near_clones
from repolens.heuristics.parameter_lists import find_long_parameter_lists
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


def test_deep_resume_and_retry_files_stay_under_mega_file_lines() -> None:
    from repolens.heuristics.mega_files import find_mega_files

    relatives = [
        "tests/test_pipeline_deep_resume.py",
        "tests/test_pipeline_retry_pass.py",
    ]
    mega, _ = find_mega_files(_entries(relatives), mega_file_lines=500)
    assert mega == []


def test_coverage_closure_function_stays_under_eighty_lines() -> None:
    large = find_large_functions(_entries(["src/repolens/pipeline/deep_pass.py"]))
    assert large == []


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


def test_product_tree_has_no_swallowed_handlers_or_magic_numbers() -> None:
    entries: list[FileEntry] = []
    for base in ("src", "scripts"):
        for path in (_ROOT / base).rglob("*.py"):
            rel = path.relative_to(_ROOT).as_posix()
            entries.append(
                FileEntry(
                    path=path,
                    relative=rel,
                    size=path.stat().st_size,
                    priority_band=3,
                )
            )
    swallowed = [
        issue
        for issue in find_logging_hygiene(entries)
        if issue.category == "heuristic.swallowed_exception"
    ]
    magic = find_magic_numbers(entries)
    assert [(issue.file, issue.line) for issue in swallowed] == []
    assert [(issue.file, issue.line, issue.title) for issue in magic] == []


def test_product_tree_has_no_long_parameter_lists_or_boolean_flags() -> None:
    entries: list[FileEntry] = []
    for base in ("src", "scripts"):
        for path in (_ROOT / base).rglob("*.py"):
            rel = path.relative_to(_ROOT).as_posix()
            entries.append(
                FileEntry(
                    path=path,
                    relative=rel,
                    size=path.stat().st_size,
                    priority_band=3,
                )
            )
    params = find_long_parameter_lists(entries)
    flags = find_boolean_flags(entries)
    assert [(issue.file, issue.title) for issue in params] == []
    assert [(issue.file, issue.title) for issue in flags] == []
