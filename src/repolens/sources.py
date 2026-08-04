"""Resolve local paths and remote git sources (Phase 2)."""

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

SourceKind = Literal["path", "git-url", "github", "bitbucket", "hf"]

_SLUG_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
_HF_ID_RE = re.compile(
    r"^(?:(datasets|spaces|models)/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$"
)


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


def parse_bitbucket_slug(slug: str) -> tuple[str, str]:
    match = _SLUG_RE.fullmatch(slug.strip())
    if not match:
        raise SourceError(
            f"Invalid --bitbucket value {slug!r}; expected WORKSPACE/REPO"
        )
    return match.group(1), match.group(2)


def parse_hf_id(repo_id: str) -> str:
    """Normalize a Hugging Face Hub git repo id (model/dataset/space)."""
    raw = repo_id.strip().strip("/")
    match = _HF_ID_RE.fullmatch(raw)
    if not match:
        raise SourceError(
            f"Invalid --hf value {repo_id!r}; expected "
            "ORG/NAME or datasets|spaces|models/ORG/NAME"
        )
    prefix, org, name = match.group(1), match.group(2), match.group(3)
    if prefix and prefix != "models":
        return f"{prefix}/{org}/{name}"
    return f"{org}/{name}"


def build_github_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def build_bitbucket_url(workspace: str, repo: str) -> str:
    return f"https://bitbucket.org/{workspace}/{repo}.git"


def build_hf_url(repo_id: str) -> str:
    return f"https://huggingface.co/{repo_id}"


def select_source(
    *,
    path: Path | None,
    git_url: str | None,
    github: str | None,
    bitbucket: str | None = None,
    hf: str | None = None,
) -> tuple[SourceKind, str | Path]:
    """Return exactly one source kind. Default path is `.` when nothing else set."""
    provided = [
        ("path", path),
        ("git-url", git_url),
        ("github", github),
        ("bitbucket", bitbucket),
        ("hf", hf),
    ]
    active = [(k, v) for k, v in provided if v is not None]
    if len(active) > 1:
        raise SourceError(
            "Use exactly one source: --path, --git-url, --github, --bitbucket, or --hf"
        )
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


def resolve_bitbucket_token() -> str | None:
    for name in ("BITBUCKET_TOKEN", "BITBUCKET_APP_PASSWORD"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def resolve_hf_token() -> str | None:
    value = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    return value.strip() if value else None


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
    elif kind == "bitbucket":
        workspace, repo = parse_bitbucket_slug(str(value))
        url = build_bitbucket_url(workspace, repo)
        label = f"bitbucket:{workspace}/{repo}"
    elif kind == "hf":
        repo_id = parse_hf_id(str(value))
        url = build_hf_url(repo_id)
        label = f"hf:{repo_id}"
    else:
        url = str(value).strip()
        if not url:
            raise SourceError("--git-url must not be empty")
        label = f"git-url:{url}"

    return _clone_ephemeral(url=url, ref=ref, label=label)


def cleanup_source(source: ResolvedSource) -> None:
    if source.ephemeral and source.root.exists():
        parent = source.root.parent
        shutil.rmtree(parent, ignore_errors=True)


def _clone_ephemeral(*, url: str, ref: str | None, label: str) -> ResolvedSource:
    work = Path(tempfile.mkdtemp(prefix="repolens-"))
    dest = work / "repo"
    template = work / "empty-template"
    template.mkdir()

    clone_cmd = ["git", "clone", "--depth", "1", "--template", str(template)]
    if ref:
        clone_cmd.extend(["--branch", ref])
    clone_cmd.extend([url, str(dest)])

    base_env = os.environ.copy()
    base_env.setdefault("GIT_TERMINAL_PROMPT", "0")

    completed = _run_git(clone_cmd, base_env)
    if completed.returncode != 0 and _looks_like_auth_failure(completed):
        token_env = _token_env_for_url(base_env, url)
        if token_env is not None:
            shutil.rmtree(dest, ignore_errors=True)
            completed = _run_git(clone_cmd, token_env)

    if completed.returncode != 0:
        shutil.rmtree(work, ignore_errors=True)
        detail = (completed.stderr or completed.stdout or "").strip()
        safe = _sanitize_git_error(detail)
        raise SourceError(f"Clone failed for {label}: {safe or 'git error'}")

    return ResolvedSource(root=dest.resolve(), ephemeral=True, label=label)


def _run_git(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)


def _token_env_for_url(base: dict[str, str], url: str) -> dict[str, str] | None:
    lower = url.lower()
    if "github.com" in lower:
        token = resolve_github_token()
        if not token:
            return None
        return _env_with_basic_auth(base, "x-access-token", token)
    if "bitbucket.org" in lower:
        token = resolve_bitbucket_token()
        if not token:
            return None
        # Access tokens: x-token-auth; app passwords need BITBUCKET_USERNAME.
        user = os.environ.get("BITBUCKET_USERNAME", "x-token-auth").strip() or "x-token-auth"
        return _env_with_basic_auth(base, user, token)
    if "huggingface.co" in lower:
        token = resolve_hf_token()
        if not token:
            return None
        # HF git accepts Bearer or user/token basic auth.
        return _env_with_bearer(base, token)
    return None


def _env_with_basic_auth(base: dict[str, str], username: str, token: str) -> dict[str, str]:
    env = dict(base)
    basic = base64.b64encode(f"{username}:{token}".encode()).decode()
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {basic}"
    return env


def _env_with_bearer(base: dict[str, str], token: str) -> dict[str, str]:
    env = dict(base)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: Bearer {token}"
    return env


def _env_with_github_token(base: dict[str, str], token: str) -> dict[str, str]:
    """Backward-compatible helper used by older tests/callers."""
    return _env_with_basic_auth(base, "x-access-token", token)


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
        "repository not found",
        "access denied",
        "unauthorized",
    )
    return any(n in text for n in needles)


def _sanitize_git_error(text: str) -> str:
    cleaned = re.sub(r"(?i)(authorization:\s*(?:bearer|basic)\s+)\S+", r"\1***", text)
    cleaned = re.sub(r"(?i)(://)([^/@\s]+@)", r"\1***@", cleaned)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    for ln in lines:
        if ln.lower().startswith("cloning into"):
            continue
        return ln[:300]
    return lines[0][:300] if lines else ""
