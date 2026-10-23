"""Shared inputs for one deep-pass run.

The planned-pass helpers used to take the same root, config, and progress
values as long parameter lists. They now read those values from this object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeepJob:
    """Fields a deep helper may read. Callers set the ones that helper uses."""

    root: Any = None
    mode: str = "review"
    full_audit: bool = False
    files: Any = None
    llm_files: Any = None
    cfg: Any = None
    prog: Any = None
    prompt_prefix: str = ""
    scanner_runs: Any = None
    scanner_issues: Any = None
    heur_result: Any = None
    out_dir: Any = None
    fmt: str = "md"
    report_when: Any = None
    skip_cache: bool = False
    graph: Any = None
    retry_passes: frozenset[str] = field(default_factory=frozenset)
    change_set: Any = None
    passes: Any = None
    rules: Any = None
    pack_ids: Any = None
    heur_issues: Any = None
    raw_dir: Any = None
    parts: Any = None
    raw_by_pass: Any = None
    degraded_by_pass: Any = None
    all_coverage_ids: Any = None
    finished_labels: Any = None
    timed_out_labels: Any = None
    p3_gaps: Any = None
    repair_attempts_total: int = 0
    deep_pass: Any = None
    part: Any = None
    raw: str = ""
    degraded: bool = False
    attempts: int = 0
    prior_summary: str = ""
    idx: int = 0
    n: int = 0
    model_name: str = ""
    provider: str = ""
    timeout: float = 0.0
    files_done: int = 0
    files_total: int = 0
    report: Any = None
    coverage: Any = None
    unique_ids: Any = None
    pass_confidences: Any = None
    degraded_passes: Any = None
    label: str = ""
    cached: bool = False
    key: Any = None
    file_work: Any = None
