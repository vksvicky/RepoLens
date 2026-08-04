"""Resolve local paths and remote git sources (Phase 2 MVP)."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SourceKind = Literal["path", "git-url", "github"]

_SLUG_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")


class SourceError(Exception):
    """User-facing source / clone failure (CLI exit 2 or 3)."""


@dataclass
class ResolvedSource:
    root: Path
    ephemeral: bool
    label: str


def parse_github_slug(slug: str) -> tuple[str, str]:
    match = _SLUG_RE.fullmatch(slug.strip())
    if not match:
        raise SourceError(f"Invalid --github value {slug!r}; expected OWNER/REPO")
    return match.group(1), match.group(2)


def build_github_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def select_source(
    *,
    path: Path | None,
    git_url: str | None,
    github: str | None,
) -> tuple[SourceKind, str | Path]:
    """Return exactly one source kind. Default path is `.` when nothing else set.

    Treat ``path`` as provided only when not None. CLI should pass ``None`` when
    the user did not set ``--path``.
    """
    provided = [
        ("path", path),
        ("git-url", git_url),
        ("github", github),
    ]
    active = [(k, v) for k, v in provided if v is not None]
    if len(active) > 1:
        raise SourceError("Use exactly one source: --path, --git-url, or --github")
    if not active:
        return "path", Path(".")
    kind, value = active[0]
    if kind == "path":
        return "path", value
    assert isinstance(value, str)
    return kind, value.strip()  # type: ignore[return-value]


def resolve_github_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        completed = subprocess.run(
            [gh, "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    token = completed.stdout.strip()
    return token or None


def resolve_source(
    *,
    kind: SourceKind,
    value: str | Path,
    ref: str | None,
) -> ResolvedSource:
    if kind == "path":
        root = Path(value).expanduser().resolve()
        if not root.exists():
            raise SourceError(f"Path not found: {root}")
        if not root.is_dir():
            raise SourceError(f"Path is not a directory: {root}")
        return ResolvedSource(root=root, ephemeral=False, label=str(root))

    if kind == "github":
        owner, repo = parse_github_slug(str(value))
        url = build_github_url(owner, repo)
        label = f"github:{owner}/{repo}"
    else:
        url = str(value).strip()
        if not url:
            raise SourceError("--git-url must not be empty")
        label = f"git-url:{url}"

    return _clone_ephemeral(url=url, ref=ref, label=label)


def cleanup_source(source: ResolvedSource) -> None:
    if source.ephemeral and source.root.exists():
        # Remove the work parent (repo + empty-template)
        parent = source.root.parent
        shutil.rmtree(parent, ignore_errors=True)


def _clone_ephemeral(*, url: str, ref: str | None, label: str) -> ResolvedSource:
    work = Path(tempfile.mkdtemp(prefix="repolens-"))
    dest = work / "repo"
    # Empty template avoids copying sample hooks (fails in some sandboxed environments).
    template = work / "empty-template"
    template.mkdir()

    clone_cmd = ["git", "clone", "--depth", "1", "--template", str(template)]
    if ref:
        clone_cmd.extend(["--branch", ref])
    clone_cmd.extend([url, str(dest)])

    base_env = os.environ.copy()
    base_env.setdefault("GIT_TERMINAL_PROMPT", "0")

    # Prefer anonymous clone first so a stale gh/env token cannot break public repos.
    completed = _run_git(clone_cmd, base_env)
    if completed.returncode != 0 and _looks_like_auth_failure(completed):
        token = resolve_github_token() if "github.com" in url.lower() else None
        if token:
            shutil.rmtree(dest, ignore_errors=True)
            completed = _run_git(clone_cmd, _env_with_github_token(base_env, token))

    if completed.returncode != 0:
        shutil.rmtree(work, ignore_errors=True)
        detail = (completed.stderr or completed.stdout or "").strip()
        safe = _sanitize_git_error(detail)
        raise SourceError(f"Clone failed for {label}: {safe or 'git error'}")

    return ResolvedSource(root=dest.resolve(), ephemeral=True, label=label)


def _run_git(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)


def _env_with_github_token(base: dict[str, str], token: str) -> dict[str, str]:
    env = dict(base)
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {basic}"
    return env


def _looks_like_auth_failure(completed: subprocess.CompletedProcess[str]) -> bool:
    text = f"{completed.stderr}\n{completed.stdout}".lower()
    needles = (
        "authentication failed",
        "invalid credentials",
        "could not read username",
        "terminal prompts disabled",
        "403",
        "401",
        "permission denied",
        "repository not found",  # GitHub often hides private repos this way
    )
    return any(n in text for n in needles)


def _sanitize_git_error(text: str) -> str:
    cleaned = re.sub(r"(?i)(authorization:\s*bearer\s+)\S+", r"\1***", text)
    cleaned = re.sub(r"(?i)(://)([^/@\s]+@)", r"\1***@", cleaned)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    for ln in lines:
        if ln.lower().startswith("cloning into"):
            continue
        return ln[:300]
    return lines[0][:300] if lines else ""
