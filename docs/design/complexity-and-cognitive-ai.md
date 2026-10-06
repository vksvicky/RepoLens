# Complexity metrics & AI-assisted refactoring

**Audience:** maintainers / contributors / advanced users  
**Date:** 2026-09-27  
**Status:** Approved design (MVP → v1 → v2) — implementation tracked via plan issues  
**Related:** [competitive-landscape-sonar-alternatives-2026.md](./competitive-landscape-sonar-alternatives-2026.md) · [zugel-comparison-and-roadmap.md](./zugel-comparison-and-roadmap.md) · [faq.md](../faq.md) · [phases.md](../phases.md)

---

## 1. Bottom line

RepoLens will ship **first-party cyclomatic (McCabe) and cognitive complexity** as Fast Brain metrics, plus **local or BYOK AI** that explains the worst functions and suggests concrete refactors. Separately, it will report **whether tests exist**, optionally ingest **line/branch coverage artifacts**, and use AI to flag **Right-BICEP / happy-negative-exception scenario gaps** — without reimplementing coverage.py or mutation engines.

| We ship | We refuse |
|---------|-----------|
| Deterministic McCabe + cognitive scores per function | SonarQube / Qodana **server**, Postgres, auth, portfolio UI |
| Scorecard aggregates + thresholded Issues | Multi-tenant ASPM portal |
| Top-N AI explanations (default **5**, max **10**) | Sending hundreds of functions to the LLM |
| Python MVP via **stdlib `ast`** (zero new deps) | Bundling tree-sitter in the base install |
| Optional `repolens-audit[complexity]` for JS/TS/Java/… | 500 idiosyncratic OOP lint rules / quality-profile clone |
| Markdown always renders **Top-10** complexity hotspots | LLM detail only for top-5 (configurable, max 10) |
| Test inventory: **files + test cases** (Python `ast`) | File-only ratios that scare without signal |
| Right-BICEP AI: focus **B / E / Negative** | Speculative **P** (performance) lectures without a profiler |
| Coverage(func) = \|executed ∩ [start,end]\| / \|executable ∈ [start,end]\| | Reimplementing coverage.py |
| High-risk uncovered: cognitive > 15 **and** Coverage(func) < 50% | Flagging every partially covered function |
| Categories: `quality.complexity`, `testing.missing_tests`, `testing.scenario_gap` | Orphan findings outside themes |

**Deterministic metrics + local/BYOK AI refactoring ≠ a Sonar server clone.**

This preserves the RepoLens wedge: **zero infrastructure**, local-first, private BYOK — see the [competitive landscape](./competitive-landscape-sonar-alternatives-2026.md).

---

## 2. Why these two metrics

Developers and architects care about:

1. **Cyclomatic complexity (McCabe)** — branching density / independent paths (testability signal).
2. **Cognitive complexity** — mental effort to read (nesting and breaks in linear flow).

Nesting indent heuristics and mega-files remain cheap proxies; they do **not** replace these metrics.

### Cognitive complexity — behavioural target

Implementation follows the **published** algorithm described in:

- G. Ann Campbell, *Cognitive Complexity: A new way of measuring understandability* (SonarSource whitepaper, **2016**).

That paper is an open specification used across OSS (e.g. ideas shared with radon, eslint-plugin-sonarjs, gocyclo-style tooling). RepoLens implements the **behaviour** (nesting increments, break-in-flow rules) from the public description — **not** proprietary SonarQube product code or quality profiles.

---

## 3. Architecture

```
Inventory
   → Language adapters measure EVERY function (cyclo + cognitive)
   → Test inventory (layout heuristics) + optional --import-coverage
   → Scorecard: p95, max, band counts, top-N hotspots, test counts/ratio, coverage % if imported
   → Issues: ONLY when complexity thresholds or “hot code / no tests” rules trip
   → Optional ML rank ([ml] default off)
   → Slow Brain: ONLY top_n (complexity refactor and/or BICEP scenario gaps)
   → Report / SARIF export
   → (v1) Optional complexity ratchet vs baseline
```

| Layer | Responsibility |
|-------|----------------|
| **Fast Brain** | All-function metrics; test layout inventory; threshold → Issue; scorecard |
| **Coverage import** | Ingest coverage.py / LCOV / JaCoCo artifacts the user already produced |
| **Slow Brain** | Explain + refactor sketches **or** missing scenario tests for top-N (Ollama or BYOK) |
| **ML (opt-in)** | Embeddings for near-clone / triage ranking — never invents scores or coverage % |
| **SARIF import** | Companion path for Ruff/ESLint/radon/Sonar exports forever |

---

## 4. Thresholds & severity (defaults)

Configurable under `[complexity]`; defaults are product-normative so a large repo does not issue-spam.

### Cyclomatic (McCabe)

| Score | Band | Issue |
|------:|------|-------|
| ≤ 10 | Clean | Scorecard only |
| 11–20 | Moderate | MEDIUM / P2 |
| 21–50 | High risk | HIGH / P1 |
| > 50 | Untestable monster | CRITICAL / P1 |

### Cognitive (Sonar-behavioural)

| Score | Band | Issue |
|------:|------|-------|
| ≤ 15 | Clean | Scorecard only |
| 16–25 | High mental load | MEDIUM / P2 |
| > 25 | Severe overload | HIGH / P1 |

If both metrics trip, emit **one** Issue (worst severity; both numbers in the explanation).

---

## 5. AI cost cap & report visibility

Legacy codebases may have hundreds of complex functions.

| Rule | Value |
|------|-------|
| Fast Brain coverage | **All** functions in inventory scope |
| Markdown **Top complexity hotspots** table | Always **Top 10** (File, Function, Line, Cyclomatic, Cognitive) — zero LLM cost |
| Slow Brain explanations / refactor `codeExample` | **`top_n_ai_explanations = 5`** (configurable, hard max **10**) |
| Ranking | Cognitive ↓, then cyclomatic ↓, then span |

AI must not invent metric numbers; it narrates evidence already computed.

Providers: existing RepoLens stack — **Ollama (local)** or **BYOK** (Gemini / Vertex / Bedrock / OpenAI-compatible). No RepoLens-hosted model.

---

## 6. Parser & packaging strategy

| Language | When | Mechanism | Install |
|----------|------|-----------|---------|
| Python | **MVP** | stdlib `ast` / `NodeVisitor` | Base `repolens-audit` |
| JS/TS, Java | **v1** | tree-sitter | `pip install "repolens-audit[graph]"` (no separate `[complexity]` extra; #95 slice covers JS/TS, not Java) |
| Go, Rust, C# | **#95** | tree-sitter | same `[graph]` extra |
| Ruby, Java, … | **later** | tree-sitter | same extra when unparked |

Missing extras → skip non-Python languages with a durability note; Python path still runs.

---

## 7. Phasing

| Phase | Deliverables | CI gate |
|-------|--------------|---------|
| **MVP** | Python cyclo + cognitive; thresholds; scorecard; Issues above band; top-5 Slow Brain explain/refactor; **test inventory**; Right-BICEP playbook on top-N; FAQ/README | **No** complexity ratchet |
| **v1** | JS/TS + Java via `[complexity]`; `repolens explain` on complexity UUIDs; SARIF dedupe; **`--import-coverage`** + recipes; uncovered×complex Issues; **optional** complexity ratchet | Opt-in ratchet |
| **v2** | More languages; `[ml]` opt-in Ollama embeddings; mutation-companion docs (mutmut/Stryker) | Unchanged unless configured |

---

## 8. Config sketch

```toml
[complexity]
enabled = true
top_n_ai_explanations = 5
cyclo_medium = 11
cyclo_high = 21
cyclo_critical = 51
cognitive_medium = 16
cognitive_high = 26

[complexity.ratchet]   # v1 — ignored at MVP
enabled = false
fail_if_max_cognitive_increases = true
fail_if_high_complexity_count_increases = true

[ml]                   # v2 — default off
enabled = false
embed_model = "nomic-embed-text"

[testing]
inventory = true
# CLI: --import-coverage path (repeatable) also supported
import_coverage = []
top_n_test_gap_explanations = 5
require_tests_for_high_complexity = true
```

---

## 9. Test presence, coverage & Right-BICEP

### What exists today in RepoLens

Extended theme `arch.testing` and playbook bullets (“unit / integration / e2e / missing coverage”) are **Slow Brain checklist** only. There is **no** Fast Brain that counts tests, imports coverage.xml, or scores scenario adequacy.

### Test inventory (F1 — MVP)

Count **test functions/cases**, not only files (file-only ratios mislead when five files hold 200 tests).

| Signal | Python MVP (stdlib `ast`) |
|--------|---------------------------|
| Test files | Paths matching test layout (`tests/`, `test_*.py`, `*_test.py`, …) |
| Test cases | `def test_*` functions + methods on `unittest.TestCase` subclasses |
| Production functions | Non-test `FunctionDef` / `AsyncFunctionDef` in inventory |
| Scorecard | `Test files: N \| Test cases: M \| Ratio: X.X tests/production function` |

### Coverage ∩ complexity (F2 — v1)

A coverage XML/LCOV file is a set of **executed line numbers**. Fast Brain already knows each function’s `[start_line, end_line]` span.

\[
\mathrm{Coverage}(func)=\frac{\lvert \mathrm{ExecutedLines} \cap [start,end] \rvert}{\lvert \mathrm{ExecutableLines} \in [start,end] \rvert}
\]

**High-Risk Uncovered Hotspot** when **cognitive > 15** and **Coverage(func) < 50%**.

### Are there libraries?

| Need | Use existing tools (import) | RepoLens role |
|------|----------------------------|---------------|
| Line / branch **% covered** | **coverage.py** + pytest-cov → XML/JSON; Istanbul/nyc → LCOV; JaCoCo XML; `go tool cover`; llvm-cov | `--import-coverage` — do **not** reimplement tracers |
| “Are there tests at all?” + case counts | Heuristics + `ast` (Python) | Fast Brain **inventory** (MVP) |
| Happy / negative / error / exception / **Right-BICEP** gaps | No standard library — Right-BICEP is a **methodology** | Slow Brain playbook + capped AI findings |
| Mutation / test effectiveness | mutmut, Cosmic Ray, Stryker | v2 **companion recipe** only |
| Property / inverse checks | Hypothesis (Python), fast-check (JS) | Mention in playbook as remediation options |

**Right-BICEP** (checklist) with **P de-emphasised for AI**:

| Letter | Question | AI emphasis |
|--------|----------|-------------|
| **[Right]** | Are results correct for representative cases? | Medium |
| **B** | Boundary conditions (nulls, empties, off-by-one)? | **Heavy** |
| **I** | Inverse relationships? | Medium |
| **C** | Cross-check via another means? | Medium |
| **E** | Error / exception / failure forced? | **Heavy** |
| **P** | Performance characteristics? | **Light** — do **not** speculate on latency or micro-benchmarks unless obvious quadratic \(O(n^2)\) (or worse) scaling is evident in the code |
| **+** | Edge + **happy / negative / exception** paths | **Heavy** on negative/exception |

Playbook must state the P guardrail explicitly so Slow Brain does not hallucinate caching lectures.

Honesty: **line coverage ≠ scenario adequacy.**

### Categories & themes

| Finding | `category` | Theme |
|---------|------------|-------|
| Complexity Issue | `quality.complexity` | `arch.kiss` |
| Missing / scarce tests | `testing.missing_tests` | `arch.testing` |
| Scenario gap | `testing.scenario_gap` | `arch.testing` (+ `rel.edge_cases` / `rel.error_recovery` in narrative) |

### Join with complexity

Priority for AI test-gap pack: **high cognitive/cyclomatic ∩ uncovered (or no tests)** — `top_n_test_gap_explanations` default 5, max 10.

---

## 10. Competitive rudder alignment

From [competitive-landscape-sonar-alternatives-2026.md](./competitive-landscape-sonar-alternatives-2026.md):

- **Adopt:** structural complexity metrics developers trust; AI remediation on the worst offenders.
- **Integrate:** SARIF from existing linters/complexity tools.
- **Refuse:** Sonar server, ASPM portal, seat SaaS, full quality-profile / OOP rule-engine clone.

Complexity + cognitive engines are a **narrow un-parking** of “metrics with teeth,” not a pivot into SonarQube.

---

## 11. Privacy

- Metric computation is local and deterministic.
- Coverage artifacts are read from user-supplied local paths only.
- AI packs leave the machine only when the user configured a **BYOK** cloud provider; Ollama stays local.
- ML embeddings (v2) default **off**; when on, prefer Ollama embed models and cache under `.repolens/` — no silent upload.

---

## 12. Success criteria (MVP)

1. Fixture-proven Python McCabe + cognitive scores (stdlib only).
2. Functions ≤10 cyclo / ≤15 cognitive never become Issues.
3. Slow Brain pack size ≤ configured top-N (default 5) even if 200+ functions are complex.
4. Scorecard shows p95, max, band counts, **Top-10 hotspot table**, and **test inventory** (files + cases + ratio).
5. Docs state clearly: metrics ≠ Sonar server; AI = local/BYOK refactor/test-gap help; **coverage % ≠ BICEP adequacy**; AI must not speculate on **P** without evidence.

---

## Changelog

| Date | Note |
|------|------|
| 2026-09-27 | Initial approved design: thresholds, top-5 AI cap, Python ast MVP, `[complexity]` extras, ratchet@v1, ML@v2 opt-in |
| 2026-09-27 | Testing lane: inventory, `--import-coverage`, Right-BICEP / happy-negative-exception gaps; library stance |
| 2026-09-27 | F1 case counts; F4 P guardrail; Top-10 vs Top-5; coverage∩span + cognitive>15 & cov<50%; categories |
