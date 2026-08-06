"""Assemble CLI argv for CI / GitHub Action (pure helpers, easy to test)."""

from __future__ import annotations

import os
from collections.abc import Mapping

KNOWN_KEY_ENVS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "REPOLENS_API_KEY",
)

VALID_MODES = frozenset({"review", "sentinel", "architecture"})
VALID_RUNS = frozenset({"auto", "dry-run", "scanners-only", "llm"})


def has_llm_api_key(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return any(bool(env.get(name, "").strip()) for name in KNOWN_KEY_ENVS)


def build_review_argv(
    *,
    mode: str = "review",
    path: str = ".",
    run: str = "auto",
    fail_on: str = "HIGH",
    scanners: str = "auto",
    require_scanners: bool = False,
    has_key: bool | None = None,
    ci: bool = True,
) -> list[str]:
    """Return argv starting with ``repolens`` for subprocess / shell use.

    Default ``ci=True`` matches the enterprise PR recipe (triage routing).
    """
    mode_norm = mode.strip().lower()
    run_norm = run.strip().lower()
    if mode_norm not in VALID_MODES:
        raise ValueError(f"Invalid mode {mode!r}; use review|sentinel|architecture")
    if run_norm not in VALID_RUNS:
        raise ValueError(f"Invalid run {run!r}; use auto|dry-run|scanners-only|llm")

    key_present = has_llm_api_key() if has_key is None else has_key
    if run_norm == "llm" and not key_present:
        raise ValueError(
            "run=llm requires an API key env "
            f"({', '.join(KNOWN_KEY_ENVS)}). See docs/setup-ai-and-scanners.md"
        )

    effective = run_norm
    if run_norm == "auto":
        effective = "llm" if key_present else "scanners-only"

    argv: list[str] = ["repolens", mode_norm, "--path", path, "--format", "both"]
    if scanners:
        argv.extend(["--scanners", scanners])
    if require_scanners:
        argv.append("--require-scanners")
    if fail_on.strip():
        argv.extend(["--fail-on", fail_on.strip()])
    if ci and effective != "dry-run":
        argv.append("--ci")

    if effective == "dry-run":
        argv.append("--dry-run")
    elif effective == "scanners-only":
        argv.append("--scanners-only")
    # llm / full review: no extra flag

    return argv
