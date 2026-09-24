# G1 — Deterministic Python import graph (design)

**Status:** Approved for plan (rev 2) · Plan: [../plans/2026-09-24-g1-python-import-graph.md](../plans/2026-09-24-g1-python-import-graph.md)  
**Date:** 2026-09-24  
**Issue:** [#34](https://github.com/vksvicky/RepoLens/issues/34) (anchor track)  
**Umbrella:** [#18](https://github.com/vksvicky/RepoLens/issues/18) · [zugel-comparison-and-roadmap.md](../../design/zugel-comparison-and-roadmap.md)  
**Companion:** [#33](https://github.com/vksvicky/RepoLens/issues/33) / [G0 spec](./2026-09-24-g0-fast-brain-quality-design.md)  
**Blocks:** G2 ratchet (#35), G3 MCP (#36)

---

## 1. Problem

LLM-only P3 architecture reviews lack deterministic structural teeth. Wave C / Zügel ordering requires a **live Python import graph + cycle detection** before MCP or DSL. A naive stdlib-`ast` resolver is a known trap (relative imports, lazy imports, name collisions, `TYPE_CHECKING` aliases).

## 2. Goals

1. **FR1 — Always-on resolver:** `grimp` is a **core** dependency of `repolens-audit`. After `pipx install repolens-audit`, `repolens review` on a Python repo reports runtime cycles on day one.
2. **FR2 — Thin wrapper:** All grimp use lives behind `repolens.graph.*`. Malformed files / analysis failures append durability gaps (`graph.analysis_failed: …`) and **must not crash** the review run.
3. **FR3 — Edge tags:** Each internal edge is `runtime` or `type_only`. Function-local imports are excluded from hard cycle gates by default (configurable) via an explicit tagging pass (§6.1).
4. **FR4 — SCC / cycles:** Tarjan (or equivalent) SCCs; machine-readable cycle list; cyclicity ∑*n²* computed and available for reports (G2 persists it later).
5. **FR5 — Findings:** **Exactly one** `source="graph"` finding **per runtime SCC** (not per module). Severity High (Critical for large SCCs — §6.2).
6. **FR6 — Gate honesty:** `--fail-on` with CI `scanner_only` still treats **`graph` like `scanner`** (structural teeth must fail CI). Heuristic/LLM remain excluded under `scanner_only`.
7. **FR7 — Adapter stub:** `load_edge_list(path)` (or equivalent) for future Sonargraph/SCIP ingest — no production consumers required in G1.
8. **FR8 — Package discovery:** Infer top-level package names for `grimp.build_graph(*packages)` (§6.5); optional config override.

## 3. Non-goals

* Hand-rolled Python path resolution as the primary engine  
* Polyglot (TS/Go/Rust) resolution in core  
* MCP tools / `check_proposed_dependency`  
* Baseline ratchet / `repolens baseline set` (G2)  
* Architecture DSL / FAS remediation prompts (G4)  
* Claiming “architecture certified” from cycles alone  

## 4. Dependency & packaging

```toml
# pyproject.toml [project] dependencies — add:
"grimp>=3.4,<4",
```

| Fact | Value |
|------|--------|
| Licence | BSD-2-Clause (compatible) |
| Footprint | ~300 KB wheel; idle on non-Python targets |
| Why core | Optional `[graph]` → silent skip or false CI pass; defeats Wave C credibility |

## 5. Architecture

```text
inventory (Python .py files)
        │
        ▼
discover_packages(root, config)     ──► package name list
        │
        ▼
repolens.graph.build (grimp + AST tag pass)
        │
        ├── edges: (from, to, kind, scope, line?)
        ├── sccs / cycles  (hard gate uses runtime ∪ included scopes only)
        ├── cyclicity
        └── durability_gaps[]
        │
        ▼
findings: **1 Issue per runtime SCC** + optional report.graph block
        │
        ▼
existing report / SARIF / --fail-on pipeline
```

### Module layout (proposed)

| Module | Responsibility |
|--------|----------------|
| `src/repolens/graph/__init__.py` | Public API: `analyse_python_graph`, types |
| `src/repolens/graph/types.py` | `EdgeKind`, `ImportScope`, `ImportEdge`, `CycleGroup`, `GraphResult` |
| `src/repolens/graph/discover.py` | Package-name discovery heuristic (§6.5) |
| `src/repolens/graph/build.py` | Invoke grimp; merge AST scope tags; map to our types; catch failures |
| `src/repolens/graph/scope_tags.py` | Lightweight stdlib `ast` pass: module-level vs function-local imports |
| `src/repolens/graph/cycles.py` | SCC / cyclicity on the **gated** edge set |
| `src/repolens/graph/findings.py` | `GraphResult` → **one `Issue` per SCC** |
| `src/repolens/graph/adapters.py` | `load_precomputed_edges(path) → GraphResult` stub |

Pipeline hook: run as a **sibling deterministic lane** beside Fast Brain heuristics (not inside the “regex-only Fast Brain” contract from Phase 6.11). Wire from `pipeline/run.py` when matched inventory contains `.py`; skip silently (no durability gap) when zero `.py` matched. Do not fold grimp into `heuristics/runner.py`.

## 6. Behaviour details

### 6.1 Edge kinds & import scope (how local imports are detected)

| Attribute | Values | Hard cycle gate? |
|-----------|--------|------------------|
| `kind` | `runtime` \| `type_only` | Only `runtime` (unless `type_only=warn` emits soft findings) |
| `scope` | `module` \| `function_local` | `function_local` excluded when `local_imports=exclude` (default) |

**Grimp limitation (explicit):** `grimp.build_graph` builds an `ImportGraph` of module→module edges and does **not** reliably expose whether each import statement lived inside a `def` / `async def` vs module top-level. RepoLens therefore:

1. Call grimp for **resolved** internal edges (path / relative / package mechanics).  
2. Run a **lightweight stdlib AST pass** (`scope_tags.py`) over each analysed `.py` file to record `(importer_module, imported_module, lineno, scope)` for every `ast.Import` / `ast.ImportFrom`.  
3. **Intersect:** tag each grimp edge with `scope=function_local` if **all** supporting import statements for that pair are function-local; otherwise `scope=module` if any module-level statement exists.  
4. Tag `kind=type_only` when the import sits under a recognised `TYPE_CHECKING` guard (including common aliases — best-effort; document gaps).  
5. Build the **gated graph** for SCC/cyclicity from edges that survive config filters (`type_only`, `local_imports`).

If AST parse fails for a file, keep grimp edges for that module as `scope=module` (conservative) and append `graph.analysis_failed: …` — do not drop the whole run.

### 6.2 Findings — **exactly one per SCC**

A single SCC of *n* modules must **not** emit *n* High findings (that would burn the metrics High-penalty cap, e.g. −50, as if *n* separate bugs existed).

**Locked rule:**

* **One `Issue` per runtime SCC** with size ≥ 2.  
* `title`: e.g. `Cyclic dependency group: 6 modules (a, b, c, …)` (truncate module list in title; full list in explanation).  
* `explanation`: full cycle chain / membership (sorted for stability).  
* `file` / `line`: representative **closing** edge’s import site when known; else first module’s file.  
* `codeExample`: the representative closing import (or a minimal cycle sketch).  
* `impact` + `codeExample` required for High/Critical (existing schema).  
* Severity: SCC size ≥ 2 → **HIGH**; SCC size ≥ 8 → **CRITICAL** (tunable constant `critical_scc_size`).

Optional `clusteredCount` may mirror SCC module count for report UX; still **one** issue row.

### 6.3 Fail-on / triage

Update `IssueSource` and `infer_issue_source` / `fail_on_triggered`:

```text
IssueSource = "scanner" | "heuristic" | "llm" | "graph"
```

When `scanner_only=True`, treat `source == "graph"` the same as `"scanner"` for gate purposes.

### 6.4 Durability gaps (non-fatal)

Examples:

* `graph.analysis_failed: SyntaxError in src/foo.py — skipped file`  
* `graph.analysis_failed: no packages discovered under …`  
* `graph.partial: N files skipped`

Review continues; confidence / provenance may note partial graph.

### 6.5 Package root discovery

`grimp.build_graph` expects **top-level package names** (e.g. `grimp.build_graph("repolens", …)`), not an arbitrary filesystem directory. Discovery lives in `discover.py`:

**Order (stop when packages non-empty, unless config forces more):**

1. **Config override:** `[graph] packages = ["repolens", …]` or `package_roots` mapped to import names — if set, use exactly these names (after validating they import under `root`).  
2. **Packaging metadata:** parse `pyproject.toml` (`[project] name` is **not** enough — prefer `[tool.setuptools.packages.find]`, hatch/poetry package tables, or `setup.cfg` `[options] packages` / `package_dir`) for declared packages.  
3. **Filesystem fallback:**  
   * If `src/` exists: each immediate child dir of `src/` that contains `__init__.py` or is a PEP 420 namespace with `.py` files → package name = dir name. Also accept a single flat module `src/foo.py` as package/module `foo` if grimp accepts it.  
   * Else at repo root: each immediate child dir with `__init__.py` (or namespace + `.py`) that is not a known non-package (`tests`, `docs`, `.venv`, `node_modules`, …).  
4. **Multi-package:** if inference finds multiple packages, call `grimp.build_graph(*packages)` with **all** of them (same import roots / sys.path setup as grimp docs recommend for the repo).  
5. **None found:** durability gap `graph.analysis_failed: no packages discovered`; zero graph findings; review continues.

Document that pure script folders without importable package layout may yield empty graphs — that is expected, not a crash.

### 6.6 Config (`.repolens.toml`)

```toml
[graph]
enabled = true                 # default true; false skips analysis (durability note)
type_only = "ignore"           # ignore | warn
local_imports = "exclude"      # exclude | include  (see §6.1 AST tag pass)
critical_scc_size = 8
# packages = ["repolens"]      # optional override; skips/augments discovery per §6.5
```

## 7. Report surface

* Issues as §6.2.  
* Optional `FindingReport.graph`: `{ cyclicity, cycleCount, moduleCount, packageCount, status }`.  
* Markdown: short “Import graph” subsection when `status=ok` or when cycles found.  
* Provenance note: `graphEngine=grimp` (version optional).

## 8. Testing (Right-BICEP)

| Case | Expect |
|------|--------|
| Right | Two-module cycle → **exactly one** High `source=graph` finding; cyclicity ≥ 4 |
| Boundary | Empty repo / no `.py` → no graph findings, no crash |
| Inverse | Acyclic package → zero runtime cycle findings |
| Cross-check | Same fixtures via `load_precomputed_edges` produce same SCCs |
| Error | Broken syntax file → durability gap; sibling modules still analysed |
| Perf | Small fixture (<50 modules) finishes in seconds in unit tests |
| Edge | `TYPE_CHECKING` only cycle → no hard finding when `type_only=ignore` |
| Edge | Function-local import closing a cycle → edge excluded when `local_imports=exclude`; included when `include` |
| Edge | `src/` layout + flat layout fixtures both discover packages |
| Edge | 6-module SCC → **1** finding (not 6); metrics High penalty counts once |
| Gate | `--fail-on HIGH` + `scanner_only` **does** fail on graph High |
| Discovery | Multi-package fixture → `build_graph` receives all package names |

## 9. Docs

* FAQ: Python cycle detection always-on; grimp; package discovery; non-Python repos idle.  
* Command atlas: graph subsection / fail-on behaviour.  
* Explicit: MCP not in G1; CLI is the gate.

## 10. Success criteria

- [ ] `grimp` in core deps; install works without extras  
- [ ] Discovery covers src/ + flat + multi-package fixtures  
- [ ] Local-import exclude proven by AST tag tests  
- [ ] One finding per SCC enforced in tests  
- [ ] Dogfood on RepoLens itself surfaces/none cycles honestly  
- [ ] Unit tests green; coverage ≥ 85% on `repolens.graph`  
- [ ] Review never crashes on bad Python files  

---

## Open points deferred to G2/G4

* Baseline file format under `.repolens/`  
* Diff-anchored import line in PR annotations  
* FAS candidate cuts + hexagonal prompt (G4)
