"""CLI: ``repolens plan`` — Slow Brain pack forecast (protects ``--dry-run``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from repolens.cli.app import app, console
from repolens.cli.pack_scope import option_trust_project
from repolens.cli.review_options import (
    option_plan_full_audit,
    option_plan_json,
    option_plan_mode,
    option_plan_path,
    option_plan_role_packs,
)
from repolens.config import load_config
from repolens.plan_forecast import forecast_as_dict, forecast_deep_plan


@app.command("plan")
def plan_cmd(
    path: Path = option_plan_path(),
    mode: str = option_plan_mode(),
    full_audit: bool = option_plan_full_audit(),
    role_packs: bool | None = option_plan_role_packs(),
    trust_project: bool = option_trust_project(),
    as_json: bool = option_plan_json(),
) -> None:
    """Plan (recon): inventory + Slow Brain pack preview. No LLM, no scanners.

    Distinct from ``--dry-run`` (inventory dump only). Use this to compare
    chars-in estimates with and without ``[deep] role_packs`` before an Audit.
    """
    _body_plan(path, mode, full_audit, role_packs, trust_project, as_json)


def _body_plan(
    path: Path,
    mode: str,
    full_audit: bool,
    role_packs: bool | None,
    trust_project: bool,
    as_json: bool,
) -> None:
    root = path.resolve()
    cfg = load_config(root, trust_project=trust_project)
    if role_packs is not None:
        cfg.deep.role_packs = role_packs
    plan = forecast_deep_plan(root, cfg, mode=mode, full_audit=full_audit)
    if as_json:
        typer.echo(json.dumps(forecast_as_dict(plan), indent=2))
        return
    _print_plan_table(root, plan)


def _print_plan_table(root: Path, plan: Any) -> None:
    console.print(
        f"[bold]Plan (Fast Brain recon)[/bold] — {root}\n"
        f"role_packs={'on' if plan.role_packs else 'off'} · "
        f"inventory {plan.inventory_kept} kept · LLM pool {plan.llm_pool} · "
        f"budget {plan.chars_per_pass:,} chars/pass"
    )
    console.print(plan.estimate_line)
    console.print(
        f"Sum of estimated pack chars across passes: "
        f"[cyan]{plan.total_estimated_chars:,}[/cyan] "
        "(honesty metric — not a Metis % claim)"
    )
    table = Table(title="Slow Brain packs (Audit preview)")
    table.add_column("Band")
    table.add_column("Mode")
    table.add_column("Files", justify="right")
    table.add_column("Est. chars", justify="right")
    table.add_column("Rules", justify="right")
    table.add_column("Coverage ids", justify="right")
    for row in plan.passes:
        table.add_row(
            row.name, row.pack_mode, str(row.file_count),
            f"{row.estimated_chars:,}", str(row.rule_count), str(row.coverage_id_count),
        )
    console.print(table)
    for row in plan.passes:
        if row.sample_paths:
            console.print(f"  {row.name} sample: " + ", ".join(row.sample_paths[:5]))
