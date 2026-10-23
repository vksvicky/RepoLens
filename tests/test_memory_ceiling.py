"""Memory ceiling and the 32B advisory decide before a model call."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from repolens.cli.commands_review_support import _map_run_mode_error
from repolens.cli.exit_codes import EXIT_BAD_INPUT
from repolens.config import ModelConfig, RepoLensConfig
from repolens.llm_structured import StructuredLlmResult
from repolens.memory_sample import (
    ceiling_decision,
    local_32b_notice,
    physical_ram_bytes,
)
from repolens.pipeline import MemoryCeilingError, ReviewRun, run_review
from repolens.progress import ReviewProgress
from repolens.schema import FindingReport, Summary


def test_32b_notice_on_a_small_ollama_host() -> None:
    notice = local_32b_notice("ollama", "qwen2.5-coder:32b", 16 * 1024**3)
    assert notice is not None
    assert "32B" in notice
    assert "14B" in notice
    assert "claude" not in notice.lower()


def test_32b_notice_skips_byok_and_enough_ram() -> None:
    assert local_32b_notice("openai", "qwen2.5-coder:32b", 16 * 1024**3) is None
    assert local_32b_notice("ollama", "qwen2.5-coder:14b", 16 * 1024**3) is None
    assert local_32b_notice("ollama", "qwen2.5-coder:32b", 24 * 1024**3) is None
    assert local_32b_notice("ollama", "qwen2.5-coder:32b", None) is None


def test_32b_token_does_not_match_a_larger_tag() -> None:
    assert local_32b_notice("ollama", "some-132b", 16 * 1024**3) is None
    notice = local_32b_notice("ollama", "qwen2.5-coder:32b-instruct", 16 * 1024**3)
    assert notice is not None


def test_physical_ram_returns_none_when_sysconf_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(_name: str) -> int:
        raise OSError("no")

    monkeypatch.setattr("repolens.memory_sample.os.sysconf", _fail)
    assert physical_ram_bytes() is None


def test_ceiling_under_the_limit_is_quiet() -> None:
    assert ceiling_decision(100, 50 * 1024 * 1024, True) == (None, False)
    assert ceiling_decision(None, 10**12, True) == (None, False)


def test_ceiling_over_the_limit_hints_and_aborts_only_when_asked() -> None:
    hint, stop = ceiling_decision(1, 2 * 1024 * 1024, False)
    assert hint is not None
    assert "max_files" in hint
    assert "chars_per_pass" in hint
    assert "workers" not in hint
    assert stop is False
    _hint, stop = ceiling_decision(1, 2 * 1024 * 1024, True)
    assert stop is True


def test_memory_ceiling_error_exits_2() -> None:
    with pytest.raises(typer.Exit) as caught:
        _map_run_mode_error(MemoryCeilingError("over the ceiling"))
    assert caught.value.exit_code == EXIT_BAD_INPUT


class _Phases(ReviewProgress):
    def __init__(self) -> None:
        super().__init__(quiet=True)
        self.messages: list[str] = []

    def phase(self, message: str) -> None:
        self.messages.append(message)


def _repo(tmp_path: Path) -> RepoLensConfig:
    return RepoLensConfig(
        model=ModelConfig(
            provider="ollama",
            model="qwen2.5-coder:7b",
            lock=False,
            memory_ceiling_mb=1,
        )
    )


def test_abort_stops_before_the_model(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    cfg = _repo(tmp_path)
    cfg.model.memory_abort = True
    with (
        patch("repolens.memory_sample.bytes_for_ceiling", return_value=50 * 1024 * 1024),
        patch("repolens.llm_structured.analyze_structured") as analyze,
        pytest.raises(MemoryCeilingError),
    ):
        run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            scanners="off",
            deep=False,
            model_lock=False,
            out_dir=tmp_path / "reports",
        ))
    analyze.assert_not_called()


def test_hint_continues_into_the_model(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    cfg = _repo(tmp_path)
    report = FindingReport(confidence=1, summary=Summary(), issues=[])
    result_llm = StructuredLlmResult(report=report, raw_text="{}", layer="ok", error=None)
    phases = _Phases()
    with (
        patch("repolens.memory_sample.bytes_for_ceiling", return_value=50 * 1024 * 1024),
        patch("repolens.llm_structured.analyze_structured", return_value=result_llm) as analyze,
    ):
        run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            scanners="off",
            deep=False,
            model_lock=False,
            progress=phases,
            out_dir=tmp_path / "reports",
        ))
    analyze.assert_called()
    assert any("max_files" in message for message in phases.messages)


def test_32b_notice_is_printed_and_the_review_continues(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="qwen2.5-coder:32b", lock=False)
    )
    phases = _Phases()
    with patch("repolens.memory_sample.physical_ram_bytes", return_value=16 * 1024**3):
        run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            scanners="off",
            scanners_only=True,
            model_lock=False,
            progress=phases,
            out_dir=tmp_path / "reports",
        ))
    notice = " ".join(phases.messages)
    assert "32b" in notice
    assert "claude" not in notice.lower()


def test_dry_run_skips_the_32b_notice(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="qwen2.5-coder:32b", lock=False)
    )
    phases = _Phases()
    with patch("repolens.memory_sample.physical_ram_bytes", return_value=16 * 1024**3):
        result = run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            dry_run=True,
            progress=phases,
            out_dir=tmp_path / "reports",
        ))
    assert result.dry_run is True
    assert all("32b" not in message for message in phases.messages)


def test_scanners_only_does_not_abort_on_the_ceiling(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    cfg = _repo(tmp_path)
    cfg.model.memory_abort = True
    with (
        patch("repolens.memory_sample.bytes_for_ceiling", return_value=50 * 1024 * 1024),
        patch("repolens.llm_structured.analyze_structured") as analyze,
    ):
        result = run_review(ReviewRun(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            scanners="off",
            scanners_only=True,
            model_lock=False,
            out_dir=tmp_path / "reports",
        ))
    assert result.report is not None
    analyze.assert_not_called()
