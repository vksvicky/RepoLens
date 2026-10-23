"""Python-process RSS. Not the Ollama model and not OS memory pressure."""

from __future__ import annotations

import logging
import os
import re
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
            logging.getLogger(__name__).debug("handled expected error", exc_info=True)
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


_GIB = 1024**3
_32B_TOKEN = re.compile(r"(?i)(?<![A-Za-z0-9])32b(?![A-Za-z0-9])")
_SMALL_HOST = 24 * _GIB


def physical_ram_bytes() -> int | None:
    """Physical RAM from ``sysconf``. ``None`` when the host does not report it."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError):
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None
    if pages <= 0 or page_size <= 0:
        return None
    return int(pages) * int(page_size)


def local_32b_notice(provider: str | None, model: str | None, ram_bytes: int | None) -> str | None:
    """Advisory only. A small host running a local 32B tag can swap. Review continues."""
    if provider != "ollama" or model is None or ram_bytes is None:
        return None
    if _32B_TOKEN.search(model) is None or ram_bytes >= _SMALL_HOST:
        return None
    return (
        "Notice: this machine has under 24 GiB of RAM and the local model id contains 32b. "
        "A 32B model can make the OS swap. A 14B tag needs less memory. "
        "A cloud model stays off this machine."
    )


def bytes_for_ceiling() -> int:
    """Current RSS on Linux. Peak RSS where ``/proc`` is absent."""
    current = read_vm_rss_bytes()
    if current is not None:
        return current
    return read_peak_rss_bytes()


def ceiling_decision(
    ceiling_mb: int | None,
    rss_bytes: int,
    abort: bool,
) -> tuple[str | None, bool]:
    """Return ``(hint, stop)``. ``stop`` is true only when abort was requested."""
    if ceiling_mb is None or rss_bytes <= ceiling_mb * _MIB:
        return None, False
    mebibytes = rss_bytes / _MIB
    hint = (
        f"Python process RSS is {mebibytes:.1f} MB, over the {ceiling_mb} MB ceiling, "
        "before the model call. Lower [general] max_files or [deep] chars_per_pass. "
        "This sample is the Python process, not the Ollama model."
    )
    return hint, abort
