# tests/test_complexity_runner.py
"""B6 — Fast Brain complexity runner: Issues + Top-10 block."""

from __future__ import annotations

from pathlib import Path

from repolens.complexity.runner import run_complexity
from repolens.inventory import FileEntry


def _entry(tmp: Path, relative: str, source: str) -> FileEntry:
    path = tmp / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return FileEntry(
        path=path, relative=relative, size=path.stat().st_size, priority_band=3
    )


def test_run_complexity_emits_issues_only_above_threshold(tmp_path: Path) -> None:
    clean = _entry(
        tmp_path,
        "pkg/clean.py",
        "def add(a, b):\n    return a + b\n",
    )
    # Build a function with many branches → high cyclo/cognitive
    lines = ["def monster(x):"]
    for i in range(30):
        lines.append(f"    if x == {i}:")
        lines.append(f"        return {i}")
    lines.append("    return -1\n")
    hot = _entry(tmp_path, "pkg/hot.py", "\n".join(lines))

    result = run_complexity(tmp_path, [clean, hot])
    assert result.block.functionsAnalysed >= 2
    assert all(i.category == "quality.complexity" for i in result.issues)
    assert all(i.source == "heuristic" for i in result.issues)
    # clean must not appear as an Issue
    assert not any(i.file.endswith("clean.py") for i in result.issues)
    assert any(i.file.endswith("hot.py") for i in result.issues)
    assert result.block.issueCount == len(result.issues)
    assert result.block.maxCyclomatic >= 11


def test_run_complexity_top10_hotspots_sorted(tmp_path: Path) -> None:
    entries = []
    for n in range(12):
        # Increasing branch counts
        body = "\n".join(
            [f"def f{n}(x):"]
            + [f"    if x == {i}:\n        return {i}" for i in range(n + 1)]
            + ["    return -1"]
        )
        entries.append(_entry(tmp_path, f"m{n}.py", body + "\n"))

    result = run_complexity(tmp_path, entries)
    assert len(result.block.hotspots) == 10
    scores = [(h.cognitive, h.cyclomatic) for h in result.block.hotspots]
    assert scores == sorted(scores, reverse=True)


def test_run_complexity_disabled_returns_empty(tmp_path: Path) -> None:
    e = _entry(tmp_path, "a.py", "def f():\n    return 1\n")
    result = run_complexity(tmp_path, [e], enabled=False)
    assert result.block.functionsAnalysed == 0
    assert result.issues == []


def test_review_entrypoints_are_not_critical_or_high() -> None:
    """run_review and _run_mode must stay out of the Critical/High bands."""
    from repolens.complexity.python_ast import analyse_python_file
    from repolens.complexity.thresholds import band_for_scores
    from repolens.schema import Severity

    root = Path(__file__).resolve().parents[1]
    hot: list[str] = []
    for rel in (
        "src/repolens/pipeline/run.py",
        "src/repolens/cli/commands_review.py",
    ):
        for fn in analyse_python_file(str(root / rel)):
            band = band_for_scores(cyclomatic=fn.cyclomatic, cognitive=fn.cognitive)
            if band.severity in {Severity.HIGH, Severity.CRITICAL}:
                hot.append(
                    f"{rel}:{fn.name} cyclo={fn.cyclomatic} cog={fn.cognitive} "
                    f"{band.severity.value}"
                )
    assert hot == []


def test_reported_hotspots_are_not_critical_or_high() -> None:
    """Functions the 2026-09-27 deep review flagged must stay out of High."""
    from repolens.complexity.python_ast import analyse_python_file
    from repolens.complexity.thresholds import band_for_scores
    from repolens.schema import Severity

    root = Path(__file__).resolve().parents[1]
    targets = {
        "src/repolens/scanners/trivy.py": {"parse_trivy_report"},
        "scripts/guided/prompts.py": {"_collect_choices"},
        "src/repolens/report_parse.py": {"parse_markdown_report"},
        "src/repolens/pipeline/deep_exec.py": {"_analyze_deep_passes"},
        "src/repolens/feedback_store.py": {"apply_feedback_calibrations"},
        "src/repolens/heuristics/near_clones.py": {"find_near_clones"},
        "src/repolens/scanners/sca.py": {"dedupe_cross_source_sca_issues"},
        "src/repolens/scanners/sca_sbom.py": {
            "parse_cyclonedx_license_summary",
            "collect_license_ids",
            "build_supply_chain",
        },
        "src/repolens/cli/commands_pr_summary.py": {"pr_summary_cmd"},
        "src/repolens/llm/gemini.py": {"stream_gemini_sse"},
        "src/repolens/llm/transport.py": {
            "_stream_anthropic",
            "_stream_openai_compatible",
        },
        "src/repolens/graph/discover.py": {"_packages_from_pyproject"},
        "src/repolens/report.py": {"render_markdown"},
        "src/repolens/testing/inventory.py": {"_count_production_functions"},
        "src/repolens/triage.py": {"triage_llm_plan"},
        "src/repolens/heuristics/runner.py": {"run_heuristics"},
        "src/repolens/benchmark.py": {"score_actionability"},
        "scripts/guided/argv.py": {"build_argv"},
        "src/repolens/report_sections.py": {"_render_provenance_section"},
        "src/repolens/pipeline/run_collect.py": {"_load_review_inventory"},
        "src/repolens/sarif_import.py": {"_issues_from_run"},
        "src/repolens/complexity/python_ast.py": {"_cog_node"},
        "src/repolens/consistency.py": {"apply_llm_consistency"},
    }
    hot: list[str] = []
    for rel, names in targets.items():
        found = {fn.name: fn for fn in analyse_python_file(str(root / rel))}
        for name in names:
            fn = found[name]
            band = band_for_scores(cyclomatic=fn.cyclomatic, cognitive=fn.cognitive)
            if band.severity in {Severity.HIGH, Severity.CRITICAL}:
                hot.append(
                    f"{rel}:{name} cyclo={fn.cyclomatic} cog={fn.cognitive} "
                    f"{band.severity.value}"
                )
    assert hot == []


def test_dogfood_modules_stay_under_mega_file_cap() -> None:
    """The 2026-09-28 review flagged these modules at the 500-line mega-file bar."""
    root = Path(__file__).resolve().parents[1]
    rels = [
        "src/repolens/cli/commands_review.py",
        "src/repolens/cli/commands_review_support.py",
        "src/repolens/cli/commands_modes.py",
        "src/repolens/explain.py",
        "src/repolens/explain_render.py",
        "src/repolens/pipeline/deep_exec.py",
        "src/repolens/pipeline/deep_pass.py",
        "src/repolens/pipeline/run.py",
        "src/repolens/pipeline/run_support.py",
        "src/repolens/pipeline/run_collect.py",
        "src/repolens/pipeline/run_route.py",
        "src/repolens/pipeline/run_finish.py",
        "src/repolens/report.py",
        "src/repolens/report_sections.py",
        "src/repolens/scanners/sca.py",
        "src/repolens/scanners/sca_sbom.py",
    ]
    over = []
    for rel in rels:
        count = len((root / rel).read_text(encoding="utf-8").splitlines())
        if count >= 500:
            over.append(f"{rel}:{count}")
    assert over == []
