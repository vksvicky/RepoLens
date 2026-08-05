"""CLI capability probes and Ollama model discovery."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RemoteKind = Literal["github", "git-url", "bitbucket", "hf"]

_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HF_RE = re.compile(
    r"^(datasets/|spaces/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
)
_GIT_URL_RE = re.compile(r"^(https?://|git@|ssh://).+", re.IGNORECASE)


def _has_cli_flag(help_text: str, flag: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", help_text) is not None


def run_capture(
    argv: list[str],
    *,
    timeout: float,
) -> str:
    """Run a command; return combined stdout/stderr, or '' on any failure."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return f"{proc.stdout or ''}{proc.stderr or ''}"
    except Exception:  # noqa: BLE001 — guided UX must not crash on probe failures
        return ""


def validate_remote_value(kind: RemoteKind, value: str) -> str | None:
    """Return an error message if ``value`` is invalid for ``kind``, else None."""
    text = value.strip()
    if not text:
        return "Value cannot be empty."
    if kind in {"github", "bitbucket"}:
        if not _OWNER_REPO_RE.match(text):
            return "Expected owner/repo (letters, digits, ., _, -)."
        return None
    if kind == "hf":
        if not _HF_RE.match(text):
            return "Expected org/name or datasets|spaces/org/name."
        return None
    if kind == "git-url":
        if not _GIT_URL_RE.match(text):
            return "Expected a git URL (https://, git@, or ssh://)."
        return None
    return None


def default_local_path(environ: Mapping[str, str] | None = None) -> str:
    """Prefer TARGET / REPOLENS_PATH when set (docs use TARGET=…); else cwd."""
    env = os.environ if environ is None else environ
    for key in ("TARGET", "REPOLENS_PATH"):
        raw = (env.get(key) or "").strip()
        if raw:
            return str(Path(raw).expanduser())
    return "."


def suggest_timeout_seconds(model: str | None) -> float:
    """Default HTTP timeout hint from model size tags in the name."""
    name = (model or "").lower()
    if re.search(r"(?<!\d)(70|72|65)b\b", name):
        return 3600.0
    if re.search(r"(?<!\d)32b\b", name):
        return 3600.0
    if re.search(r"(?<!\d)14b\b", name):
        return 1800.0
    return 900.0


def is_large_local_model(model: str | None) -> bool:
    """True when the name looks like a heavy local LLM (14B+)."""
    return suggest_timeout_seconds(model) >= 1800.0


def full_pack_large_model_warning(
    *,
    model: str | None,
    force_full: bool,
    force_changed: bool,
) -> str | None:
    """Warn when a large model is paired with a likely full LLM pack."""
    if not is_large_local_model(model) or force_changed:
        return None
    if force_full:
        pack = "forced full pack (--full)"
    else:
        pack = "adaptive pack (unchanged repos stay full)"
    return (
        f"Warning: {model} is a large local model with a likely {pack}. "
        "Expect a very large prompt and long runtimes; prefer "
        "'Changed files only', or set timeout to "
        f"{int(suggest_timeout_seconds(model))}s+."
    )


@dataclass(frozen=True)
class ReviewCliCaps:
    """Flags present in `repolens review --help` for this install."""

    supports_verbose: bool
    supports_timeout: bool
    supports_full: bool
    supports_changed: bool
    supports_deep: bool


def probe_review_cli_caps() -> ReviewCliCaps:
    """Probe once which optional review flags the local CLI documents."""
    help_text = run_capture(["repolens", "review", "--help"], timeout=10)
    return ReviewCliCaps(
        supports_verbose=_has_cli_flag(help_text, "--verbose"),
        supports_timeout=_has_cli_flag(help_text, "--timeout"),
        supports_full=_has_cli_flag(help_text, "--full"),
        supports_changed=_has_cli_flag(help_text, "--changed"),
        supports_deep=_has_cli_flag(help_text, "--deep"),
    )


def parse_ollama_list(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        token = line.split()[0]
        if token and token.lower() != "name":
            names.append(token)
    return names


def parse_ollama_tags_json(payload: Mapping[str, Any] | object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def list_installed_models() -> list[str]:
    listed = run_capture(["ollama", "list"], timeout=3)
    if listed.strip():
        # run_capture merges stderr; parse_ollama_list ignores junk lines.
        names = parse_ollama_list(listed)
        if names:
            return names
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=1
        ) as resp:
            payload = json.loads(resp.read().decode())
        return parse_ollama_tags_json(payload)
    except (
        OSError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
    ):
        return []

