"""Tests for automatic offline fallback cascade in RepoLens."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from repolens.config import ModelConfig, RepoLensConfig
from repolens.llm import LlmError
from repolens.pipeline import run_review


def test_fallback_config_default():
    cfg = ModelConfig()
    assert cfg.fallback is True


def test_run_review_fallback_to_scanners_when_no_ollama(tmp_path: Path):
    # Create a small dummy file to review
    f = tmp_path / "main.py"
    f.write_text("def hello():\n    print('world')\n")

    cfg = RepoLensConfig()
    cfg.model.provider = None
    cfg.model.fallback = True

    with patch("repolens.llm.setup.detect_ollama", return_value=False):
        res = run_review(
            path=tmp_path,
            mode="sentinel",
            config=cfg,
            scanners="off",
        )

    assert res.report is not None
    assert res.report.llmSkipped is True
    assert any("Fallback:" in gap for gap in res.report.durabilityGaps)


def test_run_review_no_fallback_raises_llm_error(tmp_path: Path):
    f = tmp_path / "main.py"
    f.write_text("def hello():\n    print('world')\n")

    cfg = RepoLensConfig()
    cfg.model.provider = None
    cfg.model.fallback = False

    with patch("repolens.llm.setup.detect_ollama", return_value=False):
        with pytest.raises(LlmError) as exc_info:
            run_review(
                path=tmp_path,
                mode="sentinel",
                config=cfg,
                scanners="off",
                fallback=False,
            )

    assert "No model provider configured" in str(exc_info.value)
