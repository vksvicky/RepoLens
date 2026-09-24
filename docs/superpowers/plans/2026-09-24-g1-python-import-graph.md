# G1 Python Import Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Always-on deterministic Python import-cycle detection via core `grimp`, emitting one `source=graph` finding per runtime SCC and treating graph findings like scanners under CI `--fail-on`.

**Architecture:** Discover top-level package names → `grimp.build_graph(*packages)` (with `src`/root on `sys.path`) → intersect edges with a stdlib AST scope/TYPE_CHECKING tag pass → Tarjan SCC on the gated edge set → one High/Critical `Issue` per SCC → sibling pipeline lane + report block. Failures become durability gaps; never crash the review.

**Tech Stack:** Python 3.11+, `grimp>=3.4,<4` (core dep), stdlib `ast`, Pydantic schema, pytest.

**Spec:** [../specs/2026-09-24-g1-python-import-graph-design.md](../specs/2026-09-24-g1-python-import-graph-design.md) · Issue [#34](https://github.com/vksvicky/RepoLens/issues/34)  
**Companion plan:** [2026-09-24-g0-fast-brain-quality.md](./2026-09-24-g0-fast-brain-quality.md)

---

## Global Constraints

- `grimp>=3.4,<4` is a **core** dependency (not an optional extra).
- British English in user-facing strings (`behaviour`, `analysed`).
- Review must not crash on SyntaxError / discovery failure — use `graph.analysis_failed: …` durability gaps.
- **Exactly one** `Issue` per runtime SCC (never one per module).
- Category `arch.import_cycle`, priority `P3`, `source="graph"`.
- Under `scanner_only=True`, `source=graph` participates in `--fail-on` like `scanner`.
- Use `grimp.build_graph(..., exclude_type_checking_imports=True)` when `type_only=ignore`; do **not** treat grimp `is_lazy` as function-local — function-local comes from our AST pass.
- Packages must be importable: temporarily prepend `root` and/or `root/src` to `sys.path` around `build_graph`.
- Dual-review gate before commit/push; TDD per task; coverage ≥ 85% on `repolens.graph`.
- Branch: `feat/g1-python-import-graph` off `main` (after specs PR #44 merges, or rebase onto it).

---

## File Map

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | Add `grimp>=3.4,<4` to `[project].dependencies` |
| `src/repolens/graph/__init__.py` | Public API: `analyse_python_graph` |
| `src/repolens/graph/types.py` | `EdgeKind`, `ImportScope`, `ImportEdge`, `CycleGroup`, `GraphResult`, `GraphStatus` |
| `src/repolens/graph/discover.py` | Package-name discovery (§6.5) |
| `src/repolens/graph/scope_tags.py` | AST: module vs function_local + TYPE_CHECKING |
| `src/repolens/graph/cycles.py` | Tarjan SCC + cyclicity ∑n² |
| `src/repolens/graph/build.py` | Orchestrate discover → grimp → tags → gated graph → SCC |
| `src/repolens/graph/findings.py` | One `Issue` per SCC |
| `src/repolens/graph/adapters.py` | `load_precomputed_edges(path)` stub |
| `src/repolens/schema.py` | `IssueSource` + optional `GraphBlock` on `FindingReport` |
| `src/repolens/config.py` | `GraphConfig` + `RepoLensConfig.graph` |
| `src/repolens/triage.py` | Infer/stamp/`fail_on_triggered` treat `graph` like scanner |
| `src/repolens/pipeline/run.py` | Sibling lane after Fast Brain heuristics |
| `src/repolens/report.py` | Markdown “Import graph” section |
| `src/repolens/metrics.py` | Treat `arch.import_cycle` / `source=graph` as architecture band (via `arch.` prefix already) |
| `.repolens.example.toml` | `[graph]` knobs |
| `tests/fixtures/graph_*` | Tiny packages: cycle, acyclic, src-layout, local-import, TYPE_CHECKING, multi-pkg |
| `tests/test_graph_*.py` | Unit/integration tests |
| `docs/faq.md`, `docs/command-atlas.md` | Always-on cycles; fail-on behaviour |

---

### Task 1: Core dependency + types

**Files:**
- Modify: `pyproject.toml`
- Create: `src/repolens/graph/__init__.py`
- Create: `src/repolens/graph/types.py`
- Create: `tests/test_graph_types.py`

**Interfaces:**
- Produces: `EdgeKind`, `ImportScope`, `ImportEdge`, `CycleGroup`, `GraphResult` dataclasses/enums

- [ ] **Step 1: Write failing test**

```python
# tests/test_graph_types.py
from repolens.graph.types import EdgeKind, GraphResult, ImportEdge, ImportScope


def test_import_edge_defaults():
    e = ImportEdge(importer="pkg.a", imported="pkg.b", kind=EdgeKind.RUNTIME, scope=ImportScope.MODULE)
    assert e.line is None
    assert e.kind is EdgeKind.RUNTIME
```

- [ ] **Step 2: Run test — expect ImportError / ModuleNotFoundError**

Run: `pytest tests/test_graph_types.py -v`

- [ ] **Step 3: Implement types + empty package init; add grimp dep**

```toml
# pyproject.toml dependencies — append:
"grimp>=3.4,<4",
```

```python
# src/repolens/graph/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum

class EdgeKind(StrEnum):
    RUNTIME = "runtime"
    TYPE_ONLY = "type_only"

class ImportScope(StrEnum):
    MODULE = "module"
    FUNCTION_LOCAL = "function_local"

class GraphStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass(frozen=True)
class ImportEdge:
    importer: str
    imported: str
    kind: EdgeKind
    scope: ImportScope
    line: int | None = None
    line_contents: str | None = None

@dataclass(frozen=True)
class CycleGroup:
    modules: tuple[str, ...]  # sorted for stability
    representative_edge: ImportEdge | None = None

@dataclass
class GraphResult:
    status: GraphStatus
    packages: list[str] = field(default_factory=list)
    edges: list[ImportEdge] = field(default_factory=list)
    gated_edges: list[ImportEdge] = field(default_factory=list)
    cycles: list[CycleGroup] = field(default_factory=list)
    cyclicity: int = 0
    module_count: int = 0
    durability_gaps: list[str] = field(default_factory=list)
```

```python
# src/repolens/graph/__init__.py
"""Deterministic Python import graph (G1 / Wave C)."""
from repolens.graph.types import CycleGroup, GraphResult, GraphStatus, ImportEdge

__all__ = ["CycleGroup", "GraphResult", "GraphStatus", "ImportEdge", "analyse_python_graph"]

def analyse_python_graph(*args, **kwargs):  # wired in Task 5
    raise NotImplementedError
```

- [ ] **Step 4: `pip install -e ".[dev]"` then pytest pass**

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/repolens/graph tests/test_graph_types.py
git commit -m "feat(graph): add grimp core dep and graph types"
```

---

### Task 2: Package discovery

**Files:**
- Create: `src/repolens/graph/discover.py`
- Create: `tests/test_graph_discover.py`
- Create fixtures under `tests/fixtures/graph_discover/`

**Interfaces:**
- Produces: `discover_packages(root: Path, *, configured: Sequence[str] | None = None) -> tuple[list[str], list[str]]` → `(packages, gaps)`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graph_discover.py
from pathlib import Path
from repolens.graph.discover import discover_packages

FIXTURES = Path(__file__).parent / "fixtures" / "graph_discover"

def test_src_layout_discovers_package(tmp_path: Path):
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("x = 1\n")
    names, gaps = discover_packages(tmp_path)
    assert names == ["mypkg"]
    assert gaps == []

def test_flat_layout(tmp_path: Path):
    pkg = tmp_path / "flatpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    names, _ = discover_packages(tmp_path)
    assert "flatpkg" in names

def test_config_override(tmp_path: Path):
    names, _ = discover_packages(tmp_path, configured=["custom"])
    assert names == ["custom"]

def test_none_found_gap(tmp_path: Path):
    names, gaps = discover_packages(tmp_path)
    assert names == []
    assert any("no packages discovered" in g for g in gaps)
```

- [ ] **Step 2: Run — expect fail (module missing)**

- [ ] **Step 3: Implement discovery order**

1. If `configured` non-empty → return those names (caller validates importability later).  
2. Try `pyproject.toml` via `tomllib`: read `[tool.setuptools.packages.find]` `where`/`include`, or hatch `[tool.hatch.build.targets.wheel.packages]`, or list `[tool.setuptools] packages`. Best-effort; ignore parse errors with a gap.  
3. Else FS: if `(root / "src").is_dir()`, each child dir of `src` with `__init__.py` or any `.py` → name; skip `_`-private and non-dirs.  
4. Else each root child dir with `__init__.py`, excluding `tests`, `docs`, `.venv`, `venv`, `node_modules`, `.git`, `build`, `dist`, `.tox`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`.  
5. Sort unique names; if empty → gap `graph.analysis_failed: no packages discovered under {root}`.

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit** `feat(graph): discover top-level package names for grimp`

---

### Task 3: AST scope tags

**Files:**
- Create: `src/repolens/graph/scope_tags.py`
- Create: `tests/test_graph_scope_tags.py`

**Interfaces:**
- Produces: `tag_file_imports(path: Path, module_name: str) -> list[TaggedImport]`  
  where `TaggedImport` has `importer`, `imported_raw`, `lineno`, `scope`, `type_only: bool`

- [ ] **Step 1: Failing tests**

```python
def test_module_level_import(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("from pkg import b\n")
    tags = tag_file_imports(p, "pkg.a")
    assert tags[0].scope == ImportScope.MODULE
    assert tags[0].type_only is False

def test_function_local(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("def f():\n    from pkg import b\n")
    tags = tag_file_imports(p, "pkg.a")
    assert tags[0].scope == ImportScope.FUNCTION_LOCAL

def test_type_checking_block(tmp_path):
    p = tmp_path / "a.py"
    p.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import b\n"
    )
    tags = tag_file_imports(p, "pkg.a")
    assert tags[0].type_only is True
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement** walk `ast.parse`; track stack of `FunctionDef`/`AsyncFunctionDef`; detect `If` tests that are `NAME=TYPE_CHECKING` or `Attribute(..., TYPE_CHECKING)`; record Import/ImportFrom. On `SyntaxError`, return `[]` (caller records gap).

- [ ] **Step 4–5: pytest pass; commit** `feat(graph): AST tag module vs function-local imports`

---

### Task 4: Tarjan SCC + cyclicity

**Files:**
- Create: `src/repolens/graph/cycles.py`
- Create: `tests/test_graph_cycles.py`

**Interfaces:**
- Produces: `strongly_connected_components(edges: Sequence[tuple[str,str]]) -> list[tuple[str, ...]]`  
  `cyclicity(sccs) -> int` (= sum of `n*n` for `|scc|>=2`, and optionally include trivial? Spec: ∑n² over SCCs — use **all** SCCs including size 1, OR only cycle groups? Roadmap says ∑n² over strongly connected components / cycle groups. **Lock:** sum `len(scc)**2` for every SCC with `len >= 2` only for the **reported cyclicity used by findings**; also expose `cyclicity_all = sum(len**2 for all sccs)` if needed. Prefer **∑ n² over SCCs with n≥2** for G1 report field to match “cycle debt”.

- [ ] **Step 1: Tests**

```python
def test_two_node_cycle():
    sccs = strongly_connected_components([("a", "b"), ("b", "a")])
    cyclic = [s for s in sccs if len(s) >= 2]
    assert len(cyclic) == 1
    assert set(cyclic[0]) == {"a", "b"}
    assert cyclicity(cyclic) == 4

def test_acyclic():
    sccs = strongly_connected_components([("a", "b"), ("b", "c")])
    assert [s for s in sccs if len(s) >= 2] == []
    assert cyclicity([]) == 0
```

- [ ] **Step 2–5: Implement Tarjan; commit** `feat(graph): Tarjan SCC and cyclicity`

---

### Task 5: build.py — grimp + gate + analyse_python_graph

**Files:**
- Create: `src/repolens/graph/build.py`
- Modify: `src/repolens/graph/__init__.py`
- Create: `tests/test_graph_build.py`
- Create fixtures: `tests/fixtures/graph_cycle_pkg/`, `graph_acyclic_pkg/`, `graph_lazy_pkg/`, `graph_typecheck_pkg/`

**Interfaces:**
- Consumes: `discover_packages`, `tag_file_imports`, `strongly_connected_components`, `cyclicity`
- Produces: `analyse_python_graph(root: Path, *, config: GraphConfig | None = None) -> GraphResult`

- [ ] **Step 1: Fixture packages** (each installable via path on `sys.path`)

`graph_cycle_pkg/packcycle/__init__.py` empty; `a.py` imports `b`; `b.py` imports `a`.

`graph_lazy_pkg/packlazy/a.py` module imports nothing; `def f(): from packlazy import b`; `b.py` imports `a` at module level — cycle only if local included.

`graph_typecheck_pkg/`: mutual imports only under `TYPE_CHECKING`.

- [ ] **Step 2: Failing integration tests**

```python
def test_detects_runtime_cycle():
    root = FIXTURES / "graph_cycle_pkg"
    result = analyse_python_graph(root)
    assert result.status in {GraphStatus.OK, GraphStatus.PARTIAL}
    assert len(result.cycles) == 1
    assert result.cyclicity >= 4

def test_excludes_function_local_by_default():
    root = FIXTURES / "graph_lazy_pkg"
    result = analyse_python_graph(root)  # local_imports=exclude
    assert result.cycles == []

def test_type_checking_ignored():
    root = FIXTURES / "graph_typecheck_pkg"
    result = analyse_python_graph(root)
    assert result.cycles == []
```

- [ ] **Step 3: Implement `build.py`**

Pseudocode contract:

```python
def analyse_python_graph(root: Path, *, config: GraphConfig | None = None) -> GraphResult:
    cfg = config or GraphConfig()
    if not cfg.enabled:
        return GraphResult(status=GraphStatus.SKIPPED, durability_gaps=["graph: disabled"])
    packages, gaps = discover_packages(root, configured=cfg.packages or None)
    if not packages:
        return GraphResult(status=GraphStatus.FAILED, durability_gaps=gaps)
    path_extra = [str(root / "src")] if (root / "src").is_dir() else []
    path_extra.append(str(root))
    # prepend path_extra to sys.path; try/finally restore
    try:
        import grimp
        graph = grimp.build_graph(
            *packages,
            exclude_type_checking_imports=(cfg.type_only == "ignore"),
            cache_dir=None,  # deterministic tests; or root/".repolens/grimp-cache"
        )
    except Exception as exc:
        return GraphResult(
            status=GraphStatus.FAILED,
            packages=packages,
            durability_gaps=gaps + [f"graph.analysis_failed: {exc}"],
        )
    # Collect edges via modules + find_modules_directly_imported_by
    # For each edge, get_import_details for line_number
    # Map module→file path under root; run tag_file_imports; intersect scopes
    # Filter gated_edges by type_only / local_imports
    # SCC on gated_edges; build CycleGroup with representative_edge
    ...
```

Intersect rule (spec): edge is `function_local` only if **all** supporting statements for that pair are function-local; else `module` if any module-level exists.

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit** `feat(graph): analyse_python_graph via grimp and gated SCCs`

---

### Task 6: Findings — one Issue per SCC

**Files:**
- Create: `src/repolens/graph/findings.py`
- Create: `tests/test_graph_findings.py`

**Interfaces:**
- Produces: `cycles_to_issues(result: GraphResult, *, critical_scc_size: int = 8) -> list[Issue]`

- [ ] **Step 1: Test — 6-module SCC yields exactly one Issue**

```python
def test_one_finding_per_scc():
    modules = tuple(f"m{i}" for i in range(6))
    edge = ImportEdge("m5", "m0", EdgeKind.RUNTIME, ImportScope.MODULE, line=1, line_contents="import m0")
    result = GraphResult(
        status=GraphStatus.OK,
        cycles=[CycleGroup(modules=modules, representative_edge=edge)],
        cyclicity=36,
    )
    issues = cycles_to_issues(result)
    assert len(issues) == 1
    assert issues[0].source == "graph"
    assert issues[0].severity == Severity.HIGH
    assert issues[0].category == "arch.import_cycle"
    assert issues[0].priority == "P3"
    assert "6 modules" in issues[0].title
    assert issues[0].impact.strip()
    assert issues[0].codeExample.strip()

def test_large_scc_critical():
    modules = tuple(f"m{i}" for i in range(8))
    result = GraphResult(
        status=GraphStatus.OK,
        cycles=[CycleGroup(modules=modules)],
        cyclicity=64,
    )
    assert cycles_to_issues(result)[0].severity == Severity.CRITICAL
```

- [ ] **Step 2–5: Implement title/explanation/codeExample; commit** `feat(graph): emit one finding per SCC`

---

### Task 7: Schema, config, triage fail-on

**Files:**
- Modify: `src/repolens/schema.py`
- Modify: `src/repolens/config.py`
- Modify: `src/repolens/triage.py`
- Modify: `tests/test_triage.py` (or create `tests/test_graph_fail_on.py`)

**Interfaces:**
- `IssueSource = Literal["scanner", "heuristic", "llm", "graph"]`
- `GraphBlock` on `FindingReport`
- `GraphConfig` on `RepoLensConfig`
- `fail_on_triggered(..., scanner_only=True)` returns True for graph High

- [ ] **Step 1: Failing fail-on test**

```python
def test_fail_on_graph_counts_when_scanner_only():
    issue = Issue(
        severity=Severity.HIGH,
        priority="P3",
        category="arch.import_cycle",
        file="a.py",
        line=1,
        title="cycle",
        explanation="x",
        impact="breaks layering",
        recommendedFix="extract interface",
        codeExample="import b",
        source="graph",
    )
    report = FindingReport(confidence=80, summary=Summary(high=1), issues=[issue])
    assert fail_on_triggered(report, "HIGH", scanner_only=True) is True
```

- [ ] **Step 2: Schema + GraphConfig**

```python
class GraphConfig(BaseModel):
    enabled: bool = True
    type_only: Literal["ignore", "warn"] = "ignore"
    local_imports: Literal["exclude", "include"] = "exclude"
    critical_scc_size: int = 8
    packages: list[str] = Field(default_factory=list)

class GraphBlock(BaseModel):
    status: str
    cyclicity: int = 0
    cycleCount: int = 0
    moduleCount: int = 0
    packageCount: int = 0
```

Wire `RepoLensConfig.graph`, `FindingReport.graph: GraphBlock | None = None`.

Update `infer_issue_source` / `stamp_issue_sources` to accept `"graph"`.  
Update `fail_on_triggered`:

```python
if scanner_only:
    src = infer_issue_source(issue)
    if src not in {"scanner", "graph"}:
        continue
```

- [ ] **Step 3–5: pytest; commit** `feat(graph): schema source=graph and CI fail-on parity`

---

### Task 8: Pipeline + report + example config

**Files:**
- Modify: `src/repolens/pipeline/run.py` (after heuristics ~L321)
- Modify: `src/repolens/report.py`
- Modify: `.repolens.example.toml`
- Create: `tests/test_graph_pipeline.py` (light: call analyse + merge path with monkeypatch if needed)

- [ ] **Step 1: After `heur_result = run_heuristics(...)`**

```python
graph_issues: list[Issue] = []
graph_block = None
graph_gaps: list[str] = []
if any(Path(f.relative).suffix == ".py" for f in fast_files):
    from repolens.graph import analyse_python_graph
    from repolens.graph.findings import cycles_to_issues
    from repolens.schema import GraphBlock
    gres = analyse_python_graph(root, config=cfg.graph)
    graph_gaps = list(gres.durability_gaps)
    graph_issues = cycles_to_issues(gres, critical_scc_size=cfg.graph.critical_scc_size)
    graph_block = GraphBlock(
        status=gres.status.value,
        cyclicity=gres.cyclicity,
        cycleCount=len(gres.cycles),
        moduleCount=gres.module_count,
        packageCount=len(gres.packages),
    )
# Merge graph_issues into report.issues alongside heur_issues everywhere scanners_only / LLM paths build issues
# Append graph_gaps to durabilityGaps
# Set report.graph = graph_block
```

- [ ] **Step 2: Markdown section** `_render_import_graph_section` after supply chain / before themes:

```markdown
## Import graph

| Metric | Value |
|--------|------:|
| Status | ok |
| Packages | 1 |
| Modules | 42 |
| Cycle groups | 1 |
| Cyclicity | 4 |

_Deterministic Python import cycles (grimp) — not an architecture certification._
```

- [ ] **Step 3: `.repolens.example.toml` `[graph]` block per spec**

- [ ] **Step 4: pytest subset + `pytest tests/test_graph_*.py -q`**

- [ ] **Step 5: Commit** `feat(graph): wire import-graph lane into review pipeline`

---

### Task 9: Adapter stub + docs + coverage

**Files:**
- Create: `src/repolens/graph/adapters.py`
- Create: `tests/test_graph_adapters.py`
- Modify: `docs/faq.md`, `docs/command-atlas.md`
- Run: `pytest --cov=repolens.graph --cov-report=term-missing`

- [ ] **Step 1: `load_precomputed_edges(path: Path) -> GraphResult`** reads JSON list of `{importer, imported, kind?, scope?, line?}`; runs SCC; no grimp.

- [ ] **Step 2: FAQ bullets** — always-on for Python; idle on non-Python; package discovery; MCP not in G1; graph fail-on like scanners.

- [ ] **Step 3: Coverage ≥ 85% on `repolens.graph`; dogfood `repolens review --path . --scanners-only` (or unit only if dogfood slow)

- [ ] **Step 4: Commit** `docs(graph): FAQ + precomputed edge adapter stub`

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| grimp core dep | 1 |
| Package discovery §6.5 | 2 |
| AST local-import tags §6.1 | 3 |
| TYPE_CHECKING via grimp flag + tags | 5 |
| Tarjan / cyclicity | 4 |
| analyse_python_graph durability | 5 |
| One finding per SCC | 6 |
| source=graph + fail-on | 7 |
| Pipeline sibling lane + report | 8 |
| Adapter stub | 9 |
| Docs | 9 |

## Placeholder scan

None intentional — fixtures paths and GraphConfig fields are named above.
