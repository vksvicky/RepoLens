"""Deterministic Slow Brain pack forecast (Plan recon — not --dry-run)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.deep import DeepPass, estimate_outline_chars, plan_deep_passes
from repolens.heuristics import run_heuristics
from repolens.inventory import scan_inventory
from repolens.rules.registry import load_enabled_rules
from repolens.runtime_estimate import estimate_deep_runtime, estimate_deep_runtime_minutes


@dataclass(frozen=True)
class PassForecast:
    name: str
    pack_mode: str
    file_count: int
    estimated_chars: int
    rule_count: int
    coverage_id_count: int
    sample_paths: list[str]


@dataclass(frozen=True)
class PlanForecast:
    root: str
    role_packs: bool
    inventory_kept: int
    llm_pool: int
    chars_per_pass: int
    provider: str
    estimate_minutes: int
    estimate_line: str
    total_estimated_chars: int
    passes: list[PassForecast]


def _pass_char_estimate(deep_pass: DeepPass) -> int:
    mode = getattr(deep_pass, "pack_mode", "full")
    modes = getattr(deep_pass, "file_pack_modes", None) or {}
    if mode == "outline":
        return sum(estimate_outline_chars(entry) for entry in deep_pass.files)
    if mode == "hybrid":
        total = 0
        for entry in deep_pass.files:
            if modes.get(entry.relative, "outline") == "full":
                total += int(entry.size)
            else:
                total += estimate_outline_chars(entry)
        return total
    return sum(int(entry.size) for entry in deep_pass.files)


def forecast_deep_plan(
    root: Path,
    cfg: RepoLensConfig,
    *,
    mode: str = "review",
    full_audit: bool = False,
) -> PlanForecast:
    """Inventory + plan_deep_passes only. Never calls an LLM or scanners."""
    fast_files, llm_files, passes = _plan_forecast_passes(
        root, cfg, mode=mode, full_audit=full_audit
    )
    forecasts = [
        PassForecast(
            name=p.name,
            pack_mode=getattr(p, "pack_mode", "full"),
            file_count=len(p.files),
            estimated_chars=_pass_char_estimate(p),
            rule_count=len(p.rule_ids),
            coverage_id_count=len(p.coverage_ids),
            sample_paths=[e.relative for e in p.files[:8]],
        )
        for p in passes
    ]
    minutes, estimate_line, provider = _forecast_runtime(cfg, forecasts)
    return PlanForecast(
        root=str(root),
        role_packs=bool(cfg.deep.role_packs),
        inventory_kept=len(fast_files),
        llm_pool=len(llm_files),
        chars_per_pass=cfg.deep.chars_per_pass,
        provider=provider,
        estimate_minutes=minutes,
        estimate_line=estimate_line,
        total_estimated_chars=sum(f.estimated_chars for f in forecasts),
        passes=forecasts,
    )


def _plan_forecast_passes(
    root: Path,
    cfg: RepoLensConfig,
    *,
    mode: str,
    full_audit: bool,
) -> tuple[list, list, list]:
    inv = scan_inventory(
        root,
        mode="full",
        max_files=cfg.fast_brain.max_files,
        skip_globs=cfg.deep.skip_paths,
    )
    fast_files = list(inv.files)
    llm_cap = cfg.general.max_files
    llm_files = fast_files if llm_cap <= 0 else fast_files[:llm_cap]
    heur = run_heuristics(
        root,
        fast_files,
        mega_file_lines=cfg.deep.mega_file_lines,
        mega_file_exclude_globs=cfg.deep.extra_skip_globs() or None,
        pack_ids=list(cfg.packs.resolved()) or None,
        workers=cfg.fast_brain.parallel_workers,
        near_clones_config=cfg.fast_brain.near_clones,
    )
    rules = load_enabled_rules(project_root=root)
    graph = None
    if cfg.deep.role_packs:
        from repolens.graph import analyse_repo_graph

        graph = analyse_repo_graph(root, config=cfg.graph)
    passes = plan_deep_passes(
        mode,
        full_audit=full_audit,
        entries=llm_files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
        max_passes=cfg.deep.max_passes,
        role_packs=bool(cfg.deep.role_packs),
        graph=graph,
    )
    return fast_files, llm_files, passes


def _forecast_runtime(
    cfg: RepoLensConfig, forecasts: list[PassForecast]
) -> tuple[int, str, str]:
    file_proxy = max((f.file_count for f in forecasts), default=0)
    provider = cfg.model.provider or "unknown"
    if cfg.deep.role_packs and forecasts:
        minutes = sum(
            estimate_deep_runtime_minutes(
                files=f.file_count, passes=1, provider=provider
            )
            for f in forecasts
        )
        estimate_line = (
            "Slow Brain estimate (role_packs): "
            + " + ".join(f"{f.name}={f.file_count}f/{f.pack_mode}" for f in forecasts)
            + f" via {provider} → ~{minutes} min lower band"
        )
    else:
        minutes = estimate_deep_runtime_minutes(
            files=file_proxy, passes=len(forecasts), provider=provider
        )
        estimate_line = estimate_deep_runtime(
            files=file_proxy, passes=len(forecasts), provider=provider
        )
    return minutes, estimate_line, provider


def forecast_as_dict(plan: PlanForecast) -> dict:
    return {
        "root": plan.root,
        "role_packs": plan.role_packs,
        "inventory_kept": plan.inventory_kept,
        "llm_pool": plan.llm_pool,
        "chars_per_pass": plan.chars_per_pass,
        "provider": plan.provider,
        "estimate_minutes": plan.estimate_minutes,
        "estimate_line": plan.estimate_line,
        "total_estimated_chars": plan.total_estimated_chars,
        "passes": [asdict(p) for p in plan.passes],
    }
