#!/usr/bin/env python3
"""Write one student note per file under src/ and tests/.

The notes land in docs/learn/src and docs/learn/tests, mirroring the tree.
Re-run after the code changes:

    python scripts/generate_learn_file_notes.py

Fail if a source or test file was added, removed, or edited without
regenerating the notes:

    python scripts/generate_learn_file_notes.py --check
"""

from __future__ import annotations

import argparse
import ast
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
LEARN = ROOT / "docs" / "learn"

# Teaching notes for algorithms a name and a docstring do not explain.
# Key is "relative/path.py::qualname".
ALGORITHMS: dict[str, str] = {
    "src/repolens/complexity/python_ast.py::_cognitive": """\
Cyclomatic complexity counts decision points. Cognitive complexity counts how hard those decisions are to follow, and it adds the current nesting depth so a branch inside a loop costs more than a branch at the top. `elif` stays at the same nesting as its `if`. `else` adds one more. Boolean `and` / `or` chains add one per extra term, not a new nesting level. Nested functions are skipped so a helper defined inside is scored on its own.

A pure McCabe count would treat a flat chain of guards the same as a staircase of nested `if`s. Students feel the staircase and miss the guards. Cognitive scoring matches that feeling. The cost is a second number to explain. Regex indentation counts (the deep-nesting rule) are cheaper and language-agnostic, and they miss `if`s that sit on one line. Both stay in the product for that reason.
""",
    "src/repolens/complexity/python_ast.py::_cyclomatic": """\
McCabe’s number starts at 1 and adds 1 for each branch, loop, exception handler, `with`, assertion, conditional expression, and comprehension. That is “how many paths a test might need,” not “how pretty the function looks.”

The alternative is a token counter or a linter’s statement count. Those grow when you add comments-worth of code that does not add a path, and they stay flat when a dense one-liner adds three branches. Path count is the right input for “is this hard to test.” It still ignores data complexity, so a function of ten straight assignments can be hard for other reasons and will not show up here.
""",
    "src/repolens/deep_budget.py::budget_files": """\
Greedy fill: walk the files in the order already chosen, add a file when its size still fits in the character budget, skip it when it does not. A later smaller file can still fit. This is the bin-packing shortcut, not an optimal pack.

An optimal pack (knapsack) could fit more source into the same 100,000 characters by reordering. Reordering would hide the hot-path priority: a risky file skipped to make room for three boring ones is the wrong trade for a review. The effect of greedy-in-order is that the front of the list is what the model sees, and a huge file does not shove every later file out.
""",
    "src/repolens/deep_budget.py::_order_entries": """\
Stable priority merge. Hot paths from the Fast Brain come first, then paths remembered from an earlier run, then whatever order the inventory already had. Duplicates are dropped.

Sorting only by size would fill the budget with the smallest files and might never send the file the rules already flagged. Sorting only by recency would ignore a secret-shaped file that did not change today. Hot-path-first makes the mechanical findings decide who gets the model’s attention.
""",
    "src/repolens/pipeline/pass_cache.py::pass_key": """\
SHA-256 over the template version, the RepoLens version, the model name, the pass name, each file path, and each file’s own SHA-256, then pack mode and any prior-pass summary. The hex digest is the cache filename.

A timestamp key would never resume. A key of only the file names would resume after an edit and hide the new code. A non-cryptographic hash would be faster and could collide, which would show the wrong saved pass. SHA-256 is slower by a file read you were going to do anyway, and a collision is not a practical concern. Changing the model name on purpose misses the cache, so a cloud answer is not reused as a local one.
""",
    "src/repolens/heuristics/near_clones.py::find_near_clones": """\
Sliding windows of source lines are normalised (imports and headers can be skipped) and hashed. Windows that share a hash across files become clone pairs. Caps stop the report filling up: a minimum number of occurrences, a maximum number of clusters, a maximum number of findings.

A token AST clone detector (SourcererCC, a real clone tool) finds reordered or renamed copies and costs a parser per language plus much more CPU. A whole-file hash finds only exact file copies and misses a function pasted twice. The window hash sits in between: it is language-light, fast enough for the Fast Brain, and blind to clones that do not share a run of lines.
""",
    "src/repolens/blast_radius.py::expand_blast_radius": """\
Start from the git change-set. Add modules that import a changed module or are imported by one, using the import graph (grimp) one hop out. That set is the “what else is next to this change” pack.

Taking the whole repository is safer and blows the character budget. Taking only the diff misses the caller that will break. Two or three hops would pull in a large fraction of a small program and start to look like the whole tree. One hop is the compromise: neighbours, not the family reunion.
""",
    "src/repolens/llm/sse.py::StreamWatch.check": """\
Two clocks. Before the first token, the whole `--timeout` is the wait for the model to start writing. After the first token, the same `--timeout` is still the total time for the pass, and a second clock aborts if five minutes pass with no new text.

The earlier design let a pass run as long as tokens kept arriving. A rambling model then occupied the machine for hours. Stopping only on silence would still allow that. Stopping at `--timeout` even while tokens arrive caps the wait. The effect is a cut-off answer and a saved record of the passes that already finished. You re-run; you do not get the discarded half sentence.
""",
    "src/repolens/llm/model_lock.py": """\
A file lock so two RepoLens processes do not both talk to one local Ollama. Cloud providers skip the lock. The queue records who is waiting.

An in-process mutex would not see a second terminal. A database lock would be a server this project refuses to require. The file lock is visible across processes on one machine and useless across two machines, which matches where Ollama actually runs.
""",
    "src/repolens/pack_sniff.py::content_score": """\
Read at most the first 4 KB and count regex hits that look like the band’s topic (secrets and shell for security, retries and locks for reliability). The score sorts files. It does not create findings.

Sending those paths to the model to decide the order would spend the slow part of the review before the review starts. A full parse would be more accurate and would need a parser per language. Four kilobytes and a regex are wrong on minified lines and on code that does the risky thing past the first 4 KB. They are cheap enough to run on every candidate when role packs are on. Role packs are off by default, so a normal review does not use this sort.
""",
    "src/repolens/graph/cycles.py": """\
Import cycles are strongly connected components in the import graph: a set of modules that can all reach each other. The implementation asks the graph library (grimp) rather than writing a fresh Tarjan search.

A hand-rolled depth-first search would be fewer dependencies and more code to get wrong on dynamic imports. Ignoring cycles would make the architecture pass miss the loops people cannot refactor safely. The effect of using the library is that Python import graphs are real, and other languages need their own adapter.
""",
    "src/repolens/inventory.py": """\
Walk the tree, drop ignored and binary files, then keep the top of the list by priority up to `max_files`. The Fast Brain cap and the Slow Brain cap are different numbers on purpose (10,000 versus 200).

Loading every file into memory would make a monorepo’s review start swap. A random sample would be faster to explain and would skip the auth package whenever it felt like it. Priority order plus a hard cap keeps the risky paths and admits the review cannot be the whole tree.
""",
    "src/repolens/cli/resolved_argv.py::strip_url_userinfo": """\
Only `http` and `https` lose their userinfo, query, and fragment. `git@host:path` has no `://`, so it is returned unchanged. `ssh://` has a scheme that is not http or https, so it is returned unchanged. A query is removed even when there is no `user:pass@`, because a token often sits in the query.

Stripping every URL scheme would break SSH remotes that are not secrets. Leaving the query in place would copy a token into the report’s provenance. The effect is that a pasted command can be re-run, and the credential that was embedded in the URL is not published with the report.
""",
    "src/repolens/cli/resolved_argv.py::build_expanded_argv": """\
Presets are applied earlier, in `apply_preset`. A preset fills only a flag that is still at its CLI default. An explicit flag keeps the value the operator typed. `repolens audit` is that same release resolution plus ratchet and verify, and it does not take `--preset`.

This function records the bag after that resolution. It writes `repolens` and the mode, then the target, the scope, and the output flags. A flag still at the Typer default is left off, so the line is a command a reader can re-run rather than a dump of every knob. `--git-url` and `--hf` pass through `strip_url_userinfo` first.

Recording the raw `sys.argv` would keep `--preset pr` and also keep any token that was in the URL. Expanding after the preset wins means the report shows the flags that actually ran. Omitting defaults means a later RepoLens with a new default does not pretend this run set that default.
""",
    "src/repolens/cli/commands_which.py::which": """\
A frozen catalog. No model, no network, no review. The key is the scenario, lower-cased and stripped. Seven names are valid: `pr`, `changed`, `release`, `audit`, `m-and-a`, `security`, `architecture`. `m-and-a` prints the same command as `audit`. Anything else prints the valid names and exits 2.

| Scenario | Command printed | What it is |
|----------|-----------------|------------|
| `pr` | `repolens review --preset pr --path .` | Scanners only, `--no-deep`, no model. It does not add `--ci` or `--fail-on` |
| `changed` | `repolens review --preset changed --path .` | `--git-diff auto --deep`, timeout 900 |
| `release` | `repolens review --preset release --path .` | `--full --full-audit --deep`, timeout 3600 |
| `audit` | `repolens audit --path .` | Release preset plus ratchet and verify. Audit takes no `--preset` |
| `m-and-a` | `repolens audit --path .` | Same command as `audit` |
| `security` | `repolens sentinel --path .` | P1 only |
| `architecture` | `repolens architecture --path .` | P3 only. P2 stays inside review |

The command goes to stdout. `--explain` adds the one-line reason. `--json` prints `scenario`, `command`, and `why`. Looking the command up in a model would make `which` nondeterministic and would spend a model call to answer a question the project already decided. A catalog that also injected `--ci` would surprise someone who only asked which command to run.
""",
    "src/repolens/pipeline/pass_progress.py::file_work_line": """\
The count is file checks, not unique files. Each pass counts its own pack. The same 16 files in security, reliability, and architecture are 48 checks. `done` is how many of those checks already finished. `pending` is `total - done`, and it cannot go below zero. The percent is integer division, `100 * done / total`, and it cannot go above 100. Zero total is 0%, not a divide by zero.

Counting unique files would sit at 100% after the first pass, while two questions were still unwritten. Counting Fast Brain files would mix the wide rule scan with the model pack. File checks move once per finished pass, which is the unit the model actually completes.
""",
    "src/repolens/pipeline/pass_progress.py::saved_pass_rerun_line": """\
Empty when this pass has never been saved. If the saved file count and the current file count differ, the line names both counts and says the pass runs again. If the counts match, the cache key still disagreed, and the line says the saved pass does not match these files.

Reusing a 16-file answer for a 23-file pack would skip the extra files without saying so. Reusing a same-sized pack after an edit would hide the new code. Saying why, and then running the pass, is the slower honest path. The screen log is this string. The journal still records `pass_started` and, if the new pass finishes, `pass_completed`.
""",
    "src/repolens/heuristics/ci_gaps.py::find_ci_gaps": """\
Look for a package manifest by file name: `package.json`, lockfiles, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `pom.xml`, Gradle build files, and the same family. The inventory is checked first. If a cap dropped the manifest, the same names are looked up at the repo root. No manifest means no finding. A manifest with both a Dependabot file and a CodeQL workflow means no finding. Otherwise the finding names whichever of Dependabot or CodeQL is missing. CodeQL counts if any workflow file under `.github/workflows/` contains `codeql` or `github/codeql-action`, not only the four well-known filenames.

Requiring every possible CI product would flag teams that use a different scanner. Ignoring the gap would leave a dependency tree with no update bot and no code scan looking the same as a tree that has both. The rule is narrow on purpose: two GitHub-shaped signals, only when a manifest says there are dependencies. It is a low-severity hint, not a proof that CI is absent.
""",
    "src/repolens/heuristics/scripts_hygiene.py::find_script_credential_hygiene": """\
Only shell-like scripts (`.sh`, `.bash`, `.zsh`, `.ps1`) and names that contain `notarize`. A password-shaped regex (`password`, `apple id`, `notarize`, `notarytool`, and the obvious env names) must hit. A keychain-shaped regex (`keychain`, `op read`, `secret manager`, `1password`, `vault`) clears the file. Test fixtures are skipped. Markdown that discusses passwords is out of scope because it is not in the suffix list.

A secret scanner would look for a live credential value. This rule looks for a script that handles a credential and does not say where the credential comes from. Flagging every mention of the word password would light up docs and tests. Requiring a keychain mention is a heuristic, so a script that loads a secret some other safe way can still fire. The category is `heuristic.scripts_hygiene`.
""",
    "src/repolens/heuristics/scripts_hygiene.py::find_todo_density": """\
Count whole-word TODO, FIXME, XXX, and HACK markers, plus commented-out lines that look like code (`def`, `class`, `import`, `return`, and the same idea in `//` comments). The marker words are built from pieces in this file so the detector does not flag its own source. Eight or more of those hits in one file is `heuristic.todo_density`, low severity.

A single TODO is a normal note. Counting every comment would flag well-commented code. The threshold is a density signal, not a ban on task markers.
""",
}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _doc(node: ast.AST) -> str:
    raw = ast.get_docstring(node) or ""
    return textwrap.dedent(raw).strip()


def _signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.__class__.__name__
    args = []
    pos = node.args
    for arg in pos.args:
        args.append(arg.arg)
    if pos.vararg:
        args.append(f"*{pos.vararg.arg}")
    for arg in pos.kwonlyargs:
        args.append(arg.arg)
    if pos.kwarg:
        args.append(f"**{pos.kwarg.arg}")
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"


def _calls(node: ast.AST) -> list[str]:
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
    seen: list[str] = []
    for name in names:
        if name not in seen and name != getattr(node, "name", None):
            seen.append(name)
    return seen


def _branch_counts(node: ast.AST) -> dict[str, int]:
    counts = {"if": 0, "loop": 0, "try": 0, "bool": 0}
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            counts["if"] += 1
        elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
            counts["loop"] += 1
        elif isinstance(child, ast.Try):
            counts["try"] += 1
        elif isinstance(child, ast.BoolOp):
            counts["bool"] += 1
    return counts


def _span(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None) or node.lineno
    return end - node.lineno + 1


def _uses(node: ast.AST, *needles: str) -> bool:
    tokens: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            tokens.add(child.id)
        elif isinstance(child, ast.Attribute):
            tokens.add(child.attr)
    return any(needle in tokens for needle in needles)


def _pattern_note(node: ast.AST) -> str:
    notes: list[str] = []
    if _uses(node, "parse", "walk", "ast"):
        notes.append(
            "This walks a syntax tree. A regex over the source text would be shorter and would break as soon as a string or a nested block contains the same word. The tree is slower to explain and it matches the program the interpreter will actually run. The effect is Python-accuracy, and no score for a language this parser does not speak."
        )
    if _uses(node, "sha256", "hashlib"):
        notes.append(
            "The fingerprint is SHA-256. A faster hash such as xxhash would shorten a cache lookup and could collide, which would replay the wrong saved answer. SHA-256 costs a read of the file you already needed. The effect is that an edited file, a different model, or a different template misses the cache on purpose."
        )
    if _uses(node, "fcntl", "flock", "FileLock"):
        notes.append(
            "The lock is a file on disk, so a second terminal sees it. A variable inside this process would not. A network lock would need a service this tool does not run. The effect is one local model job at a time on this machine, and no coordination between two computers."
        )
    if _uses(node, "subprocess", "Popen"):
        notes.append(
            "The other program is a subprocess. Importing it into this process would share a crash and a dependency tree. A subprocess isolates that and pays a process start. The effect is that a scanner can fail without taking the review down with it."
        )
    if _uses(node, "Thread", "Lock", "Event"):
        notes.append(
            "A background thread keeps the progress line moving while the request blocks. Rewriting the command as async would touch every caller. A thread is local to this process and does not speed up the model. The effect is a heartbeat, not parallel reviews."
        )
    return "\n\n".join(notes)


_BORING_CALLS = frozenset(
    {
        "append",
        "extend",
        "update",
        "add",
        "get",
        "items",
        "keys",
        "values",
        "pop",
        "len",
        "int",
        "str",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "sorted",
        "min",
        "max",
        "range",
        "enumerate",
        "isinstance",
        "getattr",
        "hasattr",
        "setattr",
        "print",
        "join",
        "split",
        "strip",
        "lower",
        "upper",
        "replace",
        "startswith",
        "endswith",
        "format",
        "any",
        "all",
        "sum",
        "abs",
        "round",
        "type",
        "repr",
        "zip",
        "map",
        "filter",
        "next",
        "super",
    }
)


def _expr(node: ast.AST | None, limit: int = 140) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except (TypeError, ValueError):
        return "..."
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _join_names(names: list[str]) -> str:
    quoted = [f"`{name}`" for name in names]
    if len(quoted) <= 1:
        return quoted[0] if quoted else ""
    if len(quoted) == 2:
        return f"{quoted[0]} and {quoted[1]}"
    return ", ".join(quoted[:-1]) + f", and {quoted[-1]}"


def _code_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _narrate_block(stmts: list[ast.stmt], budget: list[int]) -> list[str]:
    lines: list[str] = []
    for stmt in stmts:
        if budget[0] <= 0:
            lines.append("- Further steps are in the source.")
            break
        lines.extend(_narrate_stmt(stmt, budget))
    return lines


def _narrate_stmt(stmt: ast.stmt, budget: list[int]) -> list[str]:
    if budget[0] <= 0:
        return ["- Further steps are in the source."]
    if isinstance(stmt, ast.If):
        budget[0] -= 1
        lines = [f"- When `{_expr(stmt.test)}`:"]
        lines.extend(f"  {line}" for line in _narrate_block(stmt.body, budget))
        orelse = stmt.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            nested = _narrate_stmt(orelse[0], budget)
            if nested:
                nested[0] = nested[0].replace("- When `", "- Otherwise, when `", 1)
                lines.extend(nested)
        elif orelse:
            lines.append("- Otherwise:")
            lines.extend(f"  {line}" for line in _narrate_block(orelse, budget))
        return lines
    if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        budget[0] -= 1
        if isinstance(stmt, ast.While):
            lines = [f"- While `{_expr(stmt.test)}`:"]
        else:
            lines = [f"- For each `{_expr(stmt.target)}` in `{_expr(stmt.iter)}`:"]
        lines.extend(f"  {line}" for line in _narrate_block(stmt.body, budget))
        return lines
    if isinstance(stmt, ast.With):
        budget[0] -= 1
        heads = ", ".join(
            f"`{_expr(item.context_expr)}`"
            + (f" as `{_expr(item.optional_vars)}`" if item.optional_vars else "")
            for item in stmt.items
        )
        lines = [f"- Using {heads}:"]
        lines.extend(f"  {line}" for line in _narrate_block(stmt.body, budget))
        return lines
    if isinstance(stmt, ast.Try):
        budget[0] -= 1
        lines = ["- Tries:"]
        lines.extend(f"  {line}" for line in _narrate_block(stmt.body, budget))
        for handler in stmt.handlers:
            caught = _expr(handler.type) if handler.type else "any error"
            lines.append(f"- On `{caught}`:")
            lines.extend(f"  {line}" for line in _narrate_block(handler.body, budget))
        return lines
    if isinstance(stmt, ast.Return):
        budget[0] -= 1
        if stmt.value is None:
            return ["- Returns."]
        return [f"- Returns `{_expr(stmt.value)}`."]
    if isinstance(stmt, ast.Assign) and stmt.targets:
        budget[0] -= 1
        return [f"- Sets `{_expr(stmt.targets[0])}` to `{_expr(stmt.value)}`."]
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        budget[0] -= 1
        return [f"- Sets `{_expr(stmt.target)}` to `{_expr(stmt.value)}`."]
    if isinstance(stmt, ast.AugAssign):
        budget[0] -= 1
        return [f"- Updates `{_expr(stmt.target)}` with `{_expr(stmt.value)}`."]
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        budget[0] -= 1
        return [f"- Calls `{_expr(stmt.value)}`."]
    if isinstance(stmt, ast.Continue):
        budget[0] -= 1
        return ["- Continues to the next item."]
    if isinstance(stmt, ast.Break):
        budget[0] -= 1
        return ["- Stops the loop."]
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        budget[0] -= 1
        return [f"- Defines `{stmt.name}` inside this function."]
    return []


def _nontrivial(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    counts = _branch_counts(node)
    if counts["if"] or counts["loop"] or counts["try"]:
        return True
    return len(_code_body(node)) > 3


def _link_paragraph(
    qual: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    edges: list[tuple[str, str]],
) -> str:
    callers = [src for src, dst in edges if dst == qual]
    callees = [dst for src, dst in edges if src == qual]
    callee_names = {dst.split(".")[-1] for dst in callees}
    outside: list[str] = []
    for call in _calls(node):
        if call in callee_names or call in _BORING_CALLS or call in outside:
            continue
        outside.append(call)
    parts: list[str] = []
    if callers:
        parts.append(f"{_join_names(callers)} calls this.")
    else:
        parts.append("No other function in this file calls this. Callers live in other modules.")
    if callees:
        parts.append(f"It calls {_join_names(callees)} in this file.")
    else:
        parts.append("It does not call another function defined in this file.")
    if outside[:8]:
        parts.append(f"It also uses {_join_names(outside[:8])}.")
    return " ".join(parts)


def _what_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    doc = _doc(node)
    lead = doc.split("\n\n")[0].strip() if doc else ""
    if node.name.startswith("test_"):
        claim = node.name[len("test_") :].replace("_", " ")
        calls = [call for call in _calls(node) if call not in _BORING_CALLS][:6]
        called = f" It calls {_join_names(calls)}." if calls else ""
        if lead:
            return f"Claims that {claim}.{called}\n\n{lead}"
        return f"Claims that {claim}.{called}"
    if doc:
        return doc
    return f"`{node.name}` is part of this file. The sections below are its links and its steps."


def _call_edges(defs: list[tuple[str, ast.AST]]) -> list[tuple[str, str]]:
    by_name: dict[str, list[str]] = {}
    for qual, node in defs:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            by_name.setdefault(node.name, []).append(qual)
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for qual, node in defs:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in _calls(node):
            targets = by_name.get(call, [])
            if len(targets) != 1 or targets[0] == qual:
                continue
            edge = (qual, targets[0])
            if edge not in seen:
                seen.add(edge)
                edges.append(edge)
    return edges


def _arch_title(label: str) -> str:
    return label.split(".")[-1].replace("[", "(").replace("]", ")")


def _arch_id(label: str, used: set[str]) -> str:
    raw = _mermaid_id(label.split(".")[-1], used)
    if not raw[0].isalpha():
        raw = "s" + raw
    return raw


def _architecture_preamble() -> list[str]:
    """Mermaid 11.12 architecture diagrams: groups, services, and side ports.

    Markdown Preview Mermaid Support bundles 11.12.2. `align` arrived in 11.16, so these
    diagrams leave that keyword out and stay drawable in that preview.
    """
    return ["```mermaid", "architecture-beta"]


def _component_diagram(filename: str, names: list[str]) -> str:
    """One architecture group, with no edges, when nothing here calls anything else here."""
    used: set[str] = set()
    boundary = _arch_id(Path(filename).stem or "file", used)
    shown = names[:12]
    lines = _architecture_preamble()
    lines.append(f"  group {boundary}(server)[{_arch_title(filename)}]")
    for label in shown:
        alias = _arch_id(label, used)
        lines.append(f"  service {alias}(server)[{_arch_title(label)}] in {boundary}")
    lines.append("```")
    lines.append("")
    lines.append(
        "The file is the group. These functions do not call each other, so there is no line between them. "
        "Callers outside this file pick the one they need. "
        "Open the Markdown preview to draw this. The card inside the editor uses a shorter parser."
    )
    if len(names) > len(shown):
        lines.append(
            f"The file has {len(names) - len(shown)} more function"
            f"{'' if len(names) - len(shown) == 1 else 's'} than this diagram shows. They are listed below."
        )
    return "\n".join(lines) + "\n"


def _call_tree(filename: str, names: list[str], edges: list[tuple[str, str]]) -> str:
    """One architecture group per entry point. Edges use right and left ports."""
    children: dict[str, list[str]] = {}
    parents: set[str] = set()
    for src, dst in edges:
        kids = children.setdefault(src, [])
        if dst not in kids:
            kids.append(dst)
        parents.add(dst)
    order = {name: index for index, name in enumerate(names)}
    roots = [name for name in children if name not in parents]
    roots.sort(key=lambda name: order.get(name, 10**9))
    if not roots:
        roots = sorted(children, key=lambda name: order.get(name, 10**9))

    used: set[str] = set()
    drawn = 0
    lines = _architecture_preamble()
    budget = [24]

    def walk(group: str, node: str, stack: tuple[str, ...]) -> str | None:
        nonlocal drawn
        if budget[0] <= 0:
            return None
        node_id = _arch_id(node, used)
        lines.append(f"  service {node_id}(server)[{_arch_title(node)}] in {group}")
        for child in children.get(node, []):
            if budget[0] <= 0:
                break
            if child in stack:
                back_id = _arch_id(child, used)
                lines.append(f"  service {back_id}(server)[{_arch_title(child)} again] in {group}")
                lines.append(f"  {node_id}:R --> L:{back_id}")
                budget[0] -= 1
                drawn += 1
                continue
            child_id = walk(group, child, stack + (node,))
            if child_id is None:
                break
            lines.append(f"  {node_id}:R --> L:{child_id}")
            budget[0] -= 1
            drawn += 1
        return node_id

    for index, root in enumerate(roots, start=1):
        if budget[0] <= 0:
            break
        group = f"grp{index}"
        used.add(group)
        lines.append(f"  group {group}(server)[{_arch_title(root)}]")
        walk(group, root, ())
    lines.append("```")
    lines.append("")
    lines.append(
        "Each group is one entry point. An arrow leaves the right side of a function and enters the left side of the function it calls. "
        "A name that appears in more than one group is the same function, drawn again so two callers do not share one line. "
        "Open the Markdown preview to draw this. The card inside the editor uses a shorter parser."
    )
    if drawn < len(edges):
        lines.append(f"{len(edges) - drawn} more internal calls are not drawn.")
    return "\n".join(lines) + "\n"


def _flow(filename: str, names: list[str], edges: list[tuple[str, str]]) -> str:
    if not names:
        return ""
    if not edges:
        return _component_diagram(filename, names)
    return _call_tree(filename, names, edges)


def _complex_section(node: ast.AST, key: str) -> str:
    span = _span(node)
    counts = _branch_counts(node)
    branches = counts["if"] + counts["loop"] + counts["try"]
    curated = ALGORITHMS.get(key, "")
    if span < 40 and branches < 8 and not curated:
        return ""
    lines = ["", "#### Why it is written this way", ""]
    lines.append(
        f"About {span} lines, with {counts['if']} branches, {counts['loop']} loops, "
        f"and {counts['try']} try blocks."
    )
    if curated:
        lines.append("")
        lines.append(curated.strip())
    else:
        pattern = _pattern_note(node)
        if pattern:
            lines.append("")
            lines.append(pattern)
        elif branches >= 8:
            lines.append("")
            lines.append(
                "The branches are policy: each one is a case the review treats differently. A table of rules would be easier to read when the cases are data, and worse when each case calls different code. Keeping the cases in code means a test can hit one branch without a second language for the rules."
            )
        else:
            lines.append("")
            lines.append(
                "The length is orchestration. The steps run in order so each one can be tested alone. One long script would read top to bottom once and would be harder to resume in the middle. The effect of the split is more names, and a failure that points at the step that stopped."
            )
    return "\n".join(lines)


def _mermaid_id(name: str, used: set[str]) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name) or "node"
    if base[0].isdigit():
        base = "n_" + base
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def _render_fn(
    path_key: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    qualname: str,
    edges: list[tuple[str, str]],
) -> str:
    key = f"{path_key}::{qualname}"
    title = f"`{_signature(node)}`"
    if node.name.startswith("test_"):
        return f"### {title}\n\n{_what_function(node)}\n"
    parts = [f"### {title}", "", _what_function(node), "", "#### How it links", ""]
    parts.append(_link_paragraph(qualname, node, edges))
    steps = _narrate_block(_code_body(node), [24]) if _nontrivial(node) else []
    curated = ALGORITHMS.get(key, "").strip()
    pattern = _pattern_note(node)
    if steps or curated or pattern:
        parts.extend(["", "#### The logic", ""])
        parts.extend(steps)
        if pattern:
            if steps:
                parts.append("")
            parts.append(pattern)
        if curated:
            parts.append("")
            parts.append(curated)
    return "\n".join(parts).rstrip() + "\n"


def _walk_defs(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    found: list[tuple[str, ast.AST]] = []

    def walk(nodes: list[ast.stmt], prefix: str) -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                found.append((f"{prefix}{node.name}", node))
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((f"{prefix}{node.name}", node))

    walk(getattr(tree, "body", []), "")
    return found


def _constants(tree: ast.AST) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    rows.append((target.id, f"line {node.lineno}"))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                rows.append((node.target.id, f"line {node.lineno}"))
    return rows[:20]


def _render_consts_section(tree: ast.AST) -> list[str]:
    consts = _constants(tree)
    if not consts:
        return []
    lines = ["## Names that fix a policy", "", "| Name | Where |", "|------|--------|"]
    for name, where in consts:
        lines.append(f"| `{name}` | {where} |")
    lines.extend([
        "",
        "These are the numbers and switches the rest of the file obeys. Changing one changes every caller, which is why they live at the top instead of being copied into each function.",
        "",
    ])
    return lines


def _render_defs_section(
    rel: str, defs: list[tuple[str, ast.AST]], edges: dict[str, list[str]]
) -> list[str]:
    lines = ["## What each function does", ""]
    if not defs:
        lines.append("There are no functions in this file.")
        return lines
    for qual, node in defs:
        if isinstance(node, ast.ClassDef):
            class_doc = _doc(node) or "Holds the related functions and the data they share."
            lines.extend([f"## Class `{node.name}`", "", class_doc, ""])
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(_render_fn(rel, node, qual, edges))
    return lines


def _py_note(path: Path) -> str:
    rel = _rel(path)
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (
            f"# `{rel}`\n\nThis file is not valid Python on its own ({exc}). "
            "It is a fixture or a fragment another test loads as text.\n"
        )
    doc = _doc(tree)
    defs = _walk_defs(tree)
    names = [name for name, _node in defs]
    is_test = rel.startswith("tests/")
    lines = [f"# `{rel}`", "", "## What this file does", ""]
    if doc:
        lines.append(doc)
    elif is_test:
        lines.append(
            "This file locks behaviour. Each `test_` function is one claim about the code. "
            "A claim that fails means the implementation drifted from the promise the name describes."
        )
    else:
        lines.append(
            "This module has no module docstring. The functions below are the whole of its job."
        )
    file_algo = ALGORITHMS.get(rel)
    if file_algo and "::" not in rel:
        lines.extend(["", "## The algorithm in this file", "", file_algo.strip()])
    lines.extend(["", "## How the pieces fit", ""])
    edges = _call_edges(defs)
    if names:
        lines.append(_flow(Path(rel).name, names, edges))
    else:
        lines.extend([
            "This file has no functions or classes. It carries constants, re-exports, or data.",
            "",
        ])
    lines.extend(_render_consts_section(tree))
    lines.extend(_render_defs_section(rel, defs, edges))
    if is_test:
        lines.extend(
            [
                "## How to read a test in this file",
                "",
                "The name is the claim. `test_saved_pass_is_skipped` means a saved pass is skipped. The assertions are the proof. A mock on the edge (the model, the clock, the filesystem) keeps the test about this claim rather than about the network.",
                "",
                "```mermaid",
                "flowchart LR",
                '  arrange["Arrange: a temp project or a fake model"] --> act["Act: the function under test"]',
                '  act --> proof["Assert: the claim in the name"]',
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _text_note(path: Path) -> str:
    rel = _rel(path)
    suffix = path.suffix.lower()
    if suffix == ".txt" and "plugin_locks" in rel:
        body = (
            "This is a pip requirements file with a hash on every distribution, including dependencies. "
            "Pip will refuse the install if a downloaded wheel does not match. "
            "A version pin without hashes would accept a swapped file at the same version number. "
            "The effect of the hashes is a slower, larger lockfile and a closed door on a tampered wheel. "
            "The filename says the tool, the operating system, the CPU, and CPython 3.12. "
            "A different Python does not use this file."
        )
        diagram = """```mermaid
flowchart LR
  lock["This lock file"] --> pip["pip --require-hashes"]
  pip --> ok["Wheels match"]
  pip --> no["A different hash stops the install"]
```"""
    elif suffix == ".md":
        body = (
            "This Markdown is read by the tool as instructions or as a playbook. "
            "The model sees it when that pack is selected. Editing it changes the questions the model is asked. "
            "Keeping the playbook in the repository means a review can be repeated. "
            "Generating it at runtime would be harder to audit."
        )
        diagram = """```mermaid
flowchart LR
  page["This playbook"] --> prompt["Added to the model prompt"]
  prompt --> answer["The pass writes findings against these questions"]
```"""
    elif suffix == ".json":
        body = (
            "This JSON is a schema or a manifest. Callers validate against it or read a version pin from it. "
            "Checking by hand in each caller would drift. One file means one place that says what is allowed."
        )
        diagram = """```mermaid
flowchart LR
  doc["Incoming data"] --> schema["This JSON"]
  schema --> yes["Accept"]
  schema --> no["Reject"]
```"""
    else:
        body = "This file is data the neighbouring Python loads. It is not executed on its own."
        diagram = """```mermaid
flowchart LR
  data["This file"] --> loader["The test or the tool that reads it"]
```"""
    return "\n".join(
        [
            f"# `{rel}`",
            "",
            "## What this file does",
            "",
            body,
            "",
            "## How it fits",
            "",
            diagram,
            "",
        ]
    )


def _iter_files(base: Path) -> list[Path]:
    skip = {"__pycache__", ".pytest_cache"}
    found: list[Path] = []
    if not base.exists():
        return found
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        found.append(path)
    return sorted(found)


def _index_text(title: str, files: list[Path], base: Path) -> str:
    lines = [
        f"# {title}",
        "",
        "One note per file, in the same folders as the code. Each note says what the file is for and what each function does. A long or branchy function also says why that approach was used and what a different approach would change.",
        "",
        "Regenerate after the code changes. `--check` fails when a note is stale:",
        "",
        "```bash",
        "python scripts/generate_learn_file_notes.py",
        "python scripts/generate_learn_file_notes.py --check",
        "```",
        "",
        "| Note | Code |",
        "|------|------|",
    ]
    for path in files:
        note = path.relative_to(base).with_suffix(".md").as_posix()
        lines.append(f"| [{note}]({note}) | `{_rel(path)}` |")
    lines.append("")
    return "\n".join(lines)


def _rendered_notes() -> dict[Path, str]:
    """Map each learn note path to the text the generator would write."""
    groups = [(SRC, "Source files"), (TESTS, "Test files")]
    notes: dict[Path, str] = {}
    for base, title in groups:
        files = _iter_files(base)
        for path in files:
            rel = _rel(path)
            dest = LEARN / Path(rel).with_suffix(".md")
            if path.suffix.lower() == ".py":
                notes[dest] = _py_note(path)
            else:
                notes[dest] = _text_note(path)
        notes[LEARN / base.name / "README.md"] = _index_text(title, files, base)
    return notes


def _drift(expected: dict[Path, str]) -> list[str]:
    problems: list[str] = []
    for dest, text in sorted(expected.items()):
        rel = dest.relative_to(ROOT).as_posix()
        if not dest.is_file():
            problems.append(f"missing {rel}")
            continue
        if dest.read_text(encoding="utf-8") != text:
            problems.append(f"stale {rel}")
    expected_paths = set(expected)
    for folder in (LEARN / "src", LEARN / "tests"):
        if not folder.is_dir():
            problems.append(f"missing {folder.relative_to(ROOT).as_posix()}/")
            continue
        for path in sorted(folder.rglob("*.md")):
            if path not in expected_paths:
                problems.append(f"extra {path.relative_to(ROOT).as_posix()}")
    return problems


def _write_notes(expected: dict[Path, str]) -> None:
    indexes = {LEARN / "src" / "README.md", LEARN / "tests" / "README.md"}
    counts = {"src": 0, "tests": 0}
    for dest, text in expected.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        if dest in indexes:
            continue
        top = dest.relative_to(LEARN).parts[0]
        counts[top] = counts.get(top, 0) + 1
    print(f"Source files: {counts.get('src', 0)} notes")
    print(f"Test files: {counts.get('tests', 0)} notes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if docs/learn is missing a note or does not match the tree",
    )
    args = parser.parse_args(argv)
    expected = _rendered_notes()
    if args.check:
        problems = _drift(expected)
        if problems:
            print("docs/learn is out of date with src/ and tests/.", file=sys.stderr)
            print("Regenerate: python scripts/generate_learn_file_notes.py", file=sys.stderr)
            for item in problems:
                print(item, file=sys.stderr)
            return 1
        print("learn notes match src and tests")
        return 0
    _write_notes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
