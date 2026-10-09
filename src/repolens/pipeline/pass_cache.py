"""Save a finished deep pass so a later run does not repeat it."""

from __future__ import annotations

import hashlib
from pathlib import Path

from repolens import __version__
from repolens.adaptive import file_sha256
from repolens.inventory import FileEntry
from repolens.schema import FindingReport

PROMPT_TEMPLATE_VERSION = "2026-09-29-checklist"

_PASS_LABELS = {
    "p1": "P1 Security",
    "p2": "P2 Reliability",
    "p3": "P3 Architecture",
    "coverage": "Coverage closure",
}


_PASS_ALIASES = {
    "p1": "p1",
    "security": "p1",
    "p2": "p2",
    "reliability": "p2",
    "p3": "p3",
    "architecture": "p3",
    "arch": "p3",
}


def normalize_retry_pass(raw: str) -> str:
    """Map ``P3`` / ``architecture`` / ``arch`` (any case) to a band key."""
    key = raw.lower().strip()
    if key not in _PASS_ALIASES:
        raise ValueError(
            f"Unknown pass {raw!r}; use p1|p2|p3 or security|reliability|architecture"
        )
    return _PASS_ALIASES[key]


def normalize_retry_passes(raw: list[str] | tuple[str, ...] | None) -> frozenset[str]:
    return frozenset(normalize_retry_pass(item) for item in (raw or ()))


def pass_label(pass_name: str) -> str:
    return _PASS_LABELS.get(pass_name, pass_name)


def _tool_version(version: str | None) -> str:
    return __version__ if version is None else version


def closure_key(missed: list[str], model: str, *, version: str | None = None) -> str:
    """Key for the checklist follow-up. It sees missed ids, not source."""
    digest = hashlib.sha256()
    digest.update(PROMPT_TEMPLATE_VERSION.encode())
    digest.update(b"\0")
    digest.update(_tool_version(version).encode())
    digest.update(b"\0")
    digest.update(model.encode())
    digest.update(b"\0coverage")
    for cid in sorted(missed):
        digest.update(b"\0")
        digest.update(cid.encode())
    return digest.hexdigest()


def pass_key(
    files: list[FileEntry],
    model: str,
    pass_name: str,
    *,
    version: str | None = None,
    prior_summary: str | None = None,
    pack_mode: str = "full",
    file_pack_modes: dict[str, str] | None = None,
) -> str:
    digest = hashlib.sha256()
    digest.update(PROMPT_TEMPLATE_VERSION.encode())
    digest.update(b"\0")
    digest.update(_tool_version(version).encode())
    digest.update(b"\0")
    digest.update(model.encode())
    digest.update(b"\0")
    digest.update(pass_name.encode())
    for entry in sorted(files, key=lambda item: item.relative):
        digest.update(b"\0")
        digest.update(entry.relative.encode())
        try:
            digest.update(file_sha256(entry.path).encode())
        except OSError:
            digest.update(b"missing")
    digest.update(b"\0pack\0")
    digest.update((pack_mode or "full").encode())
    modes = file_pack_modes or {}
    for rel in sorted(modes):
        digest.update(b"\0")
        digest.update(f"{rel}:{modes[rel]}".encode())
    if prior_summary:
        digest.update(b"\0prior\0")
        digest.update(hashlib.sha256(prior_summary.encode()).digest())
    return digest.hexdigest()


def _cache_file(root: Path, key: str) -> Path:
    return root / ".repolens" / "passes" / f"{key}.json"


def save_pass(root: Path, key: str, report: FindingReport) -> None:
    path = _cache_file(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(), encoding="utf-8")


def load_pass(root: Path, key: str) -> FindingReport | None:
    path = _cache_file(root, key)
    if not path.is_file():
        return None
    try:
        return FindingReport.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
