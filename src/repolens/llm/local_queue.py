"""FIFO tickets for one local inference endpoint."""

from __future__ import annotations

import fcntl
import json
import os
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ticket_seq(path: Path) -> int:
    return int(path.stem.split("_")[0])


def poll_delay(
    base: float = 2.0, jitter: Callable[[], float] | None = None
) -> float:
    delta = (jitter or (lambda: random.uniform(-0.2, 0.2)))()
    return max(0.05, float(base) + float(delta))


def take_ticket(queue_dir: Path, payload: dict[str, Any]) -> Path:
    queue_dir.mkdir(parents=True, exist_ok=True)
    seq_path = queue_dir / "seq"
    fd = os.open(seq_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = os.read(fd, 64).decode("utf-8").strip()
        seq = int(raw) + 1 if raw else 1
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, str(seq).encode("utf-8"))
        os.fsync(fd)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    body = dict(payload)
    body.setdefault("pid", os.getpid())
    path = queue_dir / f"{seq}_{int(body['pid'])}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def live_tickets(queue_dir: Path) -> list[Path]:
    if not queue_dir.is_dir():
        return []
    kept: list[Path] = []
    for path in queue_dir.glob("*.json"):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            pid = int(meta.get("pid") or 0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            continue
        if not _pid_alive(pid):
            path.unlink(missing_ok=True)
            continue
        kept.append(path)
    return sorted(kept, key=ticket_seq)


def head_ticket(queue_dir: Path) -> Path | None:
    tickets = live_tickets(queue_dir)
    return tickets[0] if tickets else None
