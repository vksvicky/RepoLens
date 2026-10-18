"""Explicit state for one ``run_review`` call.

Phases take this object and read or write fields on it. They do not share
locals through ``nonlocal``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repolens.config import RepoLensConfig
from repolens.progress import ReviewProgress


@dataclass
class ReviewRun:
    """Inputs plus the fields each review phase fills in."""

    path: Path
    mode: str
    review_mode: str = "full"
    since: str | None = None
    out_dir: Path | None = None
    fmt: str = "md"
    model_override: str | None = None
    timeout_override: float | None = None
    force_full: bool = False
    force_changed: bool = False
    git_diff: str | None = None
    deep_passes: int | None = None
    full_audit: bool = False
    dry_run: bool = False
    trust_project: bool = False
    config: RepoLensConfig | None = None
    scanners: str | None = "auto"
    require_scanners: bool = False
    scanners_only: bool = False
    progress: ReviewProgress | None = None
    deep: bool | None = None
    ci: bool = False
    sarif: bool = False
    verify_findings: bool | None = None
    packs: list[str] | None = None
    fallback: bool | None = None
    import_sarif: list[Path] | None = None
    require_sarif_import: bool = False
    model_lock: bool | None = None
    resume: bool = True
    retry_passes: list[str] | None = None
    role_packs: bool | None = None
    invoked_command: str | None = None
    expanded_argv: list[str] = field(default_factory=list)

    cfg: Any = None
    aborted: bool = False
    change_set_block: Any = None
    complexity_issues: Any = None
    complexity_result: Any = None
    diff: Any = None
    fast_brain_file_count: Any = None
    fast_brain_seconds: Any = None
    fast_files: Any = None
    files: Any = None
    git_changed_paths: Any = None
    git_diff_base_cli: Any = None
    git_diff_requested: Any = None
    graph_block: Any = None
    graph_gaps: Any = None
    graph_issues: Any = None
    graph_result: Any = None
    heur_issues: Any = None
    heur_result: Any = None
    inventory_notes: Any = None
    js: Any = None
    llm_files: Any = None
    llm_label: Any = None
    llm_pack_file_count: Any = None
    llm_seconds_prov: Any = None
    md: Any = None
    model_name: Any = None
    non_llm_issues: Any = None
    out: Any = None
    pack_ids: Any = None
    pack_mode: Any = None
    prog: Any = None
    prompt_prefix: Any = None
    provider: Any = None
    report: Any = None
    report_when: Any = None
    root: Any = None
    run_started: Any = None
    scanner_gaps: Any = None
    scanner_issues: Any = None
    scanner_runs: Any = None
    started: Any = None
    store: Any = None
    supply_chain: Any = None
    testing_result: Any = None
    timeout: Any = None
    tools: Any = None
    triage_bypassed: Any = None
    triage_plan: Any = None
    use_deep: Any = None
    _llm_t0: Any = None
