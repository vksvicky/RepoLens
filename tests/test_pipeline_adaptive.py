"""Adaptive cache wired into run_review."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from repolens.config import AdaptiveConfig, ModelConfig, RepoLensConfig
from repolens.learning.store import ProjectStore, store_db_path
from repolens.pipeline import run_review
from repolens.schema import FindingReport, Summary


def test_dry_run_syncs_fingerprints(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None),
        adaptive=AdaptiveConfig(enabled=True),
    )
    run_review(
        path=tmp_path,
        mode="review",
        dry_run=True,
        config=cfg,
        out_dir=tmp_path / "out",
    )
    assert store_db_path(tmp_path).is_file()
    with ProjectStore(tmp_path) as store:
        fps = store.list_fingerprints()
    assert "a.py" in fps


def test_adaptive_disabled_skips_db(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider=None),
        adaptive=AdaptiveConfig(enabled=False),
    )
    run_review(
        path=tmp_path,
        mode="review",
        dry_run=True,
        config=cfg,
        out_dir=tmp_path / "out",
    )
    assert not store_db_path(tmp_path).is_file()


def test_llm_pack_shrinks_on_second_run(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text("def login(): pass\n", encoding="utf-8")
    (tmp_path / "util.py").write_text("def helper(): pass\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="qwen2.5:7b", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=True, mode="auto"),
    )
    from repolens.llm_structured import StructuredLlmResult
    fake = FindingReport(confidence=50, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(report=fake, raw_text="", layer="coerced", error=None)

    with patch("repolens.llm_structured.analyze_structured", return_value=fake_result) as mocked:
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out1",
            scanners="off",
            deep=False,
        )
        first_prompt = mocked.call_args[0][0]
        assert "auth.py" in first_prompt and "util.py" in first_prompt

        (tmp_path / "auth.py").write_text("def login(): return 1\n", encoding="utf-8")
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "out2",
            scanners="off",
            deep=False,
        )
        second_prompt = mocked.call_args[0][0]
        assert "auth.py" in second_prompt
        # util unchanged and not P1 → omitted in auto mode
        assert "util.py" not in second_prompt


def test_force_changed_skips_llm_when_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("print(1)\n", encoding="utf-8")
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="x", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=True, mode="auto"),
    )
    from repolens.llm_structured import StructuredLlmResult
    fake = FindingReport(confidence=50, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(report=fake, raw_text="", layer="coerced", error=None)
    with patch("repolens.llm_structured.analyze_structured", return_value=fake_result) as mocked:
        run_review(
            path=repo,
            mode="review",
            config=cfg,
            out_dir=out1,
            scanners="off",
            deep=False,
        )
        assert mocked.call_count == 1
        result = run_review(
            path=repo,
            mode="review",
            config=cfg,
            out_dir=out2,
            scanners="off",
            force_changed=True,
            deep=False,
        )
        assert mocked.call_count == 1  # no second LLM call
        assert result.report.confidence == 80
        assert any("skipped LLM" in g for g in result.report.durabilityGaps)





def test_force_full_includes_all(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text("def login(): pass\n", encoding="utf-8")
    (tmp_path / "util.py").write_text("def helper(): pass\n", encoding="utf-8")
    cfg = RepoLensConfig(
        model=ModelConfig(provider="ollama", model="x", timeout_seconds=30),
        adaptive=AdaptiveConfig(enabled=True, mode="auto"),
    )
    from repolens.llm_structured import StructuredLlmResult
    fake = FindingReport(confidence=50, summary=Summary(), issues=[])
    fake_result = StructuredLlmResult(report=fake, raw_text="", layer="coerced", error=None)
    with patch("repolens.llm_structured.analyze_structured", return_value=fake_result) as mocked:
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "o1",
            scanners="off",
            deep=False,
        )
        (tmp_path / "auth.py").write_text("def login(): return 2\n", encoding="utf-8")
        run_review(
            path=tmp_path,
            mode="review",
            config=cfg,
            out_dir=tmp_path / "o2",
            scanners="off",
            force_full=True,
            deep=False,
        )
        prompt = mocked.call_args[0][0]
        assert "auth.py" in prompt and "util.py" in prompt
