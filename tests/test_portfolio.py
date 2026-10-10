"""``repolens portfolio`` multi-repo batch (#112)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.portfolio import PortfolioRepoResult, run_portfolio, write_portfolio_index

runner = CliRunner()


def test_write_portfolio_index_rollup(tmp_path: Path) -> None:
    out = tmp_path / "portfolio-reports"
    out.mkdir()
    rows = [
        PortfolioRepoResult(
            name="alpha",
            path="/tmp/alpha",
            ok=True,
            confidence=90,
            critical=0,
            high=1,
            cyclicity=0,
            report_dir=str(out / "alpha"),
            error=None,
        ),
        PortfolioRepoResult(
            name="beta",
            path="/tmp/beta",
            ok=False,
            confidence=None,
            critical=None,
            high=None,
            cyclicity=None,
            report_dir=None,
            error="scanners failed",
        ),
    ]
    index = write_portfolio_index(out, rows)
    text = index.read_text(encoding="utf-8")
    assert "alpha" in text and "beta" in text
    assert "90" in text
    assert "scanners failed" in text
    assert "Critical/High" in text or "high" in text.lower()


def test_run_portfolio_continues_on_failure(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.py").write_text("x=1\n", encoding="utf-8")
    (b / "y.py").write_text("y=1\n", encoding="utf-8")
    paths_file = tmp_path / "repos.txt"
    paths_file.write_text(f"{a}\n{b}\n", encoding="utf-8")
    out = tmp_path / "out"

    def fake_review(**kwargs):  # type: ignore[no-untyped-def]
        root = Path(kwargs["path"])
        if root.name == "b":
            raise RuntimeError("boom")
        dest = Path(kwargs["out"])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "gate_review_report_review_x.json").write_text(
            '{"confidence":88,"summary":{"critical":0,"high":0,"medium":0,"low":0},'
            '"issues":[]}',
            encoding="utf-8",
        )

    with patch("repolens.portfolio._run_repo_scanners", side_effect=fake_review):
        result = run_portfolio(paths_file, out, slow_brain=False)
    assert result.exit_code == 1  # soft-fail: some repos failed
    assert len(result.repos) == 2
    assert (out / "index.md").is_file()


def test_cli_portfolio(tmp_path: Path) -> None:
    a = tmp_path / "repo_a"
    a.mkdir()
    (a / "a.py").write_text("print(1)\n", encoding="utf-8")
    paths = tmp_path / "repos.txt"
    paths.write_text(f"{a}\n", encoding="utf-8")
    out = tmp_path / "portfolio-reports"

    with patch("repolens.portfolio._run_repo_scanners") as run:
        def _ok(**kwargs):  # type: ignore[no-untyped-def]
            dest = Path(kwargs["out"])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "gate_review_report_review_x.json").write_text(
                '{"confidence":70,"summary":{"critical":0,"high":2,"medium":0,"low":0},'
                '"issues":[],"graph":{"status":"ok","cyclicity":3,"cycleCount":1,'
                '"moduleCount":2}}',
                encoding="utf-8",
            )

        run.side_effect = _ok
        result = runner.invoke(
            app,
            [
                "portfolio", "--paths-file", str(paths),
                "--out", str(out),
            ],
        )
    assert result.exit_code == 0, result.output
    assert (out / "index.md").is_file()
    assert "repo_a" in (out / "index.md").read_text(encoding="utf-8")
