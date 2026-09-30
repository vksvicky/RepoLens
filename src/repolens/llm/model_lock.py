"""One local Ollama endpoint serves one RepoLens review at a time."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from repolens.config import ModelConfig
from repolens.llm.local_queue import _pid_alive, head_ticket, poll_delay, take_ticket


@dataclass
class LockContext:
    repo: str
    path: str
    pass_name: str
    status: Callable[[str], None] | None = None


_lock_context: ContextVar[LockContext | None] = ContextVar(
    "repolens_ollama_lock",
    default=None,
)
_held_endpoints: ContextVar[frozenset[str]] = ContextVar(
    "repolens_local_endpoint_held",
    default=frozenset(),
)
_queue_wait: ContextVar[float] = ContextVar("repolens_queue_wait", default=0.0)


def queue_wait_seconds() -> float:
    """Seconds this process has waited for a local model since the last reset."""
    return _queue_wait.get()


def reset_queue_wait() -> None:
    """Start a review's queue-wait total at zero."""
    _queue_wait.set(0.0)


def note_queue_wait(seconds: float) -> None:
    """Add time spent before the local lock was acquired."""
    if seconds > 0:
        _queue_wait.set(_queue_wait.get() + seconds)


@contextmanager
def hold_local_endpoint(key: str) -> Iterator[None]:
    token = _held_endpoints.set(_held_endpoints.get() | {key})
    try:
        yield
    finally:
        _held_endpoints.reset(token)


def bind_lock_context(
    *,
    repo: str,
    path: str,
    pass_name: str,
    status: Callable[[str], None] | None = None,
) -> Token[LockContext | None]:
    return _lock_context.set(
        LockContext(repo=repo, path=path, pass_name=pass_name, status=status)
    )


def reset_lock_context(token: Token[LockContext | None]) -> None:
    _lock_context.reset(token)


def current_lock_context() -> LockContext:
    ctx = _lock_context.get()
    if ctx is not None:
        return ctx
    cwd = Path.cwd()
    return LockContext(repo=cwd.name, path=str(cwd), pass_name="llm")


def default_lock_dir() -> Path:
    override = os.environ.get("REPOLENS_LOCK_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".repolens" / "locks"


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


def is_local_host(hostname: str) -> bool:
    name = hostname.lower().rstrip(".")
    return name in _LOCAL_HOSTS or name.endswith(".local")


def endpoint_port(scheme: str, port: int | None, provider: str | None) -> int:
    if port is not None:
        return port
    if provider == "ollama":
        return 11434
    if scheme == "https":
        return 443
    return 80


def _host_slug(host: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in host)


def lock_path_for(
    base_url: str, lock_dir: Path, *, provider: str | None = None
) -> Path:
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or "127.0.0.1"
    port = endpoint_port(parsed.scheme, parsed.port, provider)
    return lock_dir / f"local_{_host_slug(host)}_{port}.lock"


def should_use_model_lock(
    model_cfg: ModelConfig, cli_flag: bool | None = None
) -> bool:
    from repolens.providers import default_base_url_for

    flag = cli_flag if cli_flag is not None else model_cfg.lock_cli
    if flag is not None:
        return flag
    if not model_cfg.lock:
        return False
    if model_cfg.provider == "ollama":
        return True
    if model_cfg.provider != "openai_compatible":
        return False
    base = (model_cfg.base_url or default_base_url_for("openai_compatible") or "")
    parsed = urlparse(base if "://" in base else f"http://{base}")
    return is_local_host(parsed.hostname or "")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def format_wait_message(meta: dict[str, Any], *, clock: str | None = None) -> str:
    shown = clock or time.strftime("%H:%M", time.localtime(float(meta["started_at"])))
    repo = meta.get("repo") or "another review"
    pass_name = meta.get("pass") or "a pass"
    return (
        "[Slow Brain] Waiting for local model "
        f"(held by {repo} for {pass_name} since {shown})..."
    )


class OllamaModelLock:
    """Advisory lock held for one model call. The fd stays open until release."""

    def __init__(
        self,
        *,
        repo: str,
        path: str,
        pass_name: str,
        model: str,
        base_url: str,
        provider: str | None = None,
        lock_dir: Path | None = None,
        poll_seconds: float = 2.0,
        status: Callable[[str], None] | None = None,
        sleeper: Callable[[float], None] | None = None,
        jitter: Callable[[], float] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.repo = repo
        self.path = path
        self.pass_name = pass_name
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self.lock_dir = lock_dir or default_lock_dir()
        self.poll_seconds = poll_seconds
        self.status = status
        self.sleeper = sleeper or time.sleep
        self.jitter = jitter
        self.clock = clock or time.monotonic
        self.waited_seconds = 0.0
        self.lock_file = lock_path_for(base_url, self.lock_dir, provider=provider)
        self.queue_dir = self.lock_dir / (
            "queue_" + self.lock_file.stem.removeprefix("local_")
        )
        self._fd: int | None = None
        self._nested = False
        self._ticket: Path | None = None

    def __enter__(self) -> OllamaModelLock:
        if self.lock_file.name in _held_endpoints.get():
            self._nested = True
            return self
        started = self.clock()
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._ticket = take_ticket(
            self.queue_dir,
            {
                "repo": self.repo,
                "path": self.path,
                "pass": self.pass_name,
                "model": self.model,
                "pid": os.getpid(),
                "started_at": time.time(),
            },
        )
        try:
            self._wait_for_turn()
            self._acquire_flock()
            self.waited_seconds = max(0.0, self.clock() - started)
            note_queue_wait(self.waited_seconds)
        except Exception:
            self._ticket.unlink(missing_ok=True)
            self._ticket = None
            raise
        return self

    def _wait_for_turn(self) -> None:
        while True:
            head = head_ticket(self.queue_dir)
            if head == self._ticket:
                return
            if head is not None and self.status is not None:
                meta = _read_json(head)
                if meta:
                    self.status(format_wait_message(meta))
            self.sleeper(poll_delay(self.poll_seconds, self.jitter))

    def _acquire_flock(self) -> None:
        self._fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT, 0o644)
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    os.close(self._fd)
                    self._fd = None
                    raise
                if self._holder_is_dead():
                    time.sleep(0.05)
                    continue
                self._announce_holder()
                self.sleeper(0.05)
        self._write_metadata()

    def __exit__(self, *args: object) -> None:
        if self._nested:
            return
        try:
            if self._fd is None:
                return
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
        finally:
            if self._ticket is not None:
                self._ticket.unlink(missing_ok=True)
                self._ticket = None

    def _holder_is_dead(self) -> bool:
        meta = self._read_metadata()
        if not meta:
            return False
        return not _pid_alive(int(meta.get("pid") or 0))

    def _announce_holder(self) -> None:
        meta = self._read_metadata()
        if self.status is None or not meta or self._holder_is_dead():
            return
        self.status(format_wait_message(meta))

    def _read_metadata(self) -> dict[str, Any] | None:
        try:
            text = self.lock_file.read_text(encoding="utf-8")
        except OSError:
            return None
        if not text.strip():
            return None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None
        return raw if isinstance(raw, dict) else None

    def _write_metadata(self) -> None:
        if self._fd is None:
            return
        payload = {
            "repo": self.repo,
            "path": self.path,
            "pass": self.pass_name,
            "model": self.model,
            "pid": os.getpid(),
            "started_at": time.time(),
        }
        raw = json.dumps(payload).encode("utf-8")
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.ftruncate(self._fd, 0)
        os.write(self._fd, raw)
        os.fsync(self._fd)
