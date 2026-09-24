# G2 — Cyclicity baseline ratchet + diff-aware CI (design)

**Status:** Draft for review  
**Date:** 2026-09-24  
**Issue:** [#35](https://github.com/vksvicky/RepoLens/issues/35)  
**Umbrella:** [#18](https://github.com/vksvicky/RepoLens/issues/18) · [zugel-comparison-and-roadmap.md](../../design/zugel-comparison-and-roadmap.md)  
**Depends on:** G1 [#34](https://github.com/vksvicky/RepoLens/issues/34) / [G1 spec](./2026-09-24-g1-python-import-graph-design.md) (merged graph APIs)  
**Feeds:** G3 MCP (optional baseline queries); G4 does not replace this gate

---

## 1. Problem

G1 detects runtime import cycles and can fail CI on `source=graph` findings, but there is **no stored debt baseline**. Teams with legacy cycles need a **non-increasing ratchet**: debt may stay or shrink; it must not grow — without punishing refactors that *reshape* SCCs while lowering total cyclicity.

## 2. Locked decisions

| Decision | Lock |
|----------|------|
| **Fail rule** | **Rule 1 — cyclicity-only.** Fail iff **runtime cyclicity increases** vs baseline. |
| **Cyclicity** | ∑ *n²* over SCCs with *n* ≥ 2 (same as G1 `cyclicity()`). |
| **Fingerprints** | **Informational only** — persisted + used in PR messaging / annotations; **not** a pass/fail tripwire. |
| **Gate surface** | **Approach A:** `repolens baseline set` + `repolens check --diff` (primary) + `repolens review --ratchet` (opt-in). |
| **Edge set** | Same gated graph as G1 (`type_only` / `local_imports` config). Type-only cycles do not hard-fail by default. |

### Why Rule 1 (not fingerprint-fail)

Decoupling a 6-module SCC (cyclicity 36) into a 3-module + 2-module pair (9+4=13) **creates new fingerprints** while cutting debt ~64%. Fingerprint-fail (Rule 2) would block that PR. Cyclicity-only **passes** and can celebrate the reduction in messaging.

Rule 1 still catches regressions:

* Clean baseline (0) → any 2-cycle adds ≥ +4 → fail.  
* Legacy baseline (100) → new 2-cycle → 104 → fail.  
* 3-cycle expands to 4 → 9 → 16 → fail.

---

## 3. Goals

1. **FR1 — Baseline write:** `repolens baseline set` writes a deterministic, git-friendly file under `.repolens/` with cyclicity + sorted SCC fingerprints (+ metadata).  
2. **FR2 — Fast check:** `repolens check --diff` runs graph-only analysis, compares to baseline, exits non-zero on cyclicity increase; sub-second–class on small/medium repos when G1 graph is warm/cached where practical.  
3. **FR3 — Review opt-in:** `repolens review --ratchet` (or config `[graph].ratchet = true`) applies the same comparator to the review exit code.  
4. **FR4 — Fingerprint messaging:** On breach (and optionally on improvement), print/annotate fingerprint **diff**: new cycles / resolved cycles — without using that diff as the tripwire.  
5. **FR5 — Diff-aware location:** Map ratchet failure to a **newly added import line** in the git diff when possible; emit SARIF and/or GitHub Actions annotations.  
6. **FR6 — Docs:** FAQ + `ci.md` cycles-only adoption ladder; primary gate = CLI check / pre-commit, not MCP.

## 4. Non-goals

* Failing CI solely because SCC fingerprints changed while cyclicity did not increase  
* MCP pre-flight tools (G3)  
* Architecture DSL / layer rules (G4)  
* Polyglot graphs  
* Auto-updating the baseline on every green PR (explicit `baseline set` or documented opt-in workflow only)  
* Replacing G1’s per-SCC `source=graph` findings (ratchet is additive)

---

## 5. Architecture

```text
repolens baseline set
        │
        ▼
analyse_python_graph(root)  ──► GraphResult
        │
        ▼
.repolens/baseline.json     (cyclicity + fingerprints + meta)

repolens check --diff  /  review --ratchet
        │
        ▼
analyse_python_graph(root)  ──► current GraphResult
        │
        ▼
compare(current, baseline)
        │
        ├── tripwire: current.cyclicity > baseline.cyclicity  → exit ≠ 0
        ├── messaging: fingerprint set diff (new / resolved / unchanged)
        └── location: map +Δ cyclicity to new import line(s) in git diff
                │
                ▼
        stdout + optional SARIF / Actions annotations
```

### Module layout (proposed)

| Module | Responsibility |
|--------|----------------|
| `src/repolens/graph/baseline.py` | Load/save baseline; fingerprint encode; compare |
| `src/repolens/graph/ratchet.py` | `evaluate_ratchet(current, baseline) -> RatchetResult` |
| `src/repolens/graph/diff_anchor.py` | Map breach → new import line(s) from `git diff` |
| `src/repolens/cli/commands_baseline.py` | `baseline set` / `baseline show` |
| `src/repolens/cli/commands_check.py` | `check --diff` |
| Wire `--ratchet` on review | Exit code integration |

Reuse G1: `analyse_python_graph`, `CycleGroup.modules`, `cyclicity`.

---

## 6. Baseline file format

**Path:** `.repolens/baseline.json` (JSON, not YAML — stable tooling; sorted keys).

```json
{
  "schemaVersion": 1,
  "kind": "cyclicity",
  "generatedAt": "2026-09-24T20:00:00Z",
  "repolensVersion": "0.1.0a1",
  "graph": {
    "engine": "grimp",
    "packages": ["repolens"],
    "moduleCount": 42,
    "cyclicity": 16,
    "cycleCount": 2,
    "fingerprints": [
      ["app.a", "app.b"],
      ["app.c", "app.d", "app.e"]
    ]
  },
  "configSnapshot": {
    "type_only": "ignore",
    "local_imports": "exclude"
  }
}
```

**Fingerprint:** sorted tuple of module names for each SCC with *n* ≥ 2; list of fingerprints sorted lexicographically (stable for git diffs).

**Round-trip:** write → read → identical cyclicity and fingerprint set.

Teams **may commit** the file; ratchet bumps are reviewed in PRs when someone runs `baseline set` after intentional debt acceptance (rare) or after first adoption.

---

## 7. Ratchet comparison (tripwire)

```text
RatchetResult:
  breached: bool                 # True iff current.cyclicity > baseline.cyclicity
  baseline_cyclicity: int
  current_cyclicity: int
  delta: int                     # current - baseline
  fingerprints_added: list[...]  # in current, not in baseline (informational)
  fingerprints_removed: list[...]  # in baseline, not in current (informational)
  config_mismatch: bool          # active GraphConfig ≠ baseline.configSnapshot
  config_mismatch_detail: str    # e.g. local_imports exclude→include
  notes: list[str]               # durability/info lines (incl. ratchet.config_mismatch: …)
  message: str                   # British English user-facing summary
```

### Config snapshot mismatch (implementation guard)

Baseline stores `configSnapshot` (`type_only`, `local_imports`, and any other knobs that change the gated edge set).

**Gotcha:** Baseline recorded with `local_imports=exclude` (cyclicity 16); later `.repolens.toml` flips to `include` → cyclicity may jump (e.g. 24) with **no code diff**, tripping Rule 1.

**Required behaviour in `evaluate_ratchet()`:**

1. Compare active `GraphConfig` (normalized) to `baseline.configSnapshot`.  
2. If they differ, set `config_mismatch=True` and append  
   `ratchet.config_mismatch: graph settings changed since baseline (e.g. local_imports exclude→include); re-run \`repolens baseline set\` after intentional config changes`.  
3. **Still apply Rule 1** on the numbers (do not auto-pass). Operators see *why* debt appeared to grow.  
4. Optional later (out of MVP): `--allow-config-drift` to warn-only without failing — **not** in G2 MVP unless demanded.

Test: fixture baseline exclude/16 + current include/24 → `breached=True` **and** `config_mismatch` note present.
**Exit codes (`check --diff`):**

| Code | Meaning |
|------|---------|
| 0 | No breach (cyclicity ≤ baseline), or no baseline + soft skip documented |
| 1 | Ratchet breach (cyclicity increased) |
| 2 | Usage / config / missing graph engine failure |
| 3 | Graph analysis failed hard (optional: treat as fail-closed in CI) |

**No baseline present:**

* Default: exit **2** with clear message (“run `repolens baseline set`”) when `--require-baseline`, else exit **0** with durability/warning note (config knob). Recommended CI: `--require-baseline`.

**Cyclicity decreased:** exit 0; print improvement line, e.g. `Cyclicity reduced from 36 to 13 (−23).`

---

## 8. CLI surface

```bash
repolens baseline set [--path DIR] [--out .repolens/baseline.json]
repolens baseline show [--path DIR]

repolens check --diff [--path DIR] [--baseline .repolens/baseline.json] [--require-baseline]
# graph-only; optional --sarif OUT; uses git diff vs merge-base or HEAD~ / --base REF

repolens review … --ratchet
# same comparator after graph lane; fails exit like check when breached
```

Config (`.repolens.toml`):

```toml
[graph]
# … G1 knobs …
ratchet = false              # default off for review; CI enables via flag or true
baseline_path = ".repolens/baseline.json"
require_baseline = false     # check --diff may override
```

---

## 9. Diff-aware anchoring

When `breached` and a git diff is available:

1. Compute fingerprint **added** SCCs (informational culprit set).  
2. Among modules in added/grown cycles, find **added or modified `import` / `from` lines** in the diff.  
3. Prefer the line that closes a new edge into an SCC (best-effort using G1 representative edges ∩ diff hunks).  
4. Emit:
   * CLI: path:line message  
   * GitHub Actions: `::error file=…,line=…::Ratchet breach: …`  
   * SARIF: result with physical location when `--sarif` / review SARIF on  

Example stdout:

```text
Ratchet breach: runtime cyclicity increased from 16 to 25 (+9).
+ New cycle introduced: [app.orders, app.billing, app.notifications]
- Resolved cycles: none
app/orders.py:42: import app.billing
```

If no diff / no line found: still fail on cyclicity; message without file anchor + durability note `ratchet.unanchored: …`.

---

## 10. Interaction with G1 findings

| Layer | Role |
|-------|------|
| G1 `source=graph` Issues | Describe **current** cycle groups (always-on honesty) |
| G2 ratchet | Binary **debt growth** gate vs committed baseline |

A legacy repo may have High graph findings **and** a passing ratchet (baseline already includes that debt). Adoption ladder: set baseline → stop growth → later lower baseline intentionally after cleanups.

---

## 11. Testing (Right-BICEP)

| Case | Expect |
|------|--------|
| Right | Cyclicity 16→25 → breached; fingerprints_added populated |
| Right | Cyclicity 36→13 → **not** breached; fingerprints may differ freely |
| Boundary | Baseline 0, new 2-cycle → breached (+4) |
| Inverse | Write baseline → analyse same tree → not breached, delta 0 |
| Cross-check | Fingerprint encoding matches sorted `CycleGroup.modules` |
| Error | Missing baseline + `--require-baseline` → exit 2 |
| Perf | Fixture <50 modules: `check --diff` completes in seconds in tests |
| Edge | Type-only-only cycles with `type_only=ignore` → cyclicity unchanged |
| Edge | `configSnapshot` mismatch (exclude→include) → breach **plus** `ratchet.config_mismatch` note |
| Anchor | Synthetic git diff with new import → annotation points at that line |

---

## 12. User documentation (keep it simple)

**Principle:** Operators install from PyPI and learn one short ladder — not a Sonargraph manual. Prefer FAQ + one CI snippet; avoid duplicating design math in install docs.

| Doc | Update for G2? | What users see |
|-----|----------------|----------------|
| **`docs/faq.md`** | **Yes (required)** | Short “Import cycles & ratchet” section: always-on G1 detection; optional baseline; Rule 1 in one sentence (“debt score must not rise”); fingerprints explain *what* changed; if you change `[graph]` settings, re-run `baseline set`. Link to `ci.md`. |
| **`docs/ci.md`** | **Yes (required)** | One recipe: `baseline set` once → commit `.repolens/baseline.json` → PR job `repolens check --diff --require-baseline`. Pre-commit optional one-liner. |
| **`docs/command-atlas.md`** | **Yes** | `baseline set` / `show`, `check --diff`, `review --ratchet` rows + exit codes. |
| **`README.md`** | **Yes (light)** | One bullet under features / What’s next: Python import cycles + optional cyclicity ratchet (link FAQ). No deep math. |
| **`docs/CHANGELOG.md`** | **Yes** on ship | User-facing “Added” bullets for `baseline` / `check --diff` / `--ratchet`. |
| **`.repolens.example.toml`** | **Yes** | Commented `[graph]` ratchet knobs. |
| **`docs/publishing.md` / PyPI checklist** | **No feature dump** | Stay install / Trusted Publishing / smoke `pip install repolens-audit`. Optionally one smoke line after G2 ships: `repolens baseline set --help` — not cycle theory. |
| **PyPI project description / README on PyPI** | **Same as README** | Keep install-first; cycles mentioned once if README mentions them. |
| **Design / phases / this spec** | Maintainers only | Not linked from the install path. |

**Adoption ladder (FAQ copy sketch):**

1. Install: `pip install repolens-audit` — reviews report Python cycles automatically (G1).  
2. Optional: `repolens baseline set` and commit `.repolens/baseline.json`.  
3. CI: `repolens check --diff --require-baseline` so cyclicity cannot rise.  
4. After intentional graph-config changes: re-run `baseline set`.

---

## 13. Docs (maintainer checklist)

* FAQ + `ci.md` + command atlas + light README (see §12).  
* Explicit: MCP is not the primary gate (G3 secondary).  
* Rule 1 rationale in FAQ (one paragraph): untangling must not fail CI.

---

## 14. Success criteria

- [ ] Baseline round-trip deterministic (sorted JSON)  
- [ ] Rule 1 enforced; fingerprint-only changes never fail  
- [ ] Config mismatch note when `configSnapshot` ≠ active config  
- [ ] `check --diff` + `review --ratchet` wired  
- [ ] Diff anchor + SARIF/annotation path tested  
- [ ] Coverage ≥ 85% on `baseline` / `ratchet` / `diff_anchor` modules  
- [ ] Simple user docs: FAQ + ci.md + command-atlas + light README; CHANGELOG on ship; **no** cycle essay in `publishing.md`  
- [ ] #35 AC checked  

---

## 15. Open follow-ups (out of G2 MVP)

* Warm grimp cache reuse between review and check  
* Auto-suggest `baseline set` after debt reduction in PR bot comments  
* `--allow-config-drift` warn-only mode  
* Multi-package fingerprint display truncation policy beyond title length