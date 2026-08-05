"""Review progress reporter — phases, verbose detail, heartbeat."""

from __future__ import annotations

import io
import time
from unittest.mock import MagicMock

from rich.console import Console

from repolens.progress import LlmGenerateProgress, ReviewProgress


def test_phase_prints_unless_quiet() -> None:
    buf = io.StringIO()
    prog = ReviewProgress(console=Console(file=buf, force_terminal=False))
    prog.phase("Inventory: 3 reviewable file(s)")
    assert "Inventory: 3" in buf.getvalue()

    quiet_buf = io.StringIO()
    quiet = ReviewProgress(quiet=True, console=Console(file=quiet_buf, force_terminal=False))
    quiet.phase("should not appear")
    assert quiet_buf.getvalue() == ""


def test_detail_only_when_verbose() -> None:
    buf = io.StringIO()
    prog = ReviewProgress(verbose=False, console=Console(file=buf, force_terminal=False))
    prog.detail("hidden")
    assert buf.getvalue() == ""

    vbuf = io.StringIO()
    vprog = ReviewProgress(verbose=True, console=Console(file=vbuf, force_terminal=False))
    vprog.detail("sample: a.py")
    assert "sample: a.py" in vbuf.getvalue()


def test_waiting_heartbeat(monkeypatch) -> None:
    buf = io.StringIO()
    prog = ReviewProgress(
        heartbeat_seconds=0.05,
        console=Console(file=buf, force_terminal=False),
    )
    with prog.waiting("LLM: qwen via ollama"):
        time.sleep(0.12)
    text = buf.getvalue()
    assert "LLM: qwen via ollama" in text
    assert "still waiting" in text


def test_waiting_heartbeat_includes_hint_and_status_fn() -> None:
    buf = io.StringIO()
    prog = ReviewProgress(
        heartbeat_seconds=0.05,
        verbose=True,
        console=Console(file=buf, force_terminal=False),
    )
    with prog.waiting(
        "Deep pass 1/3 (p1)",
        hint="prompt ≈ 12,000 chars",
        status_fn=lambda: "Ollama: qwen running",
    ):
        time.sleep(0.12)
    text = buf.getvalue()
    assert "still waiting" in text
    # Static hint once (verbose detail); heartbeats prefer live status_fn.
    assert "prompt ≈ 12,000 chars" in text
    assert "Ollama: qwen" in text.replace("\n", "")


def test_llm_generate_progress_summary() -> None:
    gen = LlmGenerateProgress()
    assert "waiting for first token" in gen.summary()
    gen.note_delta('{"confidence":')
    gen.note_delta(" 80}")
    assert "chars" in gen.summary()
    assert "2 chunk" in gen.summary()


def test_waiting_heartbeat_disabled() -> None:
    buf = io.StringIO()
    prog = ReviewProgress(
        heartbeat_seconds=0,
        console=Console(file=buf, force_terminal=False),
    )
    with prog.waiting("LLM: test"):
        time.sleep(0.05)
    assert "still waiting" not in buf.getvalue()
    assert "LLM: test" in buf.getvalue()


def test_waiting_quiet_is_noop() -> None:
    buf = io.StringIO()
    prog = ReviewProgress(quiet=True, console=Console(file=buf, force_terminal=False))
    with prog.waiting("LLM: silent"):
        pass
    assert buf.getvalue() == ""


def test_waiting_uses_status_on_tty() -> None:
    console = MagicMock()
    console.is_terminal = True
    console.status.return_value.__enter__ = MagicMock(return_value=None)
    console.status.return_value.__exit__ = MagicMock(return_value=False)
    prog = ReviewProgress(heartbeat_seconds=0, console=console)
    with prog.waiting("LLM: spin"):
        pass
    console.status.assert_called_once()
    console.print.assert_called()
