"""Coverage seed config: load from project .repolens.toml and deep evaluate path."""

from __future__ import annotations

from pathlib import Path

from repolens.config import CoverageConfig, load_config
from repolens.coverage import evaluate_coverage
from repolens.themes import build_theme_breakdown


def test_load_coverage_seeds_from_project_toml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        "[coverage.na]\n"
        'sec.xss_csrf = "Native desktop app; no web/DOM attack surface"\n'
        "\n"
        "[coverage.covered]\n"
        'sec.injection = "Audited: no SQL or shell=True sinks in reviewed pack"\n',
        encoding="utf-8",
    )

    cfg = load_config(project, trust_project=False)
    assert cfg.coverage.na["sec.xss_csrf"].startswith("Native desktop")
    assert cfg.coverage.covered["sec.injection"].startswith("Audited:")


def test_coverage_seeds_load_without_trust_project(tmp_path: Path, monkeypatch) -> None:
    """Coverage seeds are safe project config (not in PROJECT_MODEL_DENY)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        '[model]\nprovider = "ollama"\nbase_url = "http://evil.test"\n'
        "\n"
        "[coverage.na]\n"
        'arch.testing = "Out of scope: no test harness in this crate"\n',
        encoding="utf-8",
    )

    cfg = load_config(project, trust_project=False)
    assert cfg.model.provider is None  # stripped without trust
    assert cfg.coverage.na["arch.testing"].startswith("Out of scope")


def test_deep_evaluate_path_uses_loaded_seeds() -> None:
    """Same wiring as deep_exec: cfg.coverage → evaluate_coverage → theme notes."""
    cfg = type(
        "Cfg",
        (),
        {
            "coverage": CoverageConfig(
                na={"sec.xss_csrf": "CLI tool; no browser surface"},
                covered={"sec.injection": "Audited: argv-only subprocess"},
            )
        },
    )()
    unique_ids = ["sec.injection", "sec.xss_csrf"]
    coverage = evaluate_coverage(
        unique_ids,
        [],
        [],
        seeded_na=cfg.coverage.na,
        seeded_covered=cfg.coverage.covered,
    )
    themes = build_theme_breakdown(coverage, [], mode="review", full_audit=False)
    by_id = {t.id: t for t in themes}
    assert by_id["sec.injection"].notes.startswith("Audited:")
    assert "cli tool" in by_id["sec.xss_csrf"].notes.lower()
