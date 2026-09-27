# tests/test_testing_inventory.py
"""F1 — Fast Brain test inventory: files + test cases via ast."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.testing.inventory import run_testing_inventory


def _entry(tmp: Path, relative: str, source: str) -> FileEntry:
    path = tmp / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return FileEntry(
        path=path, relative=relative, size=path.stat().st_size, priority_band=3
    )


def test_inventory_counts_test_functions_not_just_files(tmp_path: Path) -> None:
    prod = _entry(
        tmp_path,
        "src/app.py",
        "def a():\n    return 1\n\ndef b():\n    return 2\n",
    )
    tests = _entry(
        tmp_path,
        "tests/test_app.py",
        "\n".join(
            [
                "def test_a():",
                "    assert True",
                "",
                "def test_b():",
                "    assert True",
                "",
                "def helper():",
                "    return 1",
                "",
                "import unittest",
                "",
                "class T(unittest.TestCase):",
                "    def test_c(self):",
                "        self.assertTrue(True)",
                "    def setUp(self):",
                "        pass",
            ]
        )
        + "\n",
    )
    result = run_testing_inventory(tmp_path, [prod, tests])
    assert result.block.testFileCount == 1
    assert result.block.testCaseCount == 3  # test_a, test_b, test_c
    assert result.block.productionFunctionCount == 2
    assert abs(result.block.testsPerProductionFunction - 1.5) < 0.01


def test_inventory_disabled(tmp_path: Path) -> None:
    e = _entry(tmp_path, "tests/test_x.py", "def test_x():\n    pass\n")
    result = run_testing_inventory(tmp_path, [e], enabled=False)
    assert result.block.testFileCount == 0
    assert result.block.testCaseCount == 0
