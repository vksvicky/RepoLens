"""Trivy registry-auth matrix A–J (#94) — mocked subprocess, no network."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from repolens.config import TrivyScannerConfig
from repolens.scanners.sca_sbom import write_trivy_sbom
from repolens.scanners.trivy import run_trivy
from repolens.scanners.trivy_env import redact_secrets


def _completed(
    code: int = 0, stdout: str = "{}", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["trivy"], returncode=code, stdout=stdout, stderr=stderr
    )


def _cve_json(vid: str) -> str:
    return json.dumps(
        {
            "Results": [
                {
                    "Target": "req.txt",
                    "Vulnerabilities": [
                        {"VulnerabilityID": vid, "PkgName": "demo", "Severity": "HIGH"}
                    ],
                }
            ]
        }
    )


def test_redact_ignores_empty_and_short_secrets() -> None:
    env = {"TRIVY_PASSWORD": "", "TRIVY_REGISTRY_TOKEN": "ab", "TRIVY_USERNAME": "bot"}
    noisy = "error " + ("x" * 40)
    assert "***" not in redact_secrets(noisy, env)
    long = redact_secrets("leak secret123 here", {"TRIVY_PASSWORD": "secret123"})
    assert "secret123" not in long
    assert "***" in long


def test_matrix_a_no_trivy_password_in_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("TRIVY_USERNAME", "TRIVY_PASSWORD", "TRIVY_REGISTRY_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    seen: dict[str, Any] = {}

    def fake_run(*_a: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["password"] = env.get("TRIVY_PASSWORD")
        return _completed(stdout="{}")

    binary = tmp_path / "trivy"
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        result = run_trivy(
            tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ)
        )
    assert result.run.status == "ran"
    assert seen.get("password") is None


def test_matrix_b_user_password_not_in_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIVY_USERNAME", "ci-bot")
    monkeypatch.setenv("TRIVY_PASSWORD", "supersecret")
    seen: dict[str, Any] = {}

    def fake_run(*_a: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["user"] = env.get("TRIVY_USERNAME")
        seen["password"] = env.get("TRIVY_PASSWORD")
        return _completed(code=2, stderr="auth failed supersecret")

    binary = tmp_path / "trivy"
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        result = run_trivy(
            tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ)
        )
    assert seen["user"] == "ci-bot"
    assert seen["password"] == "supersecret"
    assert result.run.status == "failed"
    assert "supersecret" not in (result.run.detail or "")


def test_matrix_c_token_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIVY_USERNAME", raising=False)
    monkeypatch.delenv("TRIVY_PASSWORD", raising=False)
    monkeypatch.setenv("TRIVY_REGISTRY_TOKEN", "tokensecret99")
    seen: dict[str, Any] = {}

    def fake_run(*_a: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["token"] = env.get("TRIVY_REGISTRY_TOKEN")
        return _completed(stdout="{}")

    binary = tmp_path / "trivy"
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        run_trivy(tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ))
    assert seen["token"] == "tokensecret99"


def test_matrix_d_incomplete_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIVY_USERNAME", "ci-bot")
    monkeypatch.delenv("TRIVY_PASSWORD", raising=False)
    monkeypatch.delenv("TRIVY_REGISTRY_TOKEN", raising=False)
    with patch("repolens.scanners.trivy.subprocess.run") as run:
        result = run_trivy(
            tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ)
        )
    run.assert_not_called()
    assert result.run.status == "failed"
    assert "incomplete" in (result.run.detail or "").lower()


def test_matrix_e_redacts_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIVY_PASSWORD", "hunter2x")
    monkeypatch.delenv("TRIVY_USERNAME", raising=False)
    binary = tmp_path / "trivy"
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch(
            "repolens.scanners.trivy.subprocess.run",
            return_value=_completed(code=2, stderr="denied hunter2x"),
        ),
    ):
        result = run_trivy(
            tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ)
        )
    assert "hunter2x" not in (result.run.detail or "")
    assert "***" in (result.run.detail or "")


def test_matrix_f_image_refs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRIVY_REGISTRY_TOKEN", "tokensecret99")
    argv: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        argv.append(list(cmd))
        return _completed(stdout="{}")

    binary = tmp_path / "trivy"
    cfg = TrivyScannerConfig(images=["repo.example/app:1", "repo.example/app:2"])
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        run_trivy(tmp_path, trivy_cfg=cfg, environ=dict(os.environ))
    image_cmds = [c for c in argv if "image" in c]
    assert len(image_cmds) == 2
    assert "repo.example/app:1" in image_cmds[0]
    assert "repo.example/app:2" in image_cmds[1]


def test_matrix_g_sbom_gets_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIVY_USERNAME", "ci-bot")
    monkeypatch.setenv("TRIVY_PASSWORD", "supersecret")
    seen: dict[str, Any] = {}

    def fake_run(*_a: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["password"] = env.get("TRIVY_PASSWORD")
        dest = Path(str(kwargs.get("cwd") or tmp_path))
        # write_trivy_sbom passes -o dest; create the file
        return _completed(stdout="")

    binary = tmp_path / "trivy"
    out = tmp_path / "out"
    out.mkdir()
    dest = out / "sbom.cdx.json"

    def fake_run_sbom(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["password"] = env.get("TRIVY_PASSWORD")
        Path(cmd[cmd.index("-o") + 1]).write_text("{}", encoding="utf-8")
        return _completed(stdout="")

    with (
        patch("repolens.scanners.sca_sbom.resolve_binary", return_value=binary),
        patch("repolens.scanners.sca_sbom.subprocess.run", side_effect=fake_run_sbom),
    ):
        path, _detail = write_trivy_sbom(
            tmp_path,
            out,
            trivy_cfg=TrivyScannerConfig(),
            environ=dict(os.environ),
        )
    assert path == dest
    assert seen["password"] == "supersecret"


def test_matrix_h_pass_registry_env_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIVY_PASSWORD", "supersecret")
    seen: dict[str, Any] = {}

    def fake_run(*_a: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        seen["password"] = env.get("TRIVY_PASSWORD")
        return _completed(stdout="{}")

    binary = tmp_path / "trivy"
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        run_trivy(
            tmp_path,
            trivy_cfg=TrivyScannerConfig(pass_registry_env=False),
            environ=dict(os.environ),
        )
    assert seen.get("password") is None


def test_matrix_i_empty_password_not_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIVY_PASSWORD", "")
    monkeypatch.delenv("TRIVY_USERNAME", raising=False)
    binary = tmp_path / "trivy"
    blob = "x" * 80
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch(
            "repolens.scanners.trivy.subprocess.run",
            return_value=_completed(code=2, stderr=blob),
        ),
    ):
        result = run_trivy(
            tmp_path, trivy_cfg=TrivyScannerConfig(), environ=dict(os.environ)
        )
    assert (result.run.detail or "").count("***") == 0


def test_matrix_j_partial_image_keeps_fs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRIVY_USERNAME", raising=False)

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        if "image" in cmd and "bad:tag" in cmd:
            return _completed(code=2, stderr="auth fail")
        if "image" in cmd:
            return _completed(stdout=_cve_json("CVE-IMG"))
        return _completed(stdout=_cve_json("CVE-FS"))

    binary = tmp_path / "trivy"
    cfg = TrivyScannerConfig(images=["bad:tag", "good:tag"])
    with (
        patch("repolens.scanners.trivy.resolve_binary", return_value=binary),
        patch("repolens.scanners.trivy.subprocess.run", side_effect=fake_run),
    ):
        result = run_trivy(tmp_path, trivy_cfg=cfg, environ=dict(os.environ))
    ids = {i.advisoryId for i in result.issues}
    assert "CVE-FS" in ids
    assert "CVE-IMG" in ids
    assert "bad:tag" in (result.run.detail or "")
