"""4KB pack sniff for role_packs ordering (Metis slice C)."""

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.pack_sniff import (
    content_score,
    is_demoted_asset,
    read_sniff_text,
    sniff_score,
)


def _entry(tmp_path: Path, relative: str, body: str) -> FileEntry:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return FileEntry(
        path=path, relative=relative, size=path.stat().st_size, priority_band=2
    )


def test_demoted_css_and_min_js() -> None:
    assert is_demoted_asset("assets/theme.css")
    assert is_demoted_asset("static/app.min.js")
    assert is_demoted_asset("logo.svg")
    assert not is_demoted_asset("src/client.py")


def test_p1_boosts_sql_exec_in_generic_client(tmp_path: Path) -> None:
    entry = _entry(
        tmp_path,
        "src/client.py",
        "def run(q):\n    cursor.execute('SELECT * FROM users')\n    os.system(q)\n",
    )
    plain = _entry(tmp_path, "src/util.py", "def add(a, b):\n    return a + b\n")
    assert sniff_score("p1", entry) > sniff_score("p1", plain)


def test_p2_boosts_retry_lock(tmp_path: Path) -> None:
    entry = _entry(
        tmp_path,
        "src/worker.py",
        "with lock:\n    for _ in range(3):\n        try:\n            pass\n"
        "        except Exception:\n            time.sleep(1)\n",
    )
    plain = _entry(tmp_path, "src/names.py", "NAMES = ['a']\n")
    assert sniff_score("p2", entry) > sniff_score("p2", plain)


def test_unreadable_falls_back_to_path_only(tmp_path: Path) -> None:
    missing = FileEntry(
        path=tmp_path / "gone.py",
        relative="gone.py",
        size=10,
        priority_band=2,
    )
    assert read_sniff_text(missing.path) == ""
    assert content_score("p1", "") == 0
    sniff_score("p1", missing)


def test_sniff_reads_at_most_4kb(tmp_path: Path) -> None:
    body = "x" * 8000 + "\ncursor.execute('SELECT 1')\n"
    entry = _entry(tmp_path, "src/big.py", body)
    assert content_score("p1", read_sniff_text(entry.path)) == 0
