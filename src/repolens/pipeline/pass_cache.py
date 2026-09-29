"""Save a finished deep pass so a later run does not repeat it."""

from __future__ import annotations

import hashlib
from pathlib import Path

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


def pass_label(pass_name: str) -> str:
    return _PASS_LABELS.get(pass_name, pass_name)


def closure_key(missed: list[str], model: str) -> str:
    """Key for the checklist follow-up. It sees missed ids, not source."""
    digest = hashlib.sha256()
    digest.update(PROMPT_TEMPLATE_VERSION.encode())
    digest.update(b"\0")
    digest.update(model.encode())
    digest.update(b"\0coverage")
    for cid in sorted(missed):
        digest.update(b"\0")
        digest.update(cid.encode())
    return digest.hexdigest()


def pass_key(files: list[FileEntry], model: str, pass_name: str) -> str:
    digest = hashlib.sha256()
    digest.update(PROMPT_TEMPLATE_VERSION.encode())
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
