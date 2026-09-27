# tests/test_complexity_python_ast.py
"""B2 — Python stdlib ast cyclomatic + cognitive (fixture-proven)."""

from __future__ import annotations

from pathlib import Path

from repolens.complexity.python_ast import analyse_python_source

FIXTURES = Path(__file__).parent / "fixtures" / "complexity"


def test_simple_function_is_clean() -> None:
    src = FIXTURES.joinpath("simple.py").read_text(encoding="utf-8")
    funcs = analyse_python_source(src, path="simple.py")
    assert len(funcs) == 1
    f = funcs[0]
    assert f.name == "add"
    assert f.cyclomatic == 1
    assert f.cognitive == 0
    assert f.start_line == 1
    assert f.end_line >= f.start_line


def test_branchy_function_scores() -> None:
    src = FIXTURES.joinpath("branchy.py").read_text(encoding="utf-8")
    funcs = {f.name: f for f in analyse_python_source(src, path="branchy.py")}
    # def classify(x):
    #     if x < 0:        # cyclo+1 cog+1
    #         return "n"
    #     elif x == 0:     # cyclo+1 cog+1
    #         return "z"
    #     else:
    #         if x > 100:  # cyclo+1 cog+1(+nest1)=2
    #             return "b"
    #         return "p"
    f = funcs["classify"]
    assert f.cyclomatic == 4  # 1 + 3 decisions
    assert f.cognitive >= 4
    assert f.start_line >= 1


def test_skips_nested_functions_as_separate_entries() -> None:
    src = '''\
def outer(n):
    def inner(x):
        if x:
            return x
        return 0
    return inner(n)
'''
    funcs = analyse_python_source(src, path="nest.py")
    names = {f.name for f in funcs}
    assert "outer" in names
    assert "inner" in names
