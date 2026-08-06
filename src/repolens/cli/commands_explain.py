"""Phase 6: ``repolens explain <uuid>``."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import _coerce_local_path, app, console
from repolens.explain import (
    ExplainDisabledError,
    IssueNotFoundError,
    run_explain,
)
from repolens.pipeline import ReviewResult
from repolens.progress import ReviewProgress
from repolens.sources import SourceError


def run_post_review_explains(
    explain_uuids: str,
    *,
    path: str | Path | None,
    result: ReviewResult,
) -> None:
    """Deep-dive UUIDs after a successful review (best-effort; never aborts)."""
    explain_root = Path.cwd()
    if path is not None:
        try:
            coerced = _coerce_local_path(path)
            if coerced is not None:
                explain_root = coerced.resolve()
        except SourceError:
            pass
    explain_out = None
    if result.json_path is not None:
        explain_out = result.json_path.parent
    elif result.markdown_path is not None:
        explain_out = result.markdown_path.parent
    prog = ReviewProgress(verbose=True)
    for raw_uid in explain_uuids.split(","):
        uid = raw_uid.strip()
        if not uid:
            continue
        try:
            artifact = run_explain(
                uuid=uid,
                project_root=explain_root,
                out_dir=explain_out,
                progress=prog,
            )
            console.print(f"[green]Explain report:[/green] {artifact}")
        except (ExplainDisabledError, IssueNotFoundError, FileNotFoundError) as exc:
            console.print(f"[yellow]Explain skipped ({uid}):[/yellow] {exc}")


@app.command("explain")
def explain_cmd(
    uuid: str = typer.Argument(
        ...,
        help=(
            "Fingerprint or Occurrence UUID from a gate report "
            "(prefer Fingerprint; both work)"
        ),
    ),
    path: str | None = typer.Option(
        None, "--path", help="Project root (default: .)"
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Report directory containing gate JSON"
    ),
    no_diagram: bool = typer.Option(
        False, "--no-diagram", help="Skip Mermaid / diagram section generation"
    ),
    render_image: bool = typer.Option(
        False,
        "--render-image",
        help="Force optional PNG/SVG render when a renderer is available",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Extra detail under phase lines"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Silence progress (CI)"
    ),
    heartbeat: float = typer.Option(
        15.0,
        "--heartbeat",
        help="Seconds between LLM wait heartbeats (0 disables)",
    ),
) -> None:
    """Deep-dive one finding into an explain Markdown artifact."""
    try:
        local = _coerce_local_path(path) or Path(".")
    except SourceError as exc:
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=2) from None
    root = local.resolve()
    prog = ReviewProgress(
        quiet=quiet,
        verbose=verbose,
        heartbeat_seconds=heartbeat,
    )
    try:
        artifact = run_explain(
            uuid=uuid,
            project_root=root,
            out_dir=out,
            no_diagram=no_diagram,
            render_image="always" if render_image else None,
            progress=prog,
        )
    except ExplainDisabledError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except IssueNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Explain report:[/green] {artifact}")
