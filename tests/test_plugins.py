"""Plugin install / status (network mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.plugins import catalog, install_plugins, plugin_status

runner = CliRunner()


def test_catalog_has_mvp_tools() -> None:
    cat = catalog()
    assert set(cat) == {"gitleaks", "semgrep", "osv"}
    for tool in cat:
        assert "darwin-arm64" in cat[tool]
        assert "linux-amd64" in cat[tool]
    for plat, spec in cat["gitleaks"].items():
        assert spec.sha256 and len(spec.sha256) == 64, plat
    for plat, spec in cat["osv"].items():
        assert spec.sha256 and len(spec.sha256) == 64, plat


def test_download_rejects_checksum_mismatch(tmp_path: Path) -> None:
    from repolens.plugins import _download

    dest = tmp_path / "bin"
    with patch("repolens.plugins.httpx.stream") as stream:
        # Avoid real network: write bytes via a fake context manager
        class Resp:
            url = "https://example.com/x"
            def raise_for_status(self) -> None:
                return None
            def iter_bytes(self):
                yield b"not-the-expected-bytes"

        class CM:
            def __enter__(self):
                return Resp()
            def __exit__(self, *args):
                return False

        stream.return_value = CM()
        try:
            _download(
                "https://example.com/x",
                dest,
                sha256="0" * 64,
            )
            raised = False
        except RuntimeError as exc:
            raised = "checksum mismatch" in str(exc)
    assert raised
    assert not dest.exists()


def test_plugin_status_rows() -> None:
    with patch("repolens.plugins.resolve_binary", return_value=None):
        rows = plugin_status()
    assert len(rows) == 3
    assert all(state == "missing" for _, state, _ in rows)


def test_install_plugins_declined(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    with patch("repolens.plugins._platform_key", return_value="darwin-arm64"):
        messages = install_plugins(
            ["gitleaks"],
            yes=False,
            prompt_fn=lambda _msg: "n",
        )
    assert any("skipped (declined)" in m for m in messages)


def test_safe_extract_zip_rejects_traversal(tmp_path: Path) -> None:
    import zipfile

    from repolens.plugins import _safe_extract_zip

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "nope")
    dest = tmp_path / "out"
    dest.mkdir()
    try:
        _safe_extract_zip(archive, dest)
        raised = False
    except RuntimeError:
        raised = True
    assert raised


def test_install_plugins_binary_yes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def fake_download(url: str, dest: Path, *, sha256: str | None = None) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"#!/bin/sh\necho osv\n")

    with (
        patch("repolens.plugins._platform_key", return_value="linux-amd64"),
        patch("repolens.plugins._download", side_effect=fake_download),
    ):
        messages = install_plugins(["osv"], yes=True)
    assert any("installed" in m for m in messages), messages
    target = tmp_path / "cache" / "repolens" / "tools" / "osv" / "osv-scanner"
    assert target.is_file()
    assert target.stat().st_mode & 0o111


def test_cli_plugins_status() -> None:
    with patch("repolens.cli.plugins.plugin_status", return_value=[("gitleaks", "missing", "hint")]):
        result = runner.invoke(app, ["plugins", "status"])
    assert result.exit_code == 0, result.output
    assert "gitleaks" in result.output


def test_cli_plugins_install_yes_mocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    with patch("repolens.cli.plugins.install_plugins", return_value=["gitleaks: installed 8.24.0"]) as inst:
        result = runner.invoke(app, ["plugins", "install", "gitleaks", "--yes"])
    assert result.exit_code == 0, result.output
    inst.assert_called_once()
    assert inst.call_args.kwargs["yes"] is True


def test_cli_require_scanners_exit_2(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    from repolens.pipeline import ScannerRequirementError

    with patch(
        "repolens.cli.commands_review.run_review",
        side_effect=ScannerRequirementError(["gitleaks"]),
    ):
        result = runner.invoke(
            app,
            [
                "review",
                "--path",
                str(tmp_path),
                "--out",
                str(tmp_path / "out"),
                "--scanners-only",
                "--require-scanners",
            ],
        )
    assert result.exit_code == 2
    assert "missing" in result.output.lower()


def test_cli_scanners_only_mocked(tmp_path: Path) -> None:
    from repolens.pipeline import ReviewResult
    from repolens.schema import FindingReport, ScannerRun, Summary

    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    report = FindingReport(
        confidence=75,
        summary=Summary(),
        scannerRuns=[ScannerRun(tool="gitleaks", status="ran", findingCount=0)],
    )
    fake = ReviewResult(
        report=report,
        markdown_path=None,
        json_path=None,
        files_scanned=1,
        dry_run=False,
    )
    with patch("repolens.cli.commands_review.run_review", return_value=fake):
        result = runner.invoke(
            app,
            [
                "review",
                "--path",
                str(tmp_path),
                "--out",
                str(tmp_path / "out"),
                "--scanners-only",
            ],
        )
    assert result.exit_code == 0, result.output
