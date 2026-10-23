"""Plugin install / status for optional scanner binaries."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from repolens.scanners.base import MANUAL_HINTS, resolve_binary, tools_cache_dir


@dataclass(frozen=True)
class AssetSpec:
    name: str
    version: str
    url: str
    kind: str  # "archive" | "binary" | "pip"
    archive_member: str | None = None
    pip_package: str | None = None
    sha256: str | None = None  # required for archive/binary downloads


def _platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-arm64"
    if system == "darwin":
        return "darwin-amd64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-amd64"
    if system == "linux" and machine in {"arm64", "aarch64"}:
        return "linux-arm64"
    raise RuntimeError(
        f"Unsupported platform for pinned scanner downloads: {system}/{machine}. "
        "Install tools manually (see docs/scanners.md)."
    )


def _gitleaks_assets() -> dict[str, AssetSpec]:
    gitleaks_v = "8.24.0"
    gl_base = f"https://github.com/gitleaks/gitleaks/releases/download/v{gitleaks_v}/"
    return {
        "darwin-arm64": AssetSpec(
            "gitleaks",
            gitleaks_v,
            f"{gl_base}gitleaks_{gitleaks_v}_darwin_arm64.tar.gz",
            "archive",
            archive_member="gitleaks",
            sha256="a3d281867df087ded8c2f9afd35d61ff923a25e64caa127b720991ee433d763b",
        ),
        "darwin-amd64": AssetSpec(
            "gitleaks",
            gitleaks_v,
            f"{gl_base}gitleaks_{gitleaks_v}_darwin_x64.tar.gz",
            "archive",
            archive_member="gitleaks",
            sha256="bd9ed3294c086f10dcc5fc25de57d44ba940c19c1a5a3d5f1cfeb10b9dff005e",
        ),
        "linux-amd64": AssetSpec(
            "gitleaks",
            gitleaks_v,
            f"{gl_base}gitleaks_{gitleaks_v}_linux_x64.tar.gz",
            "archive",
            archive_member="gitleaks",
            sha256="cb49b7de5ee986510fe8666ca0273a6cc15eb82571f2f14832c9e8920751f3a4",
        ),
        "linux-arm64": AssetSpec(
            "gitleaks",
            gitleaks_v,
            f"{gl_base}gitleaks_{gitleaks_v}_linux_arm64.tar.gz",
            "archive",
            archive_member="gitleaks",
            sha256="3755cc9b81f2466ad308f722a064ca04df27f59d551396183efe07978fef8fcb",
        ),
    }


def _osv_assets() -> dict[str, AssetSpec]:
    osv_v = "1.9.2"
    osv_base = f"https://github.com/google/osv-scanner/releases/download/v{osv_v}/"
    return {
        "darwin-arm64": AssetSpec(
            "osv",
            osv_v,
            f"{osv_base}osv-scanner_darwin_arm64",
            "binary",
            sha256="393f2c7089d9431bd26a3804d6e46d417b1c05abd5d49c41c7dfc174c520acf0",
        ),
        "darwin-amd64": AssetSpec(
            "osv",
            osv_v,
            f"{osv_base}osv-scanner_darwin_amd64",
            "binary",
            sha256="487ab433b2c2a8c80b737c0bd428a80e6d2e211b4adf775a52a6964163fa3249",
        ),
        "linux-amd64": AssetSpec(
            "osv",
            osv_v,
            f"{osv_base}osv-scanner_linux_amd64",
            "binary",
            sha256="d6af4b67fa5de658598bd2d445efb99e90d1734b3146962418719c4350ecb74b",
        ),
        "linux-arm64": AssetSpec(
            "osv",
            osv_v,
            f"{osv_base}osv-scanner_linux_arm64",
            "binary",
            sha256="9c6160afb26c79449a1f1b667323b989a57dda8fc19f22936c9ff920fd97ddfa",
        ),
    }


def _trivy_assets() -> dict[str, AssetSpec]:
    trivy_v = "0.73.0"
    trivy_base = f"https://github.com/aquasecurity/trivy/releases/download/v{trivy_v}/"
    return {
        "darwin-arm64": AssetSpec(
            "trivy",
            trivy_v,
            f"{trivy_base}trivy_{trivy_v}_macOS-ARM64.tar.gz",
            "archive",
            archive_member="trivy",
            sha256="80cc25faaf6378e37701202d0b4f9f43d9e413d198d594ba60fdf559fe44a683",
        ),
        "darwin-amd64": AssetSpec(
            "trivy",
            trivy_v,
            f"{trivy_base}trivy_{trivy_v}_macOS-64bit.tar.gz",
            "archive",
            archive_member="trivy",
            sha256="d39d1374dd3e35d48621b82df9b6625fe69f9920cc67d2739ed81bb679f16f51",
        ),
        "linux-amd64": AssetSpec(
            "trivy",
            trivy_v,
            f"{trivy_base}trivy_{trivy_v}_Linux-64bit.tar.gz",
            "archive",
            archive_member="trivy",
            sha256="2edd39da482bb4e9831962487b68f68e3928ec3137794757f54d00383d79547b",
        ),
        "linux-arm64": AssetSpec(
            "trivy",
            trivy_v,
            f"{trivy_base}trivy_{trivy_v}_Linux-ARM64.tar.gz",
            "archive",
            archive_member="trivy",
            sha256="13833d97e8a1a5367471c372a173180157f593bece570e20d5d925fef552f5dd",
        ),
    }


def _wheel(name: str, version: str, url: str, sha256: str) -> AssetSpec:
    return AssetSpec(
        name,
        version,
        url,
        "pip",
        pip_package=f"{name}=={version}",
        sha256=sha256,
    )


def _lock_manifest() -> dict:
    path = Path(__file__).resolve().parent / "plugin_locks" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _pip_assets(tool: str) -> dict[str, AssetSpec]:
    """Named-wheel identity from the hashed lock manifest."""
    block = _lock_manifest()["tools"][tool]
    version = str(block["version"])
    return {
        key: _wheel(tool, version, row["url"], row["sha256"])
        for key, row in block["platforms"].items()
    }


def catalog() -> dict[str, dict[str, AssetSpec]]:
    """Pinned release assets by tool → platform (with SHA-256 for native downloads)."""
    return {
        "gitleaks": _gitleaks_assets(),
        "osv": _osv_assets(),
        "semgrep": _pip_assets("semgrep"),
        "trivy": _trivy_assets(),
        "checkov": _pip_assets("checkov"),
    }


KNOWN_PLUGINS = ("gitleaks", "semgrep", "osv", "trivy", "checkov")


def plugin_status() -> list[tuple[str, str, str]]:
    """Return rows of (tool, state, path_or_hint)."""
    rows: list[tuple[str, str, str]] = []
    for tool in KNOWN_PLUGINS:
        names = ("osv-scanner", "osv") if tool == "osv" else (tool,)
        path = resolve_binary(tool, candidates=names)
        if path:
            rows.append((tool, "available", str(path)))
        else:
            rows.append((tool, "missing", MANUAL_HINTS[tool].split("\n")[0]))
    return rows


def _declined(tool: str, ask, spec: AssetSpec, messages: list[str]) -> bool:
    answer = str(ask(f"Download/install {tool} {spec.version}? [y/N] ")).strip().lower()
    if answer not in {"y", "yes"}:
        messages.append(f"{tool}: skipped (declined). Manual install:\n{MANUAL_HINTS[tool]}")
        return True
    return False


def install_plugins(
    tools: list[str],
    *,
    yes: bool,
    prompt_fn: Callable[[str], str] | None = None,
) -> list[str]:
    """Install tools into cache. Returns human messages."""
    ask = prompt_fn or (lambda msg: input(msg))
    key = _platform_key()
    cat = catalog()
    messages: list[str] = []
    selected = list(KNOWN_PLUGINS) if "all" in tools or not tools else tools
    for tool in selected:
        if tool not in cat:
            messages.append(f"Unknown plugin: {tool}")
            continue
        spec = cat[tool].get(key)
        if spec is None:
            messages.append(f"{tool}: no pinned asset for {key}")
            continue
        if _declined(tool, ask, spec, messages) if not yes else False:
            continue
        try:
            if spec.kind == "pip":
                _install_pip_tool(spec)
            elif spec.kind == "binary":
                _install_binary(spec)
            else:
                _install_archive(spec)
            messages.append(f"{tool}: installed {spec.version} → {tools_cache_dir() / tool}")
        except Exception as exc:  # noqa: BLE001 — surface install errors to CLI
            messages.append(f"{tool}: install failed: {exc}\n{MANUAL_HINTS[tool]}")
    return messages


_HASH_CHUNK = 1024 * 1024  # 1 MiB


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, *, sha256: str | None = None) -> None:
    if not url.startswith("https://"):
        raise RuntimeError("refusing non-HTTPS plugin download URL")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        final = str(response.url)
        if not final.startswith("https://"):
            raise RuntimeError("refusing redirect to non-HTTPS URL")
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    if sha256:
        actual = _sha256_file(dest)
        if actual != sha256:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {url}: expected {sha256}, got {actual}")


def _chmod_exec(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _require_sha256(spec: AssetSpec) -> str:
    if not spec.sha256:
        raise RuntimeError(f"missing pinned sha256 for {spec.name} {spec.version}")
    return spec.sha256


def _install_binary(spec: AssetSpec) -> None:
    out_dir = tools_cache_dir() / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ("osv-scanner" if spec.name == "osv" else spec.name)
    tmp = out_dir / ".download"
    _download(spec.url, tmp, sha256=_require_sha256(spec))
    tmp.replace(target)
    _chmod_exec(target)


def _is_within_directory(base: Path, candidate: Path) -> bool:
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return False


def _safe_extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:*") as tf:
        # Python 3.12+ data filter blocks path traversal / links escaping dest.
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="data")
        else:
            for member in tf.getmembers():
                member_path = dest / member.name
                if not _is_within_directory(dest, member_path):
                    raise RuntimeError(f"refusing unsafe archive member: {member.name}")
            tf.extractall(dest)


def _safe_extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            member_path = dest / info.filename
            if not _is_within_directory(dest, member_path):
                raise RuntimeError(f"refusing unsafe zip member: {info.filename}")
        zf.extractall(dest)


def _install_archive(spec: AssetSpec) -> None:
    out_dir = tools_cache_dir() / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / ".download"
    _download(spec.url, tmp, sha256=_require_sha256(spec))
    extract_dir = out_dir / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()
    if zipfile.is_zipfile(tmp):
        _safe_extract_zip(tmp, extract_dir)
    else:
        _safe_extract_tar(tmp, extract_dir)
    member_name = spec.archive_member or spec.name
    matches = [p for p in extract_dir.rglob(member_name) if p.is_file()]
    if not matches:
        raise RuntimeError(f"archive missing {member_name}")
    target = out_dir / member_name
    shutil.copy2(matches[0], target)
    _chmod_exec(target)
    tmp.unlink(missing_ok=True)


def _interpreter_python() -> tuple[int, int]:
    return sys.version_info[:2]


def _plugin_lock_file(name: str, platform_key: str) -> Path:
    """Hashed requirement lock for this interpreter. Missing lock fails closed."""
    major, minor = _interpreter_python()
    filename = f"{name}-{platform_key}-cp{major}{minor}.txt"
    path = Path(__file__).resolve().parent / "plugin_locks" / filename
    if not path.is_file():
        raise RuntimeError(
            f"{name.capitalize()} hash lock has no pin for {platform_key} CPython {major}.{minor}."
        )
    return path


def _require_lock_pins_wheel(lock: Path, digest: str, name: str) -> None:
    text = lock.read_text(encoding="utf-8")
    if f"--hash=sha256:{digest}" not in text:
        raise RuntimeError(f"checksum mismatch: {name} lock {lock.name} does not pin {digest}")


def _ensure_venv_python(name: str) -> Path:
    venv = tools_cache_dir() / f"{name}-venv"
    for candidate in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if candidate.exists():
            return candidate
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    for candidate in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if candidate.exists():
            return candidate
    raise RuntimeError(f"venv for {name} has no python interpreter")


def _install_pip_tool(spec: AssetSpec) -> None:
    """Install the tool and its dependencies with pip --require-hashes."""
    if not spec.url.startswith("https://files.pythonhosted.org/"):
        raise RuntimeError(f"refusing unpinned pip URL for {spec.name}")
    digest = _require_sha256(spec)
    lock = _plugin_lock_file(spec.name, _platform_key())
    _require_lock_pins_wheel(lock, digest, spec.name)
    venv_python = _ensure_venv_python(spec.name)
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--require-hashes", "-r", str(lock)],
        check=True,
    )


# Back-compat alias for older tests / call sites
_install_semgrep_pip = _install_pip_tool
