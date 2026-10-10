"""Build the resolved RepoLens argv and a sanitized invocation string.

The pipeline must not re-parse ``sys.argv``. Callers in the CLI construct a
``ResolvedInvocation`` after preset resolution and pass the result through
``ReviewRun``.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_URL_FLAGS = frozenset({"--git-url", "--hf"})


@dataclass(frozen=True)
class ResolvedInvocation:
    """Flags that change an audit, after presets and audit defaults."""

    mode: str
    path: str | None = None
    git_url: str | None = None
    github: str | None = None
    bitbucket: str | None = None
    hf: str | None = None
    ref: str | None = None
    force_full: bool = False
    force_changed: bool = False
    full_audit: bool = False
    scanners_only: bool = False
    deep: bool | None = None
    timeout: float | None = None
    git_diff: str | None = None
    scanners: str | None = None
    fail_on: str | None = None
    ratchet: bool = False
    verify_findings: bool | None = None
    out: str | None = None
    fmt: str | None = None
    ci: bool = False
    model: str | None = None
    deep_passes: int | None = None
    sarif: bool = False
    role_packs: bool | None = None
    import_sarif: tuple[str, ...] = ()
    require_scanners: bool = False
    since: str | None = None
    retry_passes: tuple[str, ...] = ()
    packs: tuple[str, ...] = ()
    trust_project: bool = False
    dry_run: bool = False
    review_mode: str | None = None
    require_sarif_import: bool = False
    fallback: bool | None = None
    model_lock: bool | None = None


def strip_url_userinfo(value: str) -> str:
    """Drop ``user:password@`` from an HTTP(S) URL. Other strings pass through."""
    if "://" not in value or "@" not in value:
        return value
    parts = urlsplit(value)
    if parts.username is None and parts.password is None:
        return value
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parts.port}" if parts.port is not None else host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _timeout_token(timeout: float) -> str:
    if float(timeout).is_integer():
        return str(int(timeout))
    return str(timeout)


def _extend_flag(argv: list[str], flag: str, value: str | None = None) -> None:
    argv.append(flag)
    if value is not None:
        argv.append(value)


def _append_target(argv: list[str], inv: ResolvedInvocation) -> None:
    if inv.git_url:
        _extend_flag(argv, "--git-url", strip_url_userinfo(inv.git_url))
    if inv.github:
        _extend_flag(argv, "--github", inv.github)
    if inv.bitbucket:
        _extend_flag(argv, "--bitbucket", inv.bitbucket)
    if inv.hf:
        _extend_flag(argv, "--hf", strip_url_userinfo(inv.hf))
    if inv.ref:
        _extend_flag(argv, "--ref", inv.ref)
    if inv.path:
        _extend_flag(argv, "--path", inv.path)


def _append_scope(argv: list[str], inv: ResolvedInvocation) -> None:
    if inv.dry_run:
        argv.append("--dry-run")
    if inv.scanners_only:
        argv.append("--scanners-only")
    if inv.force_full:
        argv.append("--full")
    if inv.force_changed:
        argv.append("--changed")
    if inv.git_diff:
        _extend_flag(argv, "--git-diff", inv.git_diff)
    if inv.full_audit:
        argv.append("--full-audit")
    if inv.deep is True:
        argv.append("--deep")
    elif inv.deep is False:
        argv.append("--no-deep")
    if inv.deep_passes is not None:
        _extend_flag(argv, "--deep-passes", str(inv.deep_passes))
    if inv.timeout is not None:
        _extend_flag(argv, "--timeout", _timeout_token(inv.timeout))
    if inv.ratchet:
        argv.append("--ratchet")
    if inv.verify_findings is True:
        argv.append("--verify-findings")
    elif inv.verify_findings is False:
        argv.append("--no-verify-findings")


def _append_output(argv: list[str], inv: ResolvedInvocation) -> None:
    if inv.out:
        _extend_flag(argv, "--out", inv.out)
    if inv.review_mode and inv.review_mode != "full":
        _extend_flag(argv, "--mode", inv.review_mode)
    if inv.since:
        _extend_flag(argv, "--since", inv.since)
    if inv.scanners and inv.scanners.strip().lower() != "auto":
        _extend_flag(argv, "--scanners", inv.scanners)
    if inv.fail_on:
        _extend_flag(argv, "--fail-on", inv.fail_on)
    if inv.fmt and inv.fmt != "md":
        _extend_flag(argv, "--format", inv.fmt)
    if inv.ci:
        argv.append("--ci")
    if inv.model:
        _extend_flag(argv, "--model", inv.model)
    if inv.sarif:
        argv.append("--sarif")
    if inv.role_packs is True:
        argv.append("--role-packs")
    elif inv.role_packs is False:
        argv.append("--no-role-packs")
    for path in inv.import_sarif:
        _extend_flag(argv, "--import-sarif", path)
    if inv.require_scanners:
        argv.append("--require-scanners")
    if inv.require_sarif_import:
        argv.append("--require-sarif-import")
    for name in inv.retry_passes:
        _extend_flag(argv, "--retry-pass", name)
    for name in inv.packs:
        _extend_flag(argv, "--pack", name)
    if inv.trust_project:
        argv.append("--trust-project-config")
    if inv.fallback is False:
        argv.append("--no-fallback")
    if inv.model_lock is True:
        argv.append("--model-lock")
    elif inv.model_lock is False:
        argv.append("--no-model-lock")


def build_expanded_argv(inv: ResolvedInvocation) -> list[str]:
    """Return the argv a reader can re-run. Typer defaults are omitted."""
    argv = ["repolens", inv.mode]
    _append_target(argv, inv)
    _append_scope(argv, inv)
    _append_output(argv, inv)
    return argv


def _is_repolens_process(argv: list[str]) -> bool:
    if not argv:
        return False
    name = Path(argv[0]).name.lower()
    if name in {"repolens", "repolens.exe"}:
        return True
    return (
        len(argv) >= 3
        and name.startswith("python")
        and argv[1] == "-m"
        and argv[2].split(".")[0] == "repolens"
    )


def _normalized_argv(argv: list[str]) -> list[str]:
    if (
        len(argv) >= 3
        and Path(argv[0]).name.lower().startswith("python")
        and argv[1] == "-m"
        and argv[2].split(".")[0] == "repolens"
    ):
        rest = argv[3:]
    else:
        rest = argv[1:]
    out = ["repolens"]
    index = 0
    while index < len(rest):
        token = rest[index]
        if token in _URL_FLAGS and index + 1 < len(rest):
            out.append(token)
            out.append(strip_url_userinfo(rest[index + 1]))
            index += 2
            continue
        out.append(strip_url_userinfo(token))
        index += 1
    return out


def sanitize_invoked_command(argv: list[str]) -> str:
    """Normalize ``argv[0]`` to ``repolens`` and strip URL userinfo."""
    return shlex.join(_normalized_argv(argv))


def command_for_provenance(fallback_argv: list[str]) -> str:
    """Record the operator command when this process is the ``repolens`` CLI.

    Test runners and library callers keep the resolved argv instead of the
    pytest command line.
    """
    if _is_repolens_process(sys.argv):
        return sanitize_invoked_command(sys.argv)
    return shlex.join(fallback_argv)
