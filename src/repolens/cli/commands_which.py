"""Deterministic ``repolens which`` catalog. No pipeline, model, or network."""

from __future__ import annotations

import json
from dataclasses import dataclass

import typer

from repolens.cli.app import app, console

_SCENARIOS = (
    "pr",
    "changed",
    "release",
    "audit",
    "m-and-a",
    "security",
    "architecture",
)


@dataclass(frozen=True)
class _Entry:
    command: str
    why: str


_CATALOG: dict[str, _Entry] = {
    "pr": _Entry(
        "repolens review --preset pr --path .",
        "Scanners only, --no-deep, no LLM",
    ),
    "changed": _Entry(
        "repolens review --preset changed --path .",
        "--git-diff auto --deep, timeout 900",
    ),
    "release": _Entry(
        "repolens review --preset release --path .",
        "--full --full-audit --deep, timeout 3600",
    ),
    "audit": _Entry(
        "repolens audit --path .",
        "Release preset plus ratchet and verify (audit takes no --preset)",
    ),
    "m-and-a": _Entry(
        "repolens audit --path .",
        "Release preset plus ratchet and verify (audit takes no --preset)",
    ),
    "security": _Entry(
        "repolens sentinel --path .",
        "P1 only",
    ),
    "architecture": _Entry(
        "repolens architecture --path .",
        "P3 only (P2 stays inside review)",
    ),
}


def _unknown(scenario: str) -> None:
    names = " | ".join(_SCENARIOS)
    console.print(f"[red]Unknown scenario: {scenario}[/red]")
    console.print(f"Valid scenarios: {names}")
    raise typer.Exit(code=2)


@app.command("which")
def which(
    scenario: str = typer.Argument(
        ...,
        help="Scenario: pr | changed | release | audit | m-and-a | security | architecture",
    ),
    explain: bool = typer.Option(False, "--explain", help="Print why these flags"),
    json_out: bool = typer.Option(False, "--json", help="Print scenario, command, and why as JSON"),
) -> None:
    """Print the RepoLens command for a known audit scenario."""
    entry = _CATALOG.get(scenario.strip().lower())
    if entry is None:
        _unknown(scenario)
        return
    if json_out:
        print(
            json.dumps(
                {"scenario": scenario.strip().lower(), "command": entry.command, "why": entry.why}
            )
        )
        return
    print(entry.command)
    if explain:
        print(entry.why)
