"""Deep-mode pass resume and coverage closure."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
from repolens.pipeline import ReviewRun, run_review
from tests.pipeline_deep_support import (
    _pass_report,
    ollama_deep_config,
    recording_band_analyze,
)


def test_coverage_closure_records_ids_the_band_passes_skipped(tmp_path: Path) -> None:
    """A deep scan asks again for checklist ids the band passes left blank."""
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )
    prompts: dict[str, str] = {}

    def fake_analyze(
        prompt, model_cfg, *, pass_id, progress=None, raw_dir=None, on_delta=None, **_
    ):
        prompts[pass_id] = prompt
        if pass_id != "coverage":
            return _pass_report(
                title=f"{pass_id} finding",
                file="a.py",
                priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
                coverage_na=[],
            )
        missed = [
            line[2:].strip()
            for line in prompt.splitlines()
            if line.startswith("- ")
        ]
        return _pass_report(
            title="Coverage closure",
            file="a.py",
            priority="P3",
            coverage_na=missed,
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        result = run_review(ReviewRun(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
            full_audit=True,
        ))

    p3 = prompts["p3"]
    assert p3.index("## Source files") < p3.index("## Coverage checklist (required before JSON)")
    assert "arch.testing" in prompts["coverage"]
    assert result.report.coverage is not None
    assert "arch.testing" not in result.report.coverage.missed
    assert any(
        g.startswith("coverage:arch.testing: N/A") for g in result.report.durabilityGaps
    )


def _progress_buffer():
    import io

    from rich.console import Console

    from repolens.progress import ReviewProgress

    buf = io.StringIO()
    prog = ReviewProgress(console=Console(file=buf, force_terminal=False, highlight=False))
    return prog, buf


def test_second_deep_run_shows_saved_file_checks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )

    def fake_analyze(prompt, model_cfg, *, pass_id, **_):
        return _pass_report(
            title=f"{pass_id} finding",
            file="a.py",
            priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))
    prog, buf = _progress_buffer()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True, progress=prog,
        ))
    text = buf.getvalue()
    assert "1 of 3 file checks done (33%)" in text
    assert "saved — skipping it" in text
    assert "3 of 3 file checks done (100%)" in text


def _ollama_review_config() -> RepoLensConfig:
    return RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )


def _fake_band_analyze(prompt, model_cfg, *, pass_id, **_):
    return _pass_report(
        title=f"{pass_id} finding",
        file="a.py",
        priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
        coverage_na=[],
    )


def test_cached_deep_pass_does_not_read_excerpts(tmp_path: Path, monkeypatch) -> None:
    """A saved pass returns before excerpts and outlines are read again."""
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = _ollama_review_config()
    with patch("repolens.llm_structured.analyze_structured", side_effect=_fake_band_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))

    reads = {"excerpt": 0, "outline": 0}

    def count_excerpt(entry, max_chars=12_000):
        reads["excerpt"] += 1
        return "counted"

    def count_outline(*_args, **_kwargs):
        reads["outline"] += 1
        return ""

    with (
        patch("repolens.llm_structured.analyze_structured", side_effect=_fake_band_analyze),
        patch("repolens.pipeline.prompt.read_excerpt", side_effect=count_excerpt),
        patch("repolens.file_outline.format_file_outline", side_effect=count_outline),
    ):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))
    assert reads == {"excerpt": 0, "outline": 0}


def test_changed_file_reads_excerpts_again(tmp_path: Path, monkeypatch) -> None:
    """A pass whose files changed still reads the excerpt."""
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = _ollama_review_config()
    with patch("repolens.llm_structured.analyze_structured", side_effect=_fake_band_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))
    (tmp_path / "a.py").write_text("print(2)\n", encoding="utf-8")
    reads = {"excerpt": 0}

    def count_excerpt(entry, max_chars=12_000):
        reads["excerpt"] += 1
        return "counted"

    with (
        patch("repolens.llm_structured.analyze_structured", side_effect=_fake_band_analyze),
        patch("repolens.pipeline.prompt.read_excerpt", side_effect=count_excerpt),
    ):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))
    assert reads["excerpt"] > 0


def test_changed_files_say_the_saved_pass_runs_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )

    def fake_analyze(prompt, model_cfg, *, pass_id, **_):
        return _pass_report(
            title=f"{pass_id} finding",
            file="a.py",
            priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True,
        ))
    (tmp_path / "a.py").write_text("print(2)\n", encoding="utf-8")
    prog, buf = _progress_buffer()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path, mode="review", config=cfg, out_dir=tmp_path / "out",
            scanners="off", deep=True, progress=prog,
        ))
    text = buf.getvalue()
    assert "does not match these files" in text
    assert "runs again" in text
    assert "0 of 3 file checks done (0%)" in text


def test_second_deep_run_skips_finished_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = ollama_deep_config()
    calls: list[str] = []
    fake_analyze = recording_band_analyze(calls)

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        ))
    first = list(calls)
    calls.clear()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        ))
    assert "p1" in first and "p2" in first and "p3" in first
    assert "p1" not in calls
    assert "p2" not in calls
    assert "p3" not in calls


def test_no_resume_reruns_cached_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = ollama_deep_config()
    calls: list[str] = []
    fake_analyze = recording_band_analyze(calls)

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        ))
    calls.clear()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(ReviewRun(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out2",
            scanners="off",
            deep=True,
            resume=False,
        ))
    assert "p1" in calls
    assert "p2" in calls
    assert "p3" in calls
    assert list((tmp_path / "locks").rglob("*.json")) == []
