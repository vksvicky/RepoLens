# G1 — Deterministic Python import graph (design)

**Status:** Draft for review  
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
3. **FR3 — Edge tags:** Each internal edge is `runtime` or `type_only`. Function-local imports are excluded from hard Critical cycles by default (configurable).
4. **FR4 — SCC / cycles:** Tarjan (or equivalent) SCCs; machine-readable cycle list; cyclicity ∑*n²* computed and available for reports (G2 persists it later).
5. **FR5 — Findings:** Runtime cycle findings use `source="graph"`, severity High (Critical only for large SCCs — see §6), with file:line on a representative import when available.
6. **FR6 — Gate honesty:** `--fail-on` with CI `scanner_only` still treats **`graph` like `scanner`** (structural teeth must fail CI). Heuristic/LLM remain excluded under `scanner_only`.
7. **FR7 — Adapter stub:** `load_edge_list(path)` (or equivalent) for future Sonargraph/SCIP ingest — no production consumers required in G1.

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
repolens.graph.build_graph(root, config)  ──► grimp (internal)
        │
        ├── edges: (from, to, kind, line?)
        ├── sccs / cycles
        ├── cyclicity
        └── durability_gaps[]
        │
        ▼
findings (source=graph) + optional report.graph block
        │
        ▼
existing report / SARIF / --fail-on pipeline
```

### Module layout (proposed)

| Module | Responsibility |
|--------|----------------|
| `src/repolens/graph/__init__.py` | Public API: `analyse_python_graph`, types |
| `src/repolens/graph/types.py` | `EdgeKind`, `ImportEdge`, `CycleGroup`, `GraphResult` |
| `src/repolens/graph/build.py` | Invoke grimp; map to our types; catch/analyse failures |
| `src/repolens/graph/cycles.py` | SCC / cyclicity (stdlib or small pure impl) |
| `src/repolens/graph/findings.py` | `GraphResult` → `list[Issue]` |
| `src/repolens/graph/adapters.py` | `load_precomputed_edges(path) → GraphResult` stub |

Pipeline hook: run as a **sibling deterministic lane** beside Fast Brain heuristics (not inside the “regex-only Fast Brain” contract from Phase 6.11). Wire from `pipeline/run.py` when matched inventory contains `.py`; skip silently (no durability gap) when zero `.py` matched. Do not fold grimp into `heuristics/runner.py` — keep `repolens.graph` separable for G2 ratchet and future adapters.

## 6. Behaviour details

### 6.1 Edge kinds

| Kind | Included in hard cycle gate? | Default |
|------|------------------------------|---------|
| `runtime` (module-level) | Yes | — |
| `type_only` (`TYPE_CHECKING` / equivalent) | No | Config: `ignore` \| `warn` (warn → Low/Medium finding, not gate Critical) |
| Function-local / lazy | No (hard gate) | Config: `exclude` (default) \| `include` |

### 6.2 Severity

* Runtime SCC size ≥ 2 → at least **HIGH** finding(s) (one per SCC or one clustered finding with cycle path in explanation).  
* Very large SCC (e.g. ≥ 8 modules) → **CRITICAL** (tunable constant).  
* Critical/High must satisfy existing schema: non-empty `impact` + `codeExample`.

### 6.3 Fail-on / triage

Update `IssueSource` and `infer_issue_source` / `fail_on_triggered`:

```text
IssueSource = "scanner" | "heuristic" | "llm" | "graph"
```

When `scanner_only=True`, treat `source == "graph"` the same as `"scanner"` for gate purposes.

### 6.4 Durability gaps (non-fatal)

Examples:

* `graph.analysis_failed: SyntaxError in src/foo.py — skipped file`  
* `graph.analysis_failed: grimp could not resolve package root under …`  
* `graph.partial: N files skipped`

Review continues; confidence / provenance may note partial graph.

### 6.5 Config (`.repolens.toml`)

```toml
[graph]
enabled = true                 # default true; false skips analysis (durability note)
type_only = "ignore"           # ignore | warn
local_imports = "exclude"      # exclude | include
# package_roots = []           # optional override; else infer from layout / grimp
```

## 7. Report surface

* Issues as above.  
* Optional `FindingReport` extension (backward compatible): e.g. `graph: { cyclicity, cycleCount, moduleCount, status }` — keep small; G2 will persist baseline separately under `.repolens/`.  
* Markdown: short “Import graph” subsection when `status=ok` or when cycles found.  
* Provenance note: `graphEngine=grimp` (version optional).

## 8. Testing (Right-BICEP)

| Case | Expect |
|------|--------|
| Right | Two-module cycle → High `source=graph` finding; cyclicity ≥ 4 |
| Boundary | Empty repo / no `.py` → no graph findings, no crash |
| Inverse | Acyclic package → zero runtime cycle findings |
| Cross-check | Same fixtures via `load_precomputed_edges` produce same SCCs |
| Error | Broken syntax file → durability gap; sibling modules still analysed |
| Perf | Small fixture (<50 modules) finishes in seconds in unit tests |
| Edge | `TYPE_CHECKING` only cycle → no hard finding when `type_only=ignore` |
| Edge | Function-local import closing a cycle → no Critical when `local_imports=exclude` |
| Gate | `--fail-on HIGH` + `scanner_only` **does** fail on graph High |

## 9. Docs

* FAQ: Python cycle detection always-on; grimp; non-Python repos idle.  
* Update #34 AC (done).  
* Command atlas: mention graph subsection / fail-on behaviour.  
* Explicit: MCP not in G1; CLI is the gate.

## 10. Success criteria

- [ ] `grimp` in core deps; install works without extras  
- [ ] Dogfood on RepoLens itself or a tiny fixture package surfaces/none cycles honestly  
- [ ] Unit tests green; coverage ≥ 85% on `repolens.graph`  
- [ ] Review never crashes on bad Python files  
- [ ] Spec non-goals respected (no MCP, no ratchet persistence)

---

## Open points deferred to G2/G4

* Baseline file format under `.repolens/`  
* Diff-anchored import line in PR annotations  
* FAS candidate cuts + hexagonal prompt (G4)
