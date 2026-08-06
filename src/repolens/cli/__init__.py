"""RepoLens CLI package — public entry points."""

from __future__ import annotations

from repolens.cli.app import app, run

# Register command modules (side-effect imports).
from repolens.cli import adaptive as adaptive  # noqa: F401
from repolens.cli import commands_benchmark as commands_benchmark  # noqa: F401
from repolens.cli import commands_explain as commands_explain  # noqa: F401
from repolens.cli import commands_feedback as commands_feedback  # noqa: F401
from repolens.cli import commands_review as commands_review  # noqa: F401
from repolens.cli import export as export  # noqa: F401
from repolens.cli import plugins as plugins  # noqa: F401

__all__ = ["app", "run"]
