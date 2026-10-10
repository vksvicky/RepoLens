"""``repolens view`` — local interactive HTML report (stdlib only)."""

from __future__ import annotations

import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer

import typer

from repolens.cli.app import app, console
from repolens.cli.pack_scope import option_path
from repolens.diff_audit import load_report
from repolens.explain import load_latest_report
from repolens.report_view import write_view_html


@app.command("view")
def view_cmd(
    report: Path | None = typer.Argument(
        None,
        help="FindingReport JSON (default: newest under --path reports)",
    ),
    path: str | None = option_path(),
    out: Path | None = typer.Option(
        None, "--out", help="Write HTML here (default: next to the report)"
    ),
    serve: bool = typer.Option(
        False,
        "--serve",
        help="Serve the HTML on localhost (stdlib http.server) until Ctrl-C",
    ),
    port: int = typer.Option(8765, "--port", help="Port for --serve"),
    no_open: bool = typer.Option(
        False, "--no-open", help="Do not open a browser tab"
    ),
) -> None:
    """Filterable local HTML viewer — zero heavy frontend stack."""
    root = Path(path or ".").resolve()
    try:
        if report is not None:
            rep = load_report(report)
            report_path = report.resolve()
        else:
            rep, report_path = load_latest_report(root)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(f"[red]view failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    dest = out or report_path.with_suffix(".html")
    if dest.suffix.lower() != ".html":
        dest = dest / f"{report_path.stem}.html"
    html_path = write_view_html(rep, dest)
    console.print(f"[green]Wrote[/green] {html_path}")

    if serve:
        directory = html_path.parent

        class _Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                super().__init__(*args, directory=str(directory), **kwargs)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                console.print(f"[dim]http[/dim] {args[0] if args else format}")

        server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        url = f"http://127.0.0.1:{port}/{html_path.name}"
        console.print(f"[green]Serving[/green] {url}  (Ctrl-C to stop)")
        if not no_open:
            Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("Stopped.")
        finally:
            server.server_close()
        return

    if not no_open:
        webbrowser.open(html_path.resolve().as_uri())
