"""File inventory ignores, caps, and P1 ordering."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import list_files


def test_ignores_venv_and_orders_p1_first(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    auth = tmp_path / "auth"
    auth.mkdir()
    (auth / "jwt.py").write_text("TOKEN='x'\n", encoding="utf-8")
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "site.py").write_text("secret\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")

    files = list_files(tmp_path)
    rels = [f.relative for f in files]
    assert "app.py" in rels
    assert "auth/jwt.py" in rels
    assert all(".venv" not in r for r in rels)
    assert all(not r.endswith(".png") for r in rels)
    assert files[0].relative == "auth/jwt.py"
    assert files[0].priority_band == 1


def test_max_files_boundary(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x=1\n", encoding="utf-8")
    files = list_files(tmp_path, max_files=3)
    assert len(files) == 3


def test_skips_symlinks_outside_root(tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("top-secret\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ok.py").write_text("x=1\n", encoding="utf-8")
    link = repo / "leak.txt"
    link.symlink_to(outside)
    files = list_files(repo)
    rels = [f.relative for f in files]
    assert "ok.py" in rels
    assert "leak.txt" not in rels
