"""File inventory ignores, caps, and P1 ordering."""

from __future__ import annotations

import subprocess
from pathlib import Path

from repolens.inventory import (
    classify_fingerprint_deletions,
    list_files,
    scan_inventory,
)


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


def test_named_virtualenvs_stay_out_of_inventory(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    for folder in (".venv-iconfix", ".venv-ml-ci", "venv-ml", "Venv_ci"):
        lib = tmp_path / folder / "lib"
        lib.mkdir(parents=True)
        (lib / "site.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "venue").mkdir()
    (tmp_path / "venue" / "keep.py").write_text("print(2)\n", encoding="utf-8")

    rels = [item.relative for item in list_files(tmp_path)]
    assert "src/app.py" in rels
    assert "venue/keep.py" in rels
    assert all(".venv-iconfix" not in rel for rel in rels)
    assert all(".venv-ml-ci" not in rel for rel in rels)
    assert all(not rel.startswith("venv-ml/") for rel in rels)
    assert all(not rel.lower().startswith("venv_ci/") for rel in rels)


def test_default_skip_paths_leave_generated_trees_out(tmp_path: Path) -> None:
    (tmp_path / "src" / "app.py").parent.mkdir()
    (tmp_path / "src" / "app.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "settings.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "gen").mkdir()
    (tmp_path / "gen" / "Rez.mcgen").write_text("gen\n", encoding="utf-8")
    files = list_files(tmp_path)
    rels = [f.relative for f in files]
    assert rels == ["src/app.py"]


def test_diff_mode_skips_generated_paths(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "settings.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "commit",
            "-m",
            "init",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "src" / "app.py").write_text("x=2\n", encoding="utf-8")
    (tmp_path / "bin" / "settings.json").write_text("{}\n\n", encoding="utf-8")
    files = list_files(tmp_path, mode="diff", since="HEAD")
    assert [f.relative for f in files] == ["src/app.py"]


def test_project_skip_paths_extend_the_defaults(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "blob.json").write_text("{}\n", encoding="utf-8")
    files = list_files(tmp_path, skip_globs=("**/fixtures/**",))
    assert [f.relative for f in files] == ["keep.py"]


def test_max_files_boundary(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x=1\n", encoding="utf-8")
    files = list_files(tmp_path, max_files=3)
    assert len(files) == 3


def test_scan_inventory_reports_truncation(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x=1\n", encoding="utf-8")
    inv = scan_inventory(tmp_path, max_files=3)
    assert inv.truncated
    assert inv.total_matched == 5
    assert len(inv.files) == 3
    note = inv.truncation_note()
    assert note is not None
    assert "3 of 5" in note
    assert "scanners" in note.lower()


def test_classify_fingerprint_deletions_splits_dropped(tmp_path: Path) -> None:
    (tmp_path / "kept.py").write_text("x=1\n", encoding="utf-8")
    removed, dropped = classify_fingerprint_deletions(
        tmp_path, ["kept.py", "gone.py"]
    )
    assert dropped == ["kept.py"]
    assert removed == ["gone.py"]


def test_ignores_superpowers_scratch(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x=1\n", encoding="utf-8")
    sdd = tmp_path / ".superpowers" / "sdd"
    sdd.mkdir(parents=True)
    (sdd / "huge.diff").write_text("diff --git a/x b/x\n" * 100, encoding="utf-8")
    files = list_files(tmp_path)
    rels = [f.relative for f in files]
    assert "ok.py" in rels
    assert all(".superpowers" not in r for r in rels)


def test_ignores_rust_target_and_reports(tmp_path: Path) -> None:
    (tmp_path / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
    tgt = tmp_path / "target" / "debug"
    tgt.mkdir(parents=True)
    (tgt / "build_script.rs").write_text("// generated\n", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "gate.md").write_text("# old\n", encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports=1\n", encoding="utf-8")
    files = list_files(tmp_path)
    rels = [f.relative for f in files]
    assert "main.rs" in rels
    assert all("target/" not in r and not r.startswith("target/") for r in rels)
    assert all("reports/" not in r for r in rels)
    assert all("node_modules/" not in r for r in rels)


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
