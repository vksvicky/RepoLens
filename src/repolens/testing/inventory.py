# src/repolens/testing/inventory.py
"""F1 — Count test files and test cases (Python: ast), not file-only ratios."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import TestingInventoryBlock

_TEST_DIR_MARKERS = ("/tests/", "/test/")


def _is_python(entry: FileEntry) -> bool:
    return entry.relative.replace("\\", "/").endswith(".py")


def _looks_like_test_file(relative: str) -> bool:
    norm = relative.replace("\\", "/")
    name = Path(norm).name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    lower = f"/{norm.lower()}"
    return any(m in lower for m in _TEST_DIR_MARKERS)


def _is_unittest_testcase(bases: list[ast.expr]) -> bool:
    for base in bases:
        if isinstance(base, ast.Name) and base.id in {"TestCase", "IsolatedAsyncioTestCase"}:
            return True
        if isinstance(base, ast.Attribute) and base.attr in {
            "TestCase",
            "IsolatedAsyncioTestCase",
        }:
            return True
    return False


def _count_test_cases(source: str) -> int:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                count += 1
    return count


def _count_production_functions(source: str) -> int:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test"):
                count += 1
        elif isinstance(node, ast.ClassDef) and not _is_unittest_testcase(node.bases):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not child.name.startswith("test") and not child.name.startswith("_"):
                        # count public-ish methods; skip dunder-heavy noise lightly
                        if not (child.name.startswith("__") and child.name.endswith("__")):
                            count += 1
    return count


@dataclass
class TestingInventoryResult:
    block: TestingInventoryBlock = field(
        default_factory=lambda: TestingInventoryBlock()
    )


def run_testing_inventory(
    root: Path,
    entries: Sequence[FileEntry],
    *,
    enabled: bool = True,
) -> TestingInventoryResult:
    if not enabled:
        return TestingInventoryResult()

    test_files = 0
    test_cases = 0
    prod_funcs = 0
    notes: list[str] = []

    for entry in entries:
        if not _is_python(entry):
            continue
        try:
            text = entry.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            notes.append(f"skipped {entry.relative}: {exc}"[:200])
            continue
        if _looks_like_test_file(entry.relative):
            test_files += 1
            test_cases += _count_test_cases(text)
        else:
            prod_funcs += _count_production_functions(text)

    ratio = (
        round(test_cases / prod_funcs, 2) if prod_funcs > 0 else 0.0
    )
    block = TestingInventoryBlock(
        testFileCount=test_files,
        testCaseCount=test_cases,
        productionFunctionCount=prod_funcs,
        testsPerProductionFunction=ratio,
        notes=notes,
    )
    return TestingInventoryResult(block=block)
