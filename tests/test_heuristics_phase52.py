"""Phase 5.2 extras (#92): large functions and transport/TLS hints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from repolens.heuristics import run_heuristics
from repolens.heuristics.paths import is_test_source
from repolens.inventory import FileEntry
from repolens.schema import Severity
from repolens.themes import theme_id_for_category


def _entry(root: Path, relative: str) -> FileEntry:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=3,
    )


def _fn_lines(name: str, inner_lines: int) -> str:
    body = "\n".join(f"    x{i} = {i}" for i in range(inner_lines))
    return f"def {name}():\n{body}\n"


def test_is_test_source_globs() -> None:
    assert is_test_source("tests/test_foo.py")
    assert is_test_source("src/foo_test.py")
    assert is_test_source("src/foo.test.ts")
    assert is_test_source("src/foo.spec.ts")
    assert is_test_source("testutils/helper.py")
    assert not is_test_source("src/app.py")


def test_theme_map_phase52_heuristics() -> None:
    assert theme_id_for_category("heuristic.large_function") == (
        "arch.readability_complexity"
    )
    assert theme_id_for_category("heuristic.transport_tls") == "sec.transport_tls"
    assert theme_id_for_category("heuristic.todo_density") == "arch.dead_code"


def test_large_function_boundary_79_vs_80(tmp_path: Path) -> None:
    # def + 78 body lines = 79; def + 79 body lines = 80.
    (tmp_path / "small.py").write_text(_fn_lines("small", 78), encoding="utf-8")
    (tmp_path / "big.py").write_text(_fn_lines("big", 79), encoding="utf-8")
    result = run_heuristics(
        tmp_path, [_entry(tmp_path, "small.py"), _entry(tmp_path, "big.py")]
    )
    hits = [i for i in result.issues if i.category == "heuristic.large_function"]
    assert [i.file for i in hits] == ["big.py"]
    assert hits[0].line == 1
    assert hits[0].severity == Severity.MEDIUM
    assert hits[0].priority == "P3"


def test_large_function_outer_includes_nested_inners_not_flagged(tmp_path: Path) -> None:
    inner = "\n".join(
        [
            "def outer():",
            "    def helper():",
            "        return 1",
            *[f"    y{i} = {i}" for i in range(77)],
        ]
    )
    (tmp_path / "nest.py").write_text(inner + "\n", encoding="utf-8")
    result = run_heuristics(tmp_path, [_entry(tmp_path, "nest.py")])
    hits = [i for i in result.issues if i.category == "heuristic.large_function"]
    assert len(hits) == 1
    assert "outer" in hits[0].title
    assert "helper" not in hits[0].title


def test_transport_skips_xmlns_and_flags_real_http(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(
        "NS = 'http://www.w3.org/2000/svg'\n"
        "SCHEMA = 'http://json-schema.org/draft-07/schema#'\n"
        "MS = 'http://schemas.microsoft.com/developer/msbuild/2003'\n"
        "POM = 'http://maven.apache.org/POM/4.0.0'\n"
        "LOCAL = 'http://localhost:8080/health'\n",
        encoding="utf-8",
    )
    (tmp_path / "bad.py").write_text(
        "API = 'http://evil.example/api'\n",
        encoding="utf-8",
    )
    result = run_heuristics(
        tmp_path, [_entry(tmp_path, "ok.py"), _entry(tmp_path, "bad.py")]
    )
    hits = [i for i in result.issues if i.category == "heuristic.transport_tls"]
    assert [i.file for i in hits] == ["bad.py"]
    assert hits[0].priority == "P1"
    assert hits[0].severity == Severity.MEDIUM


def test_transport_skips_comments_tests_and_weak_tls_hits(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "commented.py").write_text(
        "# fetch('http://evil.example/x')\nprint('ok')\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_http.py").write_text(
        "URL = 'http://evil.example/from-test'\n", encoding="utf-8"
    )
    (tmp_path / "src" / "tls.py").write_text(
        "import ssl\nctx = ssl.PROTOCOL_TLSv1\n",
        encoding="utf-8",
    )
    result = run_heuristics(
        tmp_path,
        [
            _entry(tmp_path, "src/commented.py"),
            _entry(tmp_path, "tests/test_http.py"),
            _entry(tmp_path, "src/tls.py"),
        ],
    )
    hits = [i for i in result.issues if i.category == "heuristic.transport_tls"]
    assert [i.file for i in hits] == ["src/tls.py"]


def test_unreadable_source_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "gone.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    entry = _entry(tmp_path, "gone.py")
    with patch.object(Path, "read_text", side_effect=OSError("nope")):
        result = run_heuristics(tmp_path, [entry])
    assert not any(
        i.category in {"heuristic.large_function", "heuristic.transport_tls"}
        for i in result.issues
    )
