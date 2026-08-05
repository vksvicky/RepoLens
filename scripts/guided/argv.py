"""GuidedChoices and argv builders."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from guided.caps import RemoteKind


@dataclass
class GuidedChoices:
    command: Literal["review", "sentinel", "architecture"]
    path: str | None
    out: str | None
    scanners_only: bool
    dry_run: bool
    force_full: bool
    force_changed: bool
    full_audit: bool
    model: str | None
    verbose: bool
    timeout: float | None
    fmt: str
    scanners: str
    fail_on: str | None
    remote: tuple[RemoteKind, str] | None
    ref: str | None
    deep: bool | None = None


def build_argv(choices: GuidedChoices) -> list[str]:
    argv: list[str] = ["repolens", choices.command]
    if choices.remote:
        kind, value = choices.remote
        flag = {
            "github": "--github",
            "git-url": "--git-url",
            "bitbucket": "--bitbucket",
            "hf": "--hf",
        }[kind]
        argv.extend([flag, value])
        if choices.ref:
            argv.extend(["--ref", choices.ref])
    else:
        path = str(Path(choices.path or ".").expanduser())
        argv.extend(["--path", path])
    if choices.out:
        argv.extend(["--out", str(Path(choices.out).expanduser())])
    if choices.scanners_only:
        argv.append("--scanners-only")
    if choices.dry_run:
        argv.append("--dry-run")
    if choices.force_full and not choices.scanners_only and not choices.dry_run:
        argv.append("--full")
    if choices.force_changed and not choices.scanners_only and not choices.dry_run:
        argv.append("--changed")
    llm_pack = (
        choices.full_audit
        and choices.command == "review"
        and not choices.scanners_only
        and not choices.dry_run
    )
    if llm_pack:
        argv.append("--full-audit")
    if (
        choices.deep is not None
        and not choices.scanners_only
        and not choices.dry_run
    ):
        argv.append("--deep" if choices.deep else "--no-deep")
    if (
        choices.model
        and not choices.scanners_only
        and not choices.dry_run
    ):
        argv.extend(["--model", choices.model])
    if choices.verbose:
        argv.append("--verbose")
    if (
        choices.timeout is not None
        and not choices.scanners_only
        and not choices.dry_run
    ):
        # strip trailing .0 for integers
        t = (
            str(int(choices.timeout))
            if float(choices.timeout).is_integer()
            else str(choices.timeout)
        )
        argv.extend(["--timeout", t])
    if choices.fmt and choices.fmt != "md":
        argv.extend(["--format", choices.fmt])
    if choices.scanners and choices.scanners != "auto":
        argv.extend(["--scanners", choices.scanners])
    if choices.fail_on:
        argv.extend(["--fail-on", choices.fail_on])
    return argv


def format_command(argv: list[str]) -> str:
    return shlex.join(argv)

