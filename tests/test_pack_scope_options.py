"""Shared --full / --changed / --git-diff CLI option defaults."""

from __future__ import annotations

import typer

from repolens.cli.pack_scope import (
    option_force_changed,
    option_force_full,
    option_git_diff,
)


def test_pack_scope_options_expose_the_shared_flags() -> None:
    full = option_force_full()
    changed = option_force_changed()
    git_diff = option_git_diff()
    assert isinstance(full, typer.models.OptionInfo)
    assert isinstance(changed, typer.models.OptionInfo)
    assert isinstance(git_diff, typer.models.OptionInfo)
    assert full.param_decls == ("--full",)
    assert changed.param_decls == ("--changed",)
    assert git_diff.param_decls == ("--git-diff",)
    assert full.default is False
    assert changed.default is False
    assert git_diff.default is None
    assert "Scanners/Fast Brain stay whole-tree" in (git_diff.help or "")


def test_pack_scope_option_factories_return_fresh_defaults() -> None:
    """Typer mutates option objects; share factories, not a single Option instance."""
    assert option_force_full() is not option_force_full()
    assert option_git_diff() is not option_git_diff()
