"""Informed consent for local learning."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

CONSENT_NOTICE = """\
RepoLens can build a local index of this repository to improve future reviews.
Data stays on this machine under .repolens/ (or your configured cache dir).
Nothing is uploaded to RepoLens.
If you use a cloud LLM provider, review prompts may still include code excerpts
sent to that provider.
Disable anytime: set local_learning.enabled = false or delete .repolens/.
"""


def _repolens_dir(root: Path) -> Path:
    return root / ".repolens"


def consent_path(root: Path) -> Path:
    return _repolens_dir(root) / "consent.toml"


def has_consent(root: Path) -> bool:
    path = consent_path(root)
    if not path.is_file():
        return False
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        return bool(data.get("accepted"))
    except (OSError, tomllib.TOMLDecodeError):
        return False


def accept_local_learning(root: Path) -> Path:
    """Record consent on disk. Returns path to consent file."""
    directory = _repolens_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = consent_path(root)
    path.write_text(
        "\n".join(
            [
                "# Written by RepoLens after informed consent.",
                "accepted = true",
                f'accepted_at = "{stamp}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")
    return path


def ensure_consent(root: Path, *, accept: bool) -> None:
    """Raise PermissionError if learning is used without consent."""
    if has_consent(root):
        return
    if accept:
        accept_local_learning(root)
        return
    raise PermissionError(
        "Local learning requires consent. Re-run with --accept-local-learning "
        "after reading the notice:\n\n" + CONSENT_NOTICE
    )
