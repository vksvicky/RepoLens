"""Python-process RSS. Not the Ollama model and not OS memory pressure."""

from __future__ import annotations

import logging
import resource
import sys
from pathlib import Path

PYTHON_RSS_NOTE = (
    "Python process peak RSS since process start. "
    "This is not the Ollama model and not OS memory pressure."
)
_KIB = 1024
_MIB = 1024 * 1024


def peak_rss_bytes(ru_maxrss: int, platform: str) -> int:
    """``ru_maxrss`` is bytes on macOS and kilobytes on Linux."""
    scale = 1 if platform == "darwin" else _KIB
    return int(ru_maxrss) * scale


def read_peak_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return peak_rss_bytes(int(usage.ru_maxrss), sys.platform)


def vm_rss_bytes_from_status(text: str) -> int | None:
    """Parse ``VmRSS`` from ``/proc/self/status``. The value is kilobytes."""
    for line in text.splitlines():
        if not line.startswith("VmRSS:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            return None
        try:
            return int(parts[1]) * _KIB
        except ValueError:
            return None
    return None


def read_vm_rss_bytes() -> int | None:
    path = Path("/proc/self/status")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None
    return vm_rss_bytes_from_status(text)


def format_peak_rss(num_bytes: int) -> str:
    mebibytes = num_bytes / _MIB
    return f"Python process peak RSS: {mebibytes:.1f} MB"
