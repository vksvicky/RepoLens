"""Inventory, scanner, and Fast Brain phases of a review."""

from __future__ import annotations

import time
from datetime import UTC
from pathlib import Path

from repolens.config import resolve_report_dir
from repolens.pipeline.deep_exec import (
    _sync_adaptive_cache,
)
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_support import _extend_from_import_sarif, _git_sha
from repolens.pipeline.types import ReviewResult, ScannerRequirementError
from repolens.report import write_json_report, write_markdown_report
from repolens.scanners.runner import missing_required, parse_scanners_flag, run_scanners
from repolens.scanners.sca import build_supply_chain, dedupe_sca_issues
from repolens.schema import (
    FindingReport,
    GraphBlock,
    ProvenanceBlock,
    Summary,
)


def _apply_scope_flags(state: ReviewRun) -> None:
    state.git_diff_base_cli = None
    state.git_changed_paths = []
    if state.git_diff_requested:
        raw = (state.git_diff or "").strip()
        state.git_diff_base_cli = None if raw.lower() in {"", "auto"} else raw
    if state.ci:
        state.cfg.ci.triage_routing = True
        if not state.force_full and not state.force_changed:
            state.force_changed = True
        if state.deep is None and state.cfg.ci.max_llm_passes_in_ci <= 1:
            state.deep = False
        state.prog.detail(
            "CI mode: triage routing on "
            "(LLM bypass when scanners/heuristics clean; snippet pack on hits)"
        )
    if state.mode == "sentinel" and state.scanners is None:
        state.scanners = "auto"


def _assign_inventory_files(state: ReviewRun, fast_inv) -> None:
    state.fast_files = fast_inv.files
    llm_cap = state.cfg.general.max_files
    if llm_cap <= 0:
        state.files = list(state.fast_files)
        return
    state.files = list(state.fast_files[:llm_cap])


def _announce_inventory(state: ReviewRun, fast_inv) -> None:
    if fast_inv.truncated:
        state.prog.phase(
            f"Fast brain inventory: {len(state.fast_files)} of {fast_inv.total_matched} "
            f"matched (cap max_files={fast_inv.max_files})"
        )
    else:
        state.prog.phase(f"Fast brain inventory: {len(state.fast_files)} matched file(s)")
    llm_cap = state.cfg.general.max_files
    if len(state.files) < len(state.fast_files):
        state.prog.detail(
            f"Slow brain LLM pool: top {len(state.files)} by priority "
            f"(general.max_files={llm_cap}); Fast Brain heuristics use all "
            f"{len(state.fast_files)}"
        )
        state.inventory_notes = [
            (
                f"Two-Lane: Fast Brain sees {len(state.fast_files)} file(s); "
                f"LLM sample pool is {len(state.files)} "
                f"(general.max_files={llm_cap}). "
                "Deterministic scanners still cover the full tree."
            )
        ]
        return
    state.inventory_notes = []
    note = fast_inv.truncation_note()
    if note:
        state.inventory_notes.append(note)


def _load_review_inventory(state: ReviewRun) -> None:
    _apply_scope_flags(state)
    state.prog.phase("Inventory: scanning files…")
    from repolens.inventory import scan_inventory
    from repolens.learned_prefs import load_learned_prefs, merge_skip_globs

    skip = list(state.cfg.deep.skip_paths)
    if state.cfg.deep.learned_prefs:
        prefs = load_learned_prefs(state.root)
        if prefs.skip_globs:
            skip = merge_skip_globs(skip, prefs)
    fast_inv = scan_inventory(
        state.root,
        mode=state.review_mode,
        since=state.since,
        max_files=state.cfg.fast_brain.max_files,
        skip_globs=skip,
    )
    _assign_inventory_files(state, fast_inv)
    _announce_inventory(state, fast_inv)
    if state.prog.verbose and state.fast_files:
        sample = ", ".join(f.relative for f in state.fast_files[:8])
        more = f" (+{len(state.fast_files) - 8} more)" if len(state.fast_files) > 8 else ""
        state.prog.detail(f"sample: {sample}{more}")

    # Fingerprints track Fast Brain set (not LLM slice alone).
    state.store, state.diff = _sync_adaptive_cache(
        state.root, state.fast_files, cfg=state.cfg, prog=state.prog
    )

    state.fast_brain_file_count = len(state.fast_files)
    state.llm_pack_file_count = 0
    state.fast_brain_seconds = None
    state.llm_seconds_prov = None
    state.heur_result = None
    state.complexity_result = None
    state.complexity_issues = []
    state.testing_result = None

    if state.out_dir is not None:
        state.out = state.out_dir
    else:
        state.out = resolve_report_dir(state.root, state.cfg.general.report_dir)


def _write_dry_run(state: ReviewRun) -> ReviewResult:
    from datetime import datetime

    from repolens import __version__

    state.prog.phase("Dry-run: writing inventory report (no scanners / LLM)…")
    empty = FindingReport(
        confidence=0,
        summary=Summary(),
        issues=[],
        durabilityGaps=["dry-run: no LLM call"] + list(state.inventory_notes),
        durationSeconds=round(time.time() - state.run_started, 1),
        provenance=ProvenanceBlock(
            repoLensVersion=__version__,
            gitSha=_git_sha(state.root),
            fastBrainFiles=state.fast_brain_file_count,
            llmPackFiles=0,
        ),
    )
    state.report_when = datetime.now(UTC)
    state.md = (
        write_markdown_report(empty, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"md", "both"}
        else None
    )
    state.js = (
        write_json_report(empty, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"json", "both"}
        else None
    )
    state.prog.phase("Done (dry-run)")
    return ReviewResult(
        report=empty,
        markdown_path=state.md,
        json_path=state.js,
        files_scanned=state.fast_brain_file_count,
        dry_run=True,
    )


def _run_scanner_tools(state: ReviewRun) -> None:
    state.tools = parse_scanners_flag(state.scanners, config_enabled=state.cfg.scanners.enabled)
    if state.scanners_only and state.tools is None:
        state.tools = list(state.cfg.scanners.enabled)

    state.scanner_runs = []
    state.scanner_issues = []
    state.scanner_gaps = []
    state.supply_chain = None
    state.triage_plan = None


def _postprocess_scanner_issues(state: ReviewRun) -> None:
    if state.tools:
        state.prog.phase(f"Scanners: running {', '.join(state.tools)}…")
        state.scanner_runs, state.scanner_issues, state.scanner_gaps = run_scanners(
            state.root, state.tools
        )
        for run in state.scanner_runs:
            state.prog.detail(
                f"{run.tool}: {run.status}" + (f" — {run.detail}" if run.detail else "")
            )
    else:
        state.prog.detail("Scanners: skipped (off / none selected)")

    _extend_from_import_sarif(
        state.import_sarif,
        state.root,
        state.scanner_issues,
        state.scanner_runs,
        state.prog,
        require=state.require_sarif_import,
    )

    if state.tools or state.import_sarif:
        before_dedupe = len(state.scanner_issues)
        state.scanner_issues = dedupe_sca_issues(state.scanner_issues)
        if len(state.scanner_issues) < before_dedupe:
            state.prog.detail(
                f"SCA: deduped {before_dedupe - len(state.scanner_issues)} "
                "duplicate OSV/Trivy advisory row(s)"
            )

    if state.tools:
        if state.cfg.deep.usage_hints:
            from repolens.scanners.usage_hints import apply_usage_hints

            state.scanner_issues = apply_usage_hints(state.root, state.scanner_issues)
            hinted = sum(1 for i in state.scanner_issues if i.usageHint)
            if hinted:
                state.prog.detail(
                    f"SCA usage hints: {hinted} package finding(s) "
                    "(not reachability)"
                )
        state.prog.phase(
            f"Scanners: finished ({len(state.scanner_issues)} finding(s), "
            f"{sum(1 for r in state.scanner_runs if r.status == 'ran')}/"
            f"{len(state.scanner_runs)} ran)"
        )
        require = state.require_scanners or state.cfg.scanners.require
        if require:
            missing = missing_required(state.tools, state.scanner_runs)
            if missing:
                raise ScannerRequirementError(missing)


def _collect_supply_chain(state: ReviewRun) -> None:
    want_supply = state.cfg.scanners.sbom or state.cfg.scanners.licenses
    trivy_requested = bool(state.tools) and "trivy" in state.tools
    if want_supply:
        from repolens.scanners.base import resolve_binary

        trivy_available = resolve_binary("trivy") is not None
        if trivy_available or trivy_requested:
            state.prog.phase("Supply chain: SBOM / licenses…")
            state.supply_chain, sc_gaps = build_supply_chain(
                state.root,
                state.out,
                sbom=state.cfg.scanners.sbom,
                licenses=state.cfg.scanners.licenses,
            )
            state.scanner_gaps.extend(sc_gaps)
            if state.supply_chain and state.supply_chain.sbomPath:
                state.prog.detail(f"SBOM: {state.supply_chain.sbomPath}")
            elif sc_gaps:
                state.prog.detail(sc_gaps[0])
        else:
            state.prog.detail(
                "Supply chain: skipped (install Trivy for SBOM/licenses — "
                "`repolens plugins install trivy`)"
            )


def _run_fast_brain_phase(state: ReviewRun) -> None:
    state.prog.phase(
        f"Fast brain: heuristics on {len(state.fast_files)} file(s) "
        f"(workers={state.cfg.fast_brain.parallel_workers})…"
    )
    _fb_t0 = time.monotonic()
    from repolens.heuristics import run_heuristics

    state.heur_result = run_heuristics(
        state.root,
        state.fast_files,
        mega_file_lines=state.cfg.deep.mega_file_lines,
        mega_file_exclude_globs=state.cfg.deep.extra_skip_globs() or None,
        pack_ids=state.pack_ids or None,
        workers=state.cfg.fast_brain.parallel_workers,
        near_clones_config=state.cfg.fast_brain.near_clones,
    )
    state.fast_brain_seconds = round(time.monotonic() - _fb_t0, 1)
    state.heur_issues = list(state.heur_result.issues)
    state.prog.detail(
        f"Fast brain: {len(state.heur_issues)} heuristic finding(s), "
        f"{len(state.heur_result.hot_paths)} hot path(s)"
    )

    from repolens.complexity.runner import run_complexity

    state.complexity_result = run_complexity(
        state.root,
        state.fast_files,
        enabled=state.cfg.complexity.enabled,
        hotspot_limit=state.cfg.complexity.hotspot_limit,
    )
    state.complexity_issues = list(state.complexity_result.issues)
    if state.cfg.complexity.enabled:
        state.prog.detail(
            f"Complexity: {state.complexity_result.block.functionsAnalysed} function(s), "
            f"{len(state.complexity_issues)} above threshold, "
            f"top-{len(state.complexity_result.block.hotspots)} hotspots"
        )

    from repolens.testing.inventory import run_testing_inventory

    state.testing_result = run_testing_inventory(
        state.root,
        state.fast_files,
        enabled=state.cfg.testing.inventory,
    )
    if state.cfg.testing.inventory:
        tb = state.testing_result.block
        state.prog.detail(
            f"Testing inventory: {tb.testFileCount} file(s), "
            f"{tb.testCaseCount} case(s), "
            f"ratio {tb.testsPerProductionFunction} tests/prod fn"
        )

    state.graph_issues = []
    state.graph_block = None
    state.graph_gaps = []
    if any(Path(f.relative).suffix == ".py" for f in state.fast_files):
        from repolens.graph import analyse_repo_graph
        from repolens.graph.findings import cycles_to_issues

        gres = analyse_repo_graph(state.root, config=state.cfg.graph)
        state.graph_gaps = list(gres.durability_gaps)
        state.graph_issues = cycles_to_issues(
            gres, critical_scc_size=state.cfg.graph.critical_scc_size
        )
        state.graph_block = GraphBlock(
            status=gres.status.value,
            cyclicity=gres.cyclicity,
            cycleCount=len(gres.cycles),
            moduleCount=gres.module_count,
            packageCount=len(gres.packages),
        )
        state.prog.detail(
            f"Import graph: {state.graph_block.cycleCount} cycle group(s), "
            f"{len(state.graph_issues)} finding(s), cyclicity={state.graph_block.cyclicity}"
        )
