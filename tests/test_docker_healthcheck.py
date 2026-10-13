"""The published image declares a HEALTHCHECK and checks scanner archives."""

from pathlib import Path

from repolens.plugins import catalog

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_runtime_stage_has_healthcheck() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = text.split("FROM python:${PYTHON_VERSION}-slim-bookworm")[-1]
    assert "HEALTHCHECK" in runtime
    assert "repolens version" in runtime


def test_dockerfile_linux_hashes_match_plugin_catalog() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cat = catalog()
    for tool in ("gitleaks", "osv", "trivy"):
        for plat in ("linux-amd64", "linux-arm64"):
            digest = cat[tool][plat].sha256
            assert digest and digest in text
    assert "sha256sum -c" in text
    scanner_run = text.split("WORKDIR /opt/scanners", 1)[1].split("WORKDIR /src", 1)[0]
    assert "python" not in scanner_run.lower()


def test_dockerfile_installs_hashed_cp312_semgrep_lock() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes" in text
    assert ".[scanners]" not in text
    locks = ROOT / "src" / "repolens" / "plugin_locks"
    for plat in ("linux-amd64", "linux-arm64"):
        name = f"semgrep-{plat}-cp312.txt"
        assert name in text
        digest = catalog()["semgrep"][plat].sha256
        assert digest and f"--hash=sha256:{digest}" in (locks / name).read_text(encoding="utf-8")
        assert "cp312" in catalog()["semgrep"][plat].url
