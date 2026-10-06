"""First-4KB regex sniff for role_packs ordering (Metis slice C)."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.inventory import FileEntry

SNIFF_BYTES = 4096

_DEMOTED_SUFFIXES = (
    ".css",
    ".scss",
    ".sass",
    ".svg",
    ".min.js",
    ".min.css",
    ".map",
    ".lock",
)
_DEMOTED_PATH_PARTS = (
    "/fixtures/",
    "/__mocks__/",
    "/testdata/",
    "/vendor/",
    "/node_modules/",
)

_P1_PATH_HINTS = (
    "auth",
    "secret",
    "password",
    "credential",
    "crypto",
    "jwt",
    "oauth",
    "session",
    "security",
    "tls",
    "ssl",
    "sql",
    "exec",
    "shell",
    "environ",
    "permission",
    "rbac",
    "firewall",
    ".env",
)
_P2_PATH_HINTS = (
    "error",
    "except",
    "retry",
    "timeout",
    "backoff",
    "lock",
    "thread",
    "async",
    "pool",
    "queue",
    "transaction",
    "cleanup",
    "recover",
    "health",
    "circuit",
    "resilien",
)

_P1_CONTENT = re.compile(
    r"(?i)("
    r"execute\s*\(|raw_sql|cursor\.|subprocess\.|os\.system|os\.popen|"
    r"eval\s*\(|exec\s*\(|pickle\.loads|yaml\.load\s*\(|"
    r"jwt\.|bcrypt|hashlib\.|Crypto|cryptography|"
    r"@app\.route|@router\.|FastAPI|APIRouter|Authorization|"
    r"password|api_key|secret_key"
    r")"
)
_P2_CONTENT = re.compile(
    r"(?i)("
    r"begin_transaction|commit\s*\(|rollback\s*\(|"
    r"retry|backoff|tenacity|asyncio\.Lock|threading\.|multiprocessing\.|"
    r"with\s+\w*lock|RLock|Semaphore|except\s+\w+"
    r")"
)


def is_demoted_asset(relative: str) -> bool:
    lowered = relative.lower().replace("\\", "/")
    if any(lowered.endswith(suf) for suf in _DEMOTED_SUFFIXES):
        return True
    padded = f"/{lowered}/"
    return any(part in padded for part in _DEMOTED_PATH_PARTS)


def read_sniff_text(path: Path) -> str:
    try:
        raw = path.open("rb").read(SNIFF_BYTES)
    except OSError:
        return ""
    try:
        return raw.decode("utf-8", errors="ignore")
    except UnicodeError:
        return ""


def content_score(band: str, text: str) -> int:
    if not text:
        return 0
    pattern = _P1_CONTENT if band == "p1" else _P2_CONTENT if band == "p2" else None
    if pattern is None:
        return 0
    return len(pattern.findall(text))


def path_score(band: str, relative: str) -> int:
    lowered = relative.lower().replace("\\", "/")
    hints = (
        _P1_PATH_HINTS
        if band == "p1"
        else _P2_PATH_HINTS
        if band == "p2"
        else ()
    )
    return sum(1 for hint in hints if hint in lowered)


def sniff_score(band: str, entry: FileEntry) -> int:
    return path_score(band, entry.relative) + content_score(
        band, read_sniff_text(entry.path)
    )
