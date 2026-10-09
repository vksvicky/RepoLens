"""Shared Typer option factories for review / sentinel / architecture / plan / check / init.

Call a factory at each command parameter default so Typer gets a fresh Option
object (shared Option instances are not safe across commands).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from repolens.cli.presets import PRESET_HELP
from repolens.pipeline.pass_cache import normalize_retry_pass, normalize_retry_passes

__all__ = ["normalize_retry_pass", "normalize_retry_passes"]

_MODE_HELP = "full | diff"
_SINCE_HELP = "Diff base ref"
_OUT_HELP = "Report directory"
_FORMAT_HELP = "md | json | both"
_MODEL_HELP = "Override model name"
_FAIL_ON_HELP = "Exit 1 if findings at/above severity"
_FAIL_ON_SHORT_HELP = "Exit 1 severity threshold"
_DRY_RUN_HELP = "Inventory only; no LLM call"
_FULL_AUDIT_HELP = "Include full architecture playbook"
_MODEL_LOCK_HELP = "Force the local model mutex on, including for a cloud URL"
_NO_MODEL_LOCK_HELP = "Allow concurrent calls to a local one-model server"
_DEEP_HELP = "Multi-pass deep coverage (default: on; --no-deep = single-shot)"
_DEEP_PASSES_HELP = "Cap deep band passes (1 = P1-only). Overrides [deep].max_passes."
_EXPLAIN_HELP = (
    "After review, deep-dive these UUID(s) "
    "(Fingerprint or Occurrence, comma-separated)"
)
_CI_HELP = (
    "PR/CI recipe: triage routing, --changed pack, single-shot LLM on scanner hits only"
)
_SARIF_HELP = "Write anchored SARIF 2.1 (scanner locations + resolvable anchors only)"
_VERIFY_FINDINGS_HELP = (
    "Re-check Critical locations (non-fatal; default: [deep].verify_findings)"
)
_PACK_HELP = "Enable a domain pack (repeatable); see `repolens packs list`"
_FALLBACK_HELP = (
    "Automatically fall back to local Ollama or SAST scanners "
    "when Cloud AI is unavailable"
)
_RATCHET_HELP = (
    "Exit 1 if runtime cyclicity exceeds the baseline "
    "(also enabled by [graph].ratchet; combines with --fail-on)"
)
_IMPORT_SARIF_HELP = (
    "Merge findings from a SARIF 2.1 file (repeatable). Treated as scanner evidence."
)
_REQUIRE_SARIF_IMPORT_HELP = (
    "Exit 2 if any --import-sarif path is missing or unreadable "
    "(default: soft-fail and continue)"
)
_RESUME_HELP = "Reuse finished Slow Brain pass cache (reads journal last-finished)"
_RETRY_PASS_HELP = (
    "With --resume, re-run only this pass (repeatable): "
    "p1|security, p2|reliability, p3|architecture. Other finished passes stay cached."
)
_ROLE_PACKS_HELP = "Override [deep] role_packs for this Audit (honesty metric; default: config)"
_PLAN_PATH_HELP = "Repository root to forecast (local path)"
_PLAN_MODE_HELP = "review | sentinel | architecture (same bands as Audit)"
_PLAN_FULL_AUDIT_HELP = "Use full-audit coverage ids when planning"
_PLAN_ROLE_PACKS_HELP = "Override [deep] role_packs for this forecast"
_PLAN_JSON_HELP = "Emit machine-readable JSON"
_CHECK_DIFF_HELP = "Compare runtime cyclicity to the baseline (graph-only ratchet)"
_CHECK_FORMAT_HELP = "sarif | jsonl — Fast Brain diagnostic stream (no LLM; no --diff needed)"
_CHECK_PATH_HELP = "Project root to analyse"
_BASELINE_HELP = (
    "Baseline JSON path (default: config baseline_path or .repolens/baseline.json)"
)
_REQUIRE_BASELINE_HELP = "Exit 2 when no baseline file is present (recommended for CI)"
_BASE_HELP = "Git diff base ref (else GITHUB_BASE_REF / merge-base / working tree)"
_INIT_PROVIDER_HELP = (
    "openai | anthropic | deepseek | openai_compatible | ollama | gemini | "
    "vertex | bedrock | none | "
    "azure | mistral | groq | openrouter | together | fireworks"
)
_INIT_PROVIDER_PROMPT = (
    "Provider (openai / anthropic / deepseek / openai_compatible / ollama / "
    "gemini / vertex / bedrock / azure / mistral / groq / openrouter / none)"
)
_INIT_MODEL_HELP = "Default model name"
_INIT_BASE_URL_HELP = (
    "Override API base URL (required for azure / most openai_compatible hosts)"
)
_INIT_FORCE_HELP = "Overwrite existing user config"


def option_review_mode() -> Any:
    return typer.Option("full", "--mode", help=_MODE_HELP)


def option_since() -> Any:
    return typer.Option(None, "--since", help=_SINCE_HELP)


def option_out() -> Any:
    return typer.Option(None, "--out", help=_OUT_HELP)


def option_format() -> Any:
    return typer.Option("md", "--format", help=_FORMAT_HELP)


def option_model() -> Any:
    return typer.Option(None, "--model", help=_MODEL_HELP)


def option_fail_on() -> Any:
    return typer.Option(None, "--fail-on", help=_FAIL_ON_HELP)


def option_fail_on_short() -> Any:
    return typer.Option(None, "--fail-on", help=_FAIL_ON_SHORT_HELP)


def option_dry_run() -> Any:
    return typer.Option(False, "--dry-run", help=_DRY_RUN_HELP)


def option_full_audit() -> Any:
    return typer.Option(False, "--full-audit", help=_FULL_AUDIT_HELP)


def option_model_lock() -> Any:
    return typer.Option(False, "--model-lock", help=_MODEL_LOCK_HELP)


def option_no_model_lock() -> Any:
    return typer.Option(False, "--no-model-lock", help=_NO_MODEL_LOCK_HELP)


def option_deep() -> Any:
    return typer.Option(None, "--deep/--no-deep", help=_DEEP_HELP)


def option_deep_passes() -> Any:
    return typer.Option(None, "--deep-passes", help=_DEEP_PASSES_HELP, min=1)


def option_explain() -> Any:
    return typer.Option(None, "--explain", help=_EXPLAIN_HELP)


def option_ci() -> Any:
    return typer.Option(False, "--ci", help=_CI_HELP)


def option_preset() -> Any:
    return typer.Option(None, "--preset", help=PRESET_HELP)


def option_sarif() -> Any:
    return typer.Option(False, "--sarif", help=_SARIF_HELP)


def option_verify_findings() -> Any:
    return typer.Option(
        None, "--verify-findings/--no-verify-findings", help=_VERIFY_FINDINGS_HELP
    )


def option_pack() -> Any:
    return typer.Option(None, "--pack", help=_PACK_HELP)


def option_fallback() -> Any:
    return typer.Option(True, "--fallback/--no-fallback", help=_FALLBACK_HELP)


def option_ratchet() -> Any:
    return typer.Option(False, "--ratchet", help=_RATCHET_HELP)


def option_ratchet_default_on() -> Any:
    """``repolens audit`` defaults ratchet on; ``--no-ratchet`` opts out."""
    return typer.Option(True, "--ratchet/--no-ratchet", help=_RATCHET_HELP)


def option_import_sarif() -> Any:
    return typer.Option(None, "--import-sarif", help=_IMPORT_SARIF_HELP)


def option_require_sarif_import() -> Any:
    return typer.Option(False, "--require-sarif-import", help=_REQUIRE_SARIF_IMPORT_HELP)


def option_resume() -> Any:
    return typer.Option(True, "--resume/--no-resume", help=_RESUME_HELP)


def option_retry_pass() -> Any:
    return typer.Option(None, "--retry-pass", help=_RETRY_PASS_HELP)


def option_role_packs() -> Any:
    return typer.Option(None, "--role-packs/--no-role-packs", help=_ROLE_PACKS_HELP)


def option_plan_path() -> Any:
    return typer.Option(
        Path("."),
        "--path",
        help=_PLAN_PATH_HELP,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )


def option_plan_mode() -> Any:
    return typer.Option("review", "--mode", help=_PLAN_MODE_HELP)


def option_plan_full_audit() -> Any:
    return typer.Option(False, "--full-audit", help=_PLAN_FULL_AUDIT_HELP)


def option_plan_role_packs() -> Any:
    return typer.Option(None, "--role-packs/--no-role-packs", help=_PLAN_ROLE_PACKS_HELP)


def option_plan_json() -> Any:
    return typer.Option(False, "--json", help=_PLAN_JSON_HELP)


def option_check_diff() -> Any:
    return typer.Option(False, "--diff", help=_CHECK_DIFF_HELP)


def option_check_format() -> Any:
    return typer.Option("", "--format", help=_CHECK_FORMAT_HELP)


def option_check_path() -> Any:
    return typer.Option(Path("."), "--path", help=_CHECK_PATH_HELP)


def option_baseline() -> Any:
    return typer.Option(None, "--baseline", help=_BASELINE_HELP)


def option_require_baseline() -> Any:
    return typer.Option(False, "--require-baseline", help=_REQUIRE_BASELINE_HELP)


def option_base() -> Any:
    return typer.Option(None, "--base", help=_BASE_HELP)


def option_init_provider() -> Any:
    return typer.Option(
        ..., "--provider", help=_INIT_PROVIDER_HELP, prompt=_INIT_PROVIDER_PROMPT
    )


def option_init_model() -> Any:
    return typer.Option(None, "--model", help=_INIT_MODEL_HELP)


def option_init_base_url() -> Any:
    return typer.Option(None, "--base-url", help=_INIT_BASE_URL_HELP)


def option_init_force() -> Any:
    return typer.Option(False, "--force", help=_INIT_FORCE_HELP)
