"""Shared --full / --changed / --git-diff and source-target Typer option factories.

Call a factory at each command parameter default so Typer gets a fresh Option
object (shared Option instances are not safe across commands).
"""

from __future__ import annotations

from typing import Any

import typer

_FORCE_FULL_HELP = "Force full LLM file pack (ignore adaptive changed-only selection)"
_FORCE_CHANGED_HELP = (
    "LLM pack = fingerprint added/changed files only (not git diff; skip LLM if none)"
)
_GIT_DIFF_HELP = (
    "Restrict Slow Brain pack to git change-set vs BASE "
    "(ref like main, or 'auto'). Scanners/Fast Brain stay whole-tree. "
    "Conflicts with --full / --changed."
)
_PATH_HELP = "Local project root (default: .)"
_GIT_URL_HELP = "Git clone URL"
_GITHUB_HELP = "GitHub OWNER/REPO"
_BITBUCKET_HELP = "Bitbucket WORKSPACE/REPO"
_HF_HELP = "Hugging Face Hub id (ORG/NAME or datasets|spaces/ORG/NAME)"
_REF_HELP = "Branch/tag for remotes"
_TRUST_PROJECT_HELP = (
    "Allow project .repolens.toml to set provider/base_url/api_key_env"
)
_SCANNERS_HELP = "auto | off | comma list (gitleaks,semgrep,osv,trivy,checkov)"
_REQUIRE_SCANNERS_HELP = "Exit 2 if a requested scanner is missing"
_SCANNERS_ONLY_HELP = "Skip LLM; report scanner findings only"
_QUIET_HELP = "Hide progress status lines"
_VERBOSE_HELP = "Extra progress detail (file sample, scanner status)"
_HEARTBEAT_HELP = "Seconds between LLM wait heartbeats (0 disables)"
_TIMEOUT_HELP = (
    "LLM HTTP timeout in seconds (default: 900 for ollama, 120 otherwise)"
)


def option_force_full() -> Any:
    return typer.Option(False, "--full", help=_FORCE_FULL_HELP)


def option_force_changed() -> Any:
    return typer.Option(False, "--changed", help=_FORCE_CHANGED_HELP)


def option_git_diff() -> Any:
    return typer.Option(None, "--git-diff", help=_GIT_DIFF_HELP)


def option_path() -> Any:
    return typer.Option(None, "--path", help=_PATH_HELP)


def option_git_url() -> Any:
    return typer.Option(None, "--git-url", help=_GIT_URL_HELP)


def option_github() -> Any:
    return typer.Option(None, "--github", help=_GITHUB_HELP)


def option_bitbucket() -> Any:
    return typer.Option(None, "--bitbucket", help=_BITBUCKET_HELP)


def option_hf() -> Any:
    return typer.Option(None, "--hf", help=_HF_HELP)


def option_ref() -> Any:
    return typer.Option(None, "--ref", help=_REF_HELP)


def option_trust_project() -> Any:
    return typer.Option(False, "--trust-project-config", help=_TRUST_PROJECT_HELP)


def option_scanners() -> Any:
    return typer.Option("auto", "--scanners", help=_SCANNERS_HELP)


def option_require_scanners() -> Any:
    return typer.Option(False, "--require-scanners", help=_REQUIRE_SCANNERS_HELP)


def option_scanners_only() -> Any:
    return typer.Option(False, "--scanners-only", help=_SCANNERS_ONLY_HELP)


def option_quiet() -> Any:
    return typer.Option(False, "--quiet", "-q", help=_QUIET_HELP)


def option_verbose() -> Any:
    return typer.Option(False, "--verbose", "-v", help=_VERBOSE_HELP)


def option_heartbeat() -> Any:
    return typer.Option(15.0, "--heartbeat", help=_HEARTBEAT_HELP)


def option_timeout() -> Any:
    return typer.Option(None, "--timeout", help=_TIMEOUT_HELP)
