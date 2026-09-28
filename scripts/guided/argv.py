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


_REMOTE_FLAGS = {
    "github": "--github",
    "git-url": "--git-url",
    "bitbucket": "--bitbucket",
    "hf": "--hf",
}


def _llm_flags_allowed(choices: GuidedChoices) -> bool:
    return not choices.scanners_only and not choices.dry_run


def _append_target(argv: list[str], choices: GuidedChoices) -> None:
    if choices.remote:
        kind, value = choices.remote
        argv.extend([_REMOTE_FLAGS[kind], value])
        if choices.ref:
            argv.extend(["--ref", choices.ref])
        return
    path = str(Path(choices.path or ".").expanduser())
    argv.extend(["--path", path])


def _append_scope_flags(argv: list[str], choices: GuidedChoices) -> None:
    if choices.scanners_only:
        argv.append("--scanners-only")
    if choices.dry_run:
        argv.append("--dry-run")
    if not _llm_flags_allowed(choices):
        return
    if choices.force_full:
        argv.append("--full")
    if choices.force_changed:
        argv.append("--changed")
    if choices.full_audit and choices.command == "review":
        argv.append("--full-audit")
    if choices.deep is not None:
        argv.append("--deep" if choices.deep else "--no-deep")


def _timeout_token(timeout: float) -> str:
    if float(timeout).is_integer():
        return str(int(timeout))
    return str(timeout)


def _append_model_flags(argv: list[str], choices: GuidedChoices) -> None:
    if _llm_flags_allowed(choices) and choices.model:
        argv.extend(["--model", choices.model])
    if choices.verbose:
        argv.append("--verbose")
    if _llm_flags_allowed(choices) and choices.timeout is not None:
        argv.extend(["--timeout", _timeout_token(choices.timeout)])


def _append_out(argv: list[str], choices: GuidedChoices) -> None:
    if choices.out:
        argv.extend(["--out", str(Path(choices.out).expanduser())])


def _append_output_flags(argv: list[str], choices: GuidedChoices) -> None:
    if choices.fmt and choices.fmt != "md":
        argv.extend(["--format", choices.fmt])
    if choices.scanners and choices.scanners != "auto":
        argv.extend(["--scanners", choices.scanners])
    if choices.fail_on:
        argv.extend(["--fail-on", choices.fail_on])


def build_argv(choices: GuidedChoices) -> list[str]:
    argv = ["repolens", choices.command]
    _append_target(argv, choices)
    _append_out(argv, choices)
    _append_scope_flags(argv, choices)
    _append_model_flags(argv, choices)
    _append_output_flags(argv, choices)
    return argv


def format_command(argv: list[str]) -> str:
    return shlex.join(argv)

