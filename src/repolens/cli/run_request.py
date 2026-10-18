"""One object for a review, sentinel, or architecture run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunRequest:
    """Flags for one CLI run, after preset resolution and before source checkout."""

    mode: str
    path: str | Path | None = None
    git_url: str | None = None
    github: str | None = None
    bitbucket: str | None = None
    hf: str | None = None
    ref: str | None = None
    review_mode: str = "full"
    since: str | None = None
    out: Path | None = None
    fmt: str = "md"
    model: str | None = None
    fail_on: str | None = None
    dry_run: bool = False
    full_audit: bool = False
    trust_project: bool = False
    scanners: str = "auto"
    require_scanners: bool = False
    scanners_only: bool = False
    quiet: bool = False
    verbose: bool = False
    heartbeat: float = 15.0
    timeout: float | None = None
    force_full: bool = False
    force_changed: bool = False
    git_diff: str | None = None
    deep_passes: int | None = None
    deep: bool | None = None
    explain_uuids: str | None = None
    ci: bool = False
    sarif: bool = False
    verify_findings: bool | None = None
    packs: list[str] | None = None
    fallback: bool = True
    ratchet: bool = False
    import_sarif: list[Path] | None = None
    require_sarif_import: bool = False
    no_model_lock: bool = False
    model_lock: bool | None = None
    resume: bool = True
    role_packs: bool | None = None
    retry_passes: list[str] | None = None
    progress: Any = None
    invoked_command: str | None = None
    expanded_argv: list[str] | None = None
