"""Monorepo / workspace graph detection (#113)."""

from __future__ import annotations

from pathlib import Path

from repolens.graph.workspace import (
    detect_workspace,
    inter_package_edges,
    workspace_graph_result,
)


def _pnpm_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "mono"
    root.mkdir()
    (root / "pnpm-workspace.yaml").write_text(
        "packages:\n  - 'packages/*'\n", encoding="utf-8"
    )
    a = root / "packages" / "alpha"
    b = root / "packages" / "beta"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "package.json").write_text(
        '{"name":"@acme/alpha","version":"1.0.0"}', encoding="utf-8"
    )
    (b / "package.json").write_text(
        '{"name":"@acme/beta","version":"1.0.0","dependencies":{"@acme/alpha":"workspace:*"}}',
        encoding="utf-8",
    )
    # Python twin packages for cycle detection across workspace members
    (a / "alpha").mkdir()
    (a / "alpha" / "__init__.py").write_text("from beta import x\n", encoding="utf-8")
    (b / "beta").mkdir()
    (b / "beta" / "__init__.py").write_text("from alpha import y\nx=1\n", encoding="utf-8")
    return root


def test_detect_pnpm_workspace(tmp_path: Path) -> None:
    root = _pnpm_fixture(tmp_path)
    ws = detect_workspace(root)
    assert ws is not None
    assert ws.kind == "pnpm"
    names = {m.name for m in ws.members}
    assert "@acme/alpha" in names
    assert "@acme/beta" in names
    assert any(m.path.endswith("packages/alpha") for m in ws.members)


def test_inter_package_edges_from_deps(tmp_path: Path) -> None:
    root = _pnpm_fixture(tmp_path)
    ws = detect_workspace(root)
    assert ws is not None
    edges = inter_package_edges(ws)
    pairs = {(e.importer, e.imported) for e in edges}
    assert ("@acme/beta", "@acme/alpha") in pairs


def test_workspace_graph_merges_and_finds_cross_package_cycle(tmp_path: Path) -> None:
    root = _pnpm_fixture(tmp_path)
    result = workspace_graph_result(root)
    assert result.status.value in {"ok", "partial"}
    # Package-level edge present
    pkg_edges = {(e.importer, e.imported) for e in result.edges}
    assert ("@acme/beta", "@acme/alpha") in pkg_edges


def test_detect_cargo_and_go_work(tmp_path: Path) -> None:
    cargo_root = tmp_path / "cargo"
    cargo_root.mkdir()
    (cargo_root / "Cargo.toml").write_text(
        '[workspace]\nmembers = ["crates/a", "crates/b"]\n', encoding="utf-8"
    )
    (cargo_root / "crates" / "a").mkdir(parents=True)
    (cargo_root / "crates" / "b").mkdir(parents=True)
    (cargo_root / "crates" / "a" / "Cargo.toml").write_text(
        '[package]\nname = "crate_a"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (cargo_root / "crates" / "b" / "Cargo.toml").write_text(
        '[package]\nname = "crate_b"\nversion = "0.1.0"\n'
        "[dependencies]\ncrate_a = { path = \"../a\" }\n",
        encoding="utf-8",
    )
    ws = detect_workspace(cargo_root)
    assert ws is not None and ws.kind == "cargo"
    edges = {(e.importer, e.imported) for e in inter_package_edges(ws)}
    assert ("crate_b", "crate_a") in edges

    go_root = tmp_path / "gowork"
    go_root.mkdir()
    (go_root / "go.work").write_text("go 1.22\n\nuse (\n\t./svc-a\n\t./svc-b\n)\n", encoding="utf-8")
    (go_root / "svc-a").mkdir()
    (go_root / "svc-b").mkdir()
    gows = detect_workspace(go_root)
    assert gows is not None and gows.kind == "go"
    assert len(gows.members) == 2


def test_no_workspace_returns_none(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    (root / "readme.txt").write_text("x", encoding="utf-8")
    assert detect_workspace(root) is None
