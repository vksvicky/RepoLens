"""Shared --full / --changed / --git-diff Typer option factories.

Call a factory at each command parameter default so Typer gets a fresh Option
object (shared Option instances are not safe across commands).
"""

from __future__ import annotations

from typing import Any

import typer

_FORCE_FULL_HELP = "Force full LLM file pack (ignore adaptive changed-only selection)"
_FORCE_CHANGED_HELP = (
    "LLM pack = fingerprint added/changed files only (not git diff; skip LLM if none)"
)
_GIT_DIFF_HELP = (
    "Restrict Slow Brain pack to git change-set vs BASE "
    "(ref like main, or 'auto'). Scanners/Fast Brain stay whole-tree. "
    "Conflicts with --full / --changed."
)


def option_force_full() -> Any:
    return typer.Option(False, "--full", help=_FORCE_FULL_HELP)


def option_force_changed() -> Any:
    return typer.Option(False, "--changed", help=_FORCE_CHANGED_HELP)


def option_git_diff() -> Any:
    return typer.Option(None, "--git-diff", help=_GIT_DIFF_HELP)
