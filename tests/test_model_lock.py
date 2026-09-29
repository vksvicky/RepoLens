"""Local Ollama reviews take a user-level lock before they open HTTP."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from repolens.config import ModelConfig
from repolens.llm.model_lock import (
    OllamaModelLock,
    _pid_alive,
    bind_lock_context,
    current_lock_context,
    default_lock_dir,
    format_wait_message,
    lock_path_for,
    reset_lock_context,
    should_use_model_lock,
)


def test_only_local_ollama_takes_the_lock() -> None:
    assert should_use_model_lock(ModelConfig(provider="ollama")) is True
    assert should_use_model_lock(ModelConfig(provider="ollama", lock=False)) is False
    assert should_use_model_lock(ModelConfig(provider="openai")) is False
    assert should_use_model_lock(ModelConfig(provider="gemini")) is False


def test_hostname_match_rejects_a_lookalike() -> None:
    from repolens.llm.model_lock import is_local_host

    assert is_local_host("localhost") is True
    assert is_local_host("studio.local") is True
    assert is_local_host("notlocalhost.example") is False
    assert is_local_host("evil.local.example") is False


def test_missing_port_follows_the_scheme_and_the_provider() -> None:
    assert (
        lock_path_for("http://localhost/v1", Path("/tmp/locks"), provider="openai_compatible").name
        == "local_localhost_80.lock"
    )
    assert (
        lock_path_for("http://localhost/v1", Path("/tmp/locks"), provider="ollama").name
        == "local_localhost_11434.lock"
    )
    assert (
        lock_path_for("https://localhost/v1", Path("/tmp/locks"), provider="openai_compatible").name
        == "local_localhost_443.lock"
    )
    assert lock_path_for("http://127.0.0.1:8000/v1", Path("/tmp/locks")).name == (
        "local_127_0_0_1_8000.lock"
    )


def test_should_use_model_lock_follows_cli_then_config_then_host() -> None:
    ollama = ModelConfig(provider="ollama")
    cloud = ModelConfig(provider="gemini")
    local_compat = ModelConfig(
        provider="openai_compatible", base_url="http://127.0.0.1:8000/v1"
    )
    remote_compat = ModelConfig(
        provider="openai_compatible", base_url="https://api.together.xyz/v1"
    )
    assert should_use_model_lock(ollama) is True
    assert should_use_model_lock(ollama, cli_flag=False) is False
    assert should_use_model_lock(cloud) is False
    assert should_use_model_lock(cloud, cli_flag=True) is True
    assert should_use_model_lock(ModelConfig(provider="ollama", lock=False)) is False
    assert should_use_model_lock(local_compat) is True
    assert should_use_model_lock(remote_compat) is False
    assert should_use_model_lock(ModelConfig(provider="openai_compatible")) is True


def test_lock_file_is_per_endpoint() -> None:
    path = lock_path_for("http://127.0.0.1:11434/v1", Path("/tmp/locks"))
    assert path.name == "local_127_0_0_1_11434.lock"
    assert path.parent == Path("/tmp/locks")


def test_wait_message_names_the_holding_review() -> None:
    text = format_wait_message(
        {
            "repo": "LogViewer",
            "pass": "P2",
            "started_at": 0.0,
        },
        clock="12:30",
    )
    assert text == (
        "[Slow Brain] Waiting for local model "
        "(held by LogViewer for P2 since 12:30)..."
    )


def test_acquire_writes_metadata_and_a_second_attempt_sees_it(tmp_path: Path) -> None:
    notes: list[str] = []
    first = OllamaModelLock(
        repo="LogViewer",
        path="/Users/vivek/Development/LogViewer",
        pass_name="P2",
        model="qwen2.5-coder:32b",
        base_url="http://127.0.0.1:11434/v1",
        lock_dir=tmp_path,
        status=notes.append,
    )
    with first:
        raw = json.loads(first.lock_file.read_text(encoding="utf-8"))
        assert raw["repo"] == "LogViewer"
        assert raw["pass"] == "P2"
        assert raw["model"] == "qwen2.5-coder:32b"
        assert raw["pid"] > 0
    assert first._fd is None


def test_bound_context_names_the_running_review() -> None:
    token = bind_lock_context(repo="LogViewer", path="/tmp/LogViewer", pass_name="P2")
    try:
        ctx = current_lock_context()
        assert ctx.repo == "LogViewer"
        assert ctx.pass_name == "P2"
    finally:
        reset_lock_context(token)
    assert current_lock_context().repo == Path.cwd().name


def test_default_lock_dir_honours_env_then_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "custom"))
    assert default_lock_dir() == tmp_path / "custom"
    monkeypatch.delenv("REPOLENS_LOCK_DIR")
    monkeypatch.setattr("repolens.llm.model_lock.Path.home", lambda: tmp_path)
    assert default_lock_dir() == tmp_path / ".repolens" / "locks"


def test_wait_message_fills_in_a_missing_holder() -> None:
    text = format_wait_message({"started_at": 0.0}, clock="01:00")
    assert "another review" in text
    assert "a pass" in text


def test_pid_alive_rejects_dead_and_non_positive_pids() -> None:
    assert _pid_alive(0) is False
    assert _pid_alive(os.getpid()) is True
    assert _pid_alive(2**30) is False


def test_metadata_reader_ignores_empty_and_broken_files(tmp_path: Path) -> None:
    lock = _lock(tmp_path)
    assert lock._read_metadata() is None
    lock.lock_file.write_text("   ", encoding="utf-8")
    assert lock._read_metadata() is None
    lock.lock_file.write_text("not-json", encoding="utf-8")
    assert lock._read_metadata() is None
    lock.lock_file.write_text("[]", encoding="utf-8")
    assert lock._read_metadata() is None
    lock._write_metadata()


def test_unexpected_flock_error_closes_the_descriptor(tmp_path: Path, monkeypatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EIO, "io")

    monkeypatch.setattr(fcntl, "flock", boom)
    lock = _lock(tmp_path)
    with pytest.raises(OSError):
        with lock:
            pass
    assert lock._fd is None


def test_second_process_waits_and_names_the_holder(tmp_path: Path) -> None:
    proc = _hold_lock(tmp_path, seconds=0.8)
    threading.Thread(target=proc.wait, daemon=True).start()
    notes: list[str] = []
    try:
        _wait_for_holder(tmp_path)
        with _lock(tmp_path, status=notes.append, poll_seconds=0.05):
            assert any("LogViewer" in note and "P2" in note for note in notes)
    finally:
        proc.wait(timeout=5)
        assert proc.returncode == 0


def test_dead_holder_metadata_does_not_announce(tmp_path: Path) -> None:
    proc = _hold_lock(tmp_path, seconds=0.8)
    threading.Thread(target=proc.wait, daemon=True).start()
    notes: list[str] = []
    try:
        _wait_for_holder(tmp_path)
        for ticket in (tmp_path / "queue_127_0_0_1_11434").glob("*.json"):
            meta = json.loads(ticket.read_text(encoding="utf-8"))
            meta["pid"] = 2**30
            ticket.write_text(json.dumps(meta), encoding="utf-8")
        (tmp_path / "local_127_0_0_1_11434.lock").write_text(
            json.dumps({"repo": "Ghost", "pass": "P1", "pid": 2**30, "started_at": 0}),
            encoding="utf-8",
        )
        with _lock(tmp_path, status=notes.append, poll_seconds=0.05):
            assert notes == []
    finally:
        proc.wait(timeout=5)
        assert proc.returncode == 0


def test_second_enter_while_held_does_not_take_another_ticket(tmp_path: Path) -> None:
    from repolens.llm.model_lock import hold_local_endpoint

    lock = _lock(tmp_path, poll_seconds=0.05)
    sleeps: list[float] = []
    lock.sleeper = sleeps.append
    with lock:
        with hold_local_endpoint(lock.lock_file.name):
            again = _lock(tmp_path, poll_seconds=0.05)
            again.sleeper = sleeps.append
            with again:
                pass
    assert (lock.queue_dir / "seq").read_text(encoding="utf-8").strip() == "1"
    assert sleeps == []


def test_a_new_ticket_waits_behind_an_older_one(tmp_path: Path) -> None:
    code = textwrap.dedent(
        f"""
        import time
        from pathlib import Path
        from repolens.llm.local_queue import take_ticket
        root = Path({str(tmp_path)!r})
        take_ticket(root / "queue_127_0_0_1_11434", {{
            "repo": "LogViewer",
            "pass": "P2",
            "pid": __import__("os").getpid(),
            "started_at": 0,
        }})
        time.sleep(1.5)
        """
    )
    proc = subprocess.Popen([sys.executable, "-c", code])
    # Reap the child while we wait. A zombie still answers kill(pid, 0),
    # so the ticket would look alive until wait().
    threading.Thread(target=proc.wait, daemon=True).start()
    notes: list[str] = []
    try:
        for _ in range(50):
            queue = tmp_path / "queue_127_0_0_1_11434"
            if queue.is_dir() and any(queue.glob("*.json")):
                break
            time.sleep(0.02)
        lock = _lock(tmp_path, status=notes.append, poll_seconds=0.05)
        lock.jitter = lambda: 0.0
        with lock:
            assert any("LogViewer" in note for note in notes)
    finally:
        proc.wait(timeout=5)


def test_cloud_analyze_creates_no_lock_files(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import MagicMock

    from repolens.llm import analyze_raw

    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = MagicMock()
    cfg = ModelConfig(provider="openai", model="gpt-4.1-mini", api_key_env="OPENAI_API_KEY")
    try:
        analyze_raw("prompt", cfg, client=client)
    except Exception:
        pass
    assert not (tmp_path / "locks").exists()


def _lock(
    tmp_path: Path,
    *,
    status: Callable[[str], None] | None = None,
    poll_seconds: float = 2.0,
) -> OllamaModelLock:
    return OllamaModelLock(
        repo="RepoLens",
        path=str(tmp_path),
        pass_name="P1",
        model="qwen2.5-coder:32b",
        base_url="http://127.0.0.1:11434/v1",
        lock_dir=tmp_path,
        poll_seconds=poll_seconds,
        status=status,
    )


def _wait_for_holder(tmp_path: Path) -> None:
    lock_file = tmp_path / "local_127_0_0_1_11434.lock"
    for _ in range(50):
        if lock_file.is_file() and b"LogViewer" in lock_file.read_bytes():
            return
        time.sleep(0.02)
    raise AssertionError("holder did not take the lock")


def _hold_lock(tmp_path: Path, *, seconds: float) -> subprocess.Popen[str]:
    code = textwrap.dedent(
        f"""
        import time
        from pathlib import Path
        from repolens.llm.model_lock import OllamaModelLock
        with OllamaModelLock(
            repo="LogViewer",
            path="/tmp/LogViewer",
            pass_name="P2",
            model="qwen",
            base_url="http://127.0.0.1:11434/v1",
            lock_dir=Path({str(tmp_path)!r}),
        ):
            time.sleep({seconds})
        """
    )
    return subprocess.Popen([sys.executable, "-c", code])
