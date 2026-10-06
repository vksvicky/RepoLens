"""#95 relative specifier → repo-relative path (JS/TS extension fallbacks)."""

from __future__ import annotations

from pathlib import Path

from repolens.graph.resolve_spec import canonicalize_import


def test_ts_relative_user_file(tmp_path: Path) -> None:
    (tmp_path / "src/api").mkdir(parents=True)
    (tmp_path / "src/api/routes.ts").write_text("export {}", encoding="utf-8")
    (tmp_path / "src/api/user.ts").write_text("export {}", encoding="utf-8")
    got = canonicalize_import(
        "src/api/routes.ts", "./user", root=tmp_path
    )
    assert got == "src/api/user.ts"


def test_ts_relative_index_and_parent_dir(tmp_path: Path) -> None:
    (tmp_path / "src/controllers").mkdir(parents=True)
    (tmp_path / "src/services").mkdir(parents=True)
    (tmp_path / "src/controllers/user.ts").write_text("export {}", encoding="utf-8")
    (tmp_path / "src/services/user.ts").write_text("export {}", encoding="utf-8")
    got = canonicalize_import(
        "src/controllers/user.ts", "../services/user", root=tmp_path
    )
    assert got == "src/services/user.ts"

    (tmp_path / "src/services/auth").mkdir()
    (tmp_path / "src/services/auth/index.ts").write_text("export {}", encoding="utf-8")
    indexed = canonicalize_import(
        "src/controllers/user.ts", "../services/auth", root=tmp_path
    )
    assert indexed == "src/services/auth/index.ts"


def test_missing_file_still_repo_relative(tmp_path: Path) -> None:
    (tmp_path / "src/api").mkdir(parents=True)
    got = canonicalize_import(
        "src/api/routes.ts", "./missing", root=tmp_path
    )
    assert got == "src/api/missing"
    assert ".." not in got


def test_bare_package_unchanged(tmp_path: Path) -> None:
    assert canonicalize_import("src/a.ts", "react", root=tmp_path) == "react"
    assert canonicalize_import("src/a.go", "fmt", root=tmp_path) == "fmt"
    assert canonicalize_import("src/a.ts", "file:ignore", root=tmp_path) == "file:ignore"
    assert canonicalize_import("src/a.ts", "  ", root=tmp_path) == ""
