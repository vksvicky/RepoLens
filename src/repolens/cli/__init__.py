"""RepoLens CLI package — public entry points."""

from __future__ import annotations

# Register command modules (side-effect imports).
from repolens.cli import adaptive as adaptive  # noqa: F401
from repolens.cli import commands_architecture as commands_architecture  # noqa: F401
from repolens.cli import commands_baseline as commands_baseline  # noqa: F401
from repolens.cli import commands_benchmark as commands_benchmark  # noqa: F401
from repolens.cli import commands_blast_radius as commands_blast_radius  # noqa: F401
from repolens.cli import commands_check as commands_check  # noqa: F401
from repolens.cli import commands_diff_audit as commands_diff_audit  # noqa: F401
from repolens.cli import commands_duplicates as commands_duplicates  # noqa: F401
from repolens.cli import commands_explain as commands_explain  # noqa: F401
from repolens.cli import commands_feedback as commands_feedback  # noqa: F401
from repolens.cli import commands_fix as commands_fix  # noqa: F401
from repolens.cli import commands_graph as commands_graph  # noqa: F401
from repolens.cli import commands_hotspots as commands_hotspots  # noqa: F401
from repolens.cli import commands_ignore as commands_ignore  # noqa: F401
from repolens.cli import commands_journal as commands_journal  # noqa: F401
from repolens.cli import commands_modes as commands_modes  # noqa: F401
from repolens.cli import commands_packs as commands_packs  # noqa: F401
from repolens.cli import commands_plan as commands_plan  # noqa: F401
from repolens.cli import commands_portfolio as commands_portfolio  # noqa: F401
from repolens.cli import commands_pr_summary as commands_pr_summary  # noqa: F401
from repolens.cli import commands_review as commands_review  # noqa: F401
from repolens.cli import commands_view as commands_view  # noqa: F401
from repolens.cli import commands_which as commands_which  # noqa: F401
from repolens.cli import export as export  # noqa: F401
from repolens.cli import plugins as plugins  # noqa: F401
from repolens.cli.app import app, run

__all__ = ["app", "run"]
