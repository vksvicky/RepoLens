"""``repolens portfolio`` — offline multi-repo batch audit."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.portfolio import run_portfolio


@app.command("portfolio")
def portfolio_cmd(
    paths_file: Path = typer.Option(
        ...,
        "--paths-file",
        exists=True,
        readable=True,
        dir_okay=False,
        help="Text file: one repo path per line (# comments ok)",
    ),
    out: Path = typer.Option(
        Path("portfolio-reports"),
        "--out",
        help="Directory for per-repo reports + index.md",
    ),
    slow_brain: bool = typer.Option(
        False,
        "--slow-brain/--no-slow-brain",
        help="Enable Slow Brain / LLM (off by default for cost)",
    ),
) -> None:
    """Batch Fast Brain + scanners across repos; soft-fail; write index.md rollup."""
    try:
        result = run_portfolio(paths_file, out, slow_brain=slow_brain)
    except (OSError, ValueError) as exc:
        console.print(f"[red]portfolio failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    ok = sum(1 for r in result.repos if r.ok)
    failed = len(result.repos) - ok
    console.print(
        f"[green]Portfolio[/green] {ok} ok · {failed} failed → {result.index_path}"
    )
    raise typer.Exit(code=result.exit_code)