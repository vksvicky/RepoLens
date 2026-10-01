"""Deep-mode pass resume / coverage-closure / timeout retry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from repolens.config import AdaptiveConfig, DeepConfig, ModelConfig, RepoLensConfig
from repolens.llm_structured import StructuredLlmResult
from repolens.pipeline import run_review
from repolens.schema import FindingReport, Summary
from tests.pipeline_deep_support import _pass_report


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
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
            full_audit=True,
        )

    p3 = prompts["p3"]
    assert p3.index("## Source files") < p3.index("## Coverage checklist (required before JSON)")
    assert "arch.testing" in prompts["coverage"]
    assert result.report.coverage is not None
    assert "arch.testing" not in result.report.coverage.missed
    assert any(
        g.startswith("coverage:arch.testing: N/A") for g in result.report.durabilityGaps
    )


def test_second_deep_run_skips_finished_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REPOLENS_LOCK_DIR", str(tmp_path / "locks"))
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )
    calls: list[str] = []

    def fake_analyze(
        prompt, model_cfg, *, pass_id, progress=None, raw_dir=None, on_delta=None, **_
    ):
        calls.append(pass_id)
        return _pass_report(
            title=f"{pass_id} finding",
            file="a.py",
            priority="P1" if pass_id == "p1" else "P2" if pass_id == "p2" else "P3",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )
    first = list(calls)
    calls.clear()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )
    assert "p1" in first and "p2" in first and "p3" in first
    assert "p1" not in calls
    assert "p2" not in calls
    assert "p3" not in calls
    assert list((tmp_path / "locks").rglob("*.json")) == []


def test_timed_out_pass_is_retried_and_names_finished_passes(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="mock", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=False),
        deep=DeepConfig(enabled=True),
    )
    calls: list[str] = []

    def fake_analyze(
        prompt, model_cfg, *, pass_id, progress=None, raw_dir=None, on_delta=None, **_
    ):
        calls.append(pass_id)
        if pass_id == "p3":
            return StructuredLlmResult(
                report=FindingReport(
                    confidence=0,
                    summary=Summary(),
                    issues=[],
                    durabilityGaps=["LLM timed out after 30s waiting for the first token"],
                ),
                raw_text="",
                layer="degraded",
                error="timed out",
            )
        return _pass_report(
            title=f"{pass_id} finding",
            file="a.py",
            priority="P1" if pass_id == "p1" else "P2",
            coverage_na=[],
        )

    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        result = run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out",
            scanners="off",
            deep=True,
        )
    assert any(
        g.startswith("The P3 Architecture pass timed out.")
        and "P1 Security" in g
        and "Finished passes are kept." in g
        for g in result.report.durabilityGaps
    )
    calls.clear()
    with patch("repolens.llm_structured.analyze_structured", side_effect=fake_analyze):
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out2",
            scanners="off",
            deep=True,
        )
    assert "p3" in calls
    assert "p1" not in calls
    assert "p2" not in calls
