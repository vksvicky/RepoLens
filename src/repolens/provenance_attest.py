"""Attestation helpers for ProvenanceBlock (dirty tree, digests, journal tip)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from repolens.pipeline.pass_cache import PROMPT_TEMPLATE_VERSION


def git_dirty_tree(root: Path) -> bool | None:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return bool(completed.stdout.strip())


def scanner_binary_digests(tools: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for tool in tools:
        path = shutil.which(tool)
        if not path:
            continue
        try:
            data = Path(path).read_bytes()
        except OSError:
            continue
        out[tool] = hashlib.sha256(data).hexdigest()[:16]
    return out


def prompt_template_hash() -> str:
    return hashlib.sha256(PROMPT_TEMPLATE_VERSION.encode()).hexdigest()[:16]


def journal_tip_hash(root: Path) -> str | None:
    path = root / ".repolens" / "journal.jsonl"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    return hashlib.sha256(lines[-1].encode()).hexdigest()[:16]
