# G2 Cyclicity Ratchet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a git-friendly cyclicity baseline and fail CI only when runtime cyclicity rises (Rule 1), via `baseline set`, `check --diff`, and `review --ratchet`, with fingerprint messaging, config-mismatch notes, and diff-anchored annotations.

**Architecture:** Build on G1 `analyse_python_graph` / `GraphResult`. `baseline.py` encodes cyclicity + sorted SCC fingerprints + `configSnapshot`; `ratchet.py` applies Rule 1 and config mismatch warnings; `diff_anchor.py` maps breaches to new import lines; thin Typer commands for baseline/check; review gains `--ratchet`.

**Tech Stack:** Python 3.11+, existing `repolens.graph` (grimp), Typer, JSON (sorted), git diff subprocess, pytest.

**Spec:** [../specs/2026-09-24-g2-cyclicity-ratchet-design.md](../specs/2026-09-24-g2-cyclicity-ratchet-design.md) · Issue [#35](https://github.com/vksvicky/RepoLens/issues/35)

**Prerequisite:** G1 [#34](https://github.com/vksvicky/RepoLens/issues/34) / [PR #46](https://github.com/vksvicky/RepoLens/pull/46) **merged to `main`** (graph package present). Do not start code on a branch without `repolens.graph`.

---

## Global Constraints

- **Rule 1 only:** fail iff `current.cyclicity > baseline.cyclicity`. Fingerprint changes alone never fail.
- Cyclicity = ∑ n² over SCCs with n≥2 (reuse G1 `cyclicity()`).
- British English in user-facing strings (`behaviour`, `analysed`).
- Config mismatch → note `ratchet.config_mismatch: …`; **still** apply Rule 1 (no auto-pass).
- Primary gate = `repolens check --diff`; MCP not in scope.
- Simple user docs: FAQ + ci.md + command-atlas + light README; **no** cycle essay in `publishing.md`.
- TDD per task; coverage ≥ 85% on `baseline` / `ratchet` / `diff_anchor`.
- Branch: `feat/g2-cyclicity-ratchet` off `main` after G1 merge (worktree `.worktrees/g2`).

---

## File Map

| Path | Responsibility |
|------|----------------|
| `src/repolens/graph/baseline.py` | Fingerprints; load/save `.repolens/baseline.json`; `config_snapshot_from_graph_config` |
| `src/repolens/graph/ratchet.py` | `RatchetResult`, `evaluate_ratchet` |
| `src/repolens/graph/diff_anchor.py` | Map breach → import line from git unified diff |
| `src/repolens/config.py` | Extend `GraphConfig`: `ratchet`, `baseline_path`, `require_baseline` |
| `src/repolens/cli/commands_baseline.py` | `baseline set` / `show` |
| `src/repolens/cli/commands_check.py` | `check --diff` |
| `src/repolens/cli/app.py` | Register typers |
| `src/repolens/cli/commands_review.py` + `pipeline/run.py` | `--ratchet` exit integration |
| `.repolens.example.toml` | Ratchet knobs |
| `docs/faq.md`, `docs/ci.md`, `docs/command-atlas.md`, `README.md`, `docs/CHANGELOG.md` | Simple user docs |
| `tests/test_graph_baseline.py`, `test_graph_ratchet.py`, `test_graph_diff_anchor.py`, `test_cli_check.py` | TDD |

Reuse G1 fixtures under `tests/fixtures/graph_cycle_pkg/` when present on `main`.

---

### Task 1: Baseline encode / load / save

**Files:**
- Create: `src/repolens/graph/baseline.py`
- Create: `tests/test_graph_baseline.py`

**Interfaces:**
- Produces:
  - `fingerprint_cycles(result: GraphResult) -> list[list[str]]`
  - `config_snapshot_from_graph_config(cfg: GraphConfig) -> dict[str, str]`
  - `baseline_from_graph(result, *, config: GraphConfig, version: str) -> dict`
  - `write_baseline(path: Path, doc: dict) -> None` (sorted keys, indent=2, trailing newline)
  - `load_baseline(path: Path) -> dict`
  - `DEFAULT_BASELINE_PATH = ".repolens/baseline.json"`

- [ ] **Step 1: Failing tests**

```python
def test_fingerprint_sorted_and_stable():
    # CycleGroup modules unsorted → fingerprints sorted; list of fps lexicographic
    ...

def test_round_trip_tmp_path(tmp_path):
    doc = baseline_from_graph(result, config=GraphConfig(), version="0.0.0-test")
    path = tmp_path / "baseline.json"
    write_baseline(path, doc)
    loaded = load_baseline(path)
    assert loaded["graph"]["cyclicity"] == doc["graph"]["cyclicity"]
    assert loaded["graph"]["fingerprints"] == doc["graph"]["fingerprints"]
    assert loaded["configSnapshot"] == {"type_only": "ignore", "local_imports": "exclude"}
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement** JSON with `json.dumps(..., sort_keys=True, indent=2) + "\n"`. Schema fields per spec §6.

- [ ] **Step 4–5: pytest pass; commit** `feat(graph): cyclicity baseline encode and round-trip`

---

### Task 2: evaluate_ratchet (Rule 1 + config mismatch)

**Files:**
- Create: `src/repolens/graph/ratchet.py`
- Create: `tests/test_graph_ratchet.py`

**Interfaces:**
- Produces: `@dataclass RatchetResult` and  
  `evaluate_ratchet(*, current: GraphResult, baseline: dict, config: GraphConfig) -> RatchetResult`

- [ ] **Step 1: Failing tests**

```python
def test_breach_when_cyclicity_rises():
    # baseline cyclicity 16, current 25 → breached, delta 9, fingerprints_added non-empty

def test_no_breach_when_debt_falls_even_if_fingerprints_change():
    # 36 → 13 with different fingerprints → breached False

def test_config_mismatch_note_still_breaches():
    # baseline snapshot local_imports=exclude, cyclicity 16
    # current config include, cyclicity 24
    # → breached True AND config_mismatch True AND note starts with ratchet.config_mismatch:
```

- [ ] **Step 2–5: Implement; commit** `feat(graph): Rule 1 ratchet evaluate with config mismatch note`

Message helpers (British English):

* Breach: `Ratchet breach: runtime cyclicity increased from {b} to {c} (+{d}).`
* Improve: `Cyclicity reduced from {b} to {c} (−{d}).`
* Flat: `Cyclicity unchanged at {c}.`

---

### Task 3: Diff anchor

**Files:**
- Create: `src/repolens/graph/diff_anchor.py`
- Create: `tests/test_graph_diff_anchor.py`

**Interfaces:**
- Produces:  
  `parse_added_import_lines(unified_diff: str) -> list[tuple[str, int, str]]`  
  `anchor_ratchet_breach(*, diff_text: str, added_fingerprints: Sequence[Sequence[str]], representative_paths: Sequence[str] | None = None) -> tuple[str, int, str] | None`  
  `format_github_actions_error(file: str, line: int, message: str) -> str`

- [ ] **Step 1: Test with synthetic unified diff** containing `+from app import billing` in `app/orders.py` → returns `("app/orders.py", line, …)`.

- [ ] **Step 2–5: Implement** (stdlib only; no git required in unit tests — inject diff string). Prefer lines whose path modules intersect added fingerprint module tails. Commit `feat(graph): diff-anchor ratchet import lines`

---

### Task 4: Config knobs + example TOML

**Files:**
- Modify: `src/repolens/config.py` (`GraphConfig`)
- Modify: `.repolens.example.toml`
- Modify: `tests/test_config.py` (parse `[graph]` ratchet fields)

```python
# GraphConfig additions:
ratchet: bool = False
baseline_path: str = ".repolens/baseline.json"
require_baseline: bool = False
```

- [ ] **Steps: TDD parse → commit** `feat(graph): ratchet config knobs`

---

### Task 5: CLI `baseline set` / `show`

**Files:**
- Create: `src/repolens/cli/commands_baseline.py`
- Modify: `src/repolens/cli/app.py` (register `baseline_app`)
- Create: `tests/test_cli_baseline.py` (CliRunner)

```python
baseline_app = typer.Typer(name="baseline", ...)
@baseline_app.command("set")
def baseline_set(path: Path = ..., out: Path | None = ...): ...
@baseline_app.command("show")
def baseline_show(...): ...
```

`set`: `analyse_python_graph` → `write_baseline`. On graph FAILED → exit 3.  
`show`: print cyclicity + fingerprint count + path.

- [ ] **Commit** `feat(cli): repolens baseline set and show`

---

### Task 6: CLI `check --diff`

**Files:**
- Create: `src/repolens/cli/commands_check.py`
- Modify: `src/repolens/cli/app.py`
- Create: `tests/test_cli_check.py`

**Behaviour:**

1. Load config; resolve baseline path.  
2. If missing baseline: exit 2 if `--require-baseline` / `require_baseline`, else exit 0 + warn.  
3. `analyse_python_graph` → `evaluate_ratchet`.  
4. Print message + fingerprint +/- lines + config mismatch notes.  
5. If breached and git available: `git diff` (base ref option `--base`, default merge-base with `origin/main` or `HEAD~1` best-effort) → anchor → print path:line; if `GITHUB_ACTIONS=true`, print `::error ...`.  
6. Exit 1 if breached, else 0. Graph hard-fail → exit 3.

Keep graph-only (no scanners/LLM).

- [ ] **Commit** `feat(cli): repolens check --diff cyclicity ratchet`

---

### Task 7: `review --ratchet`

**Files:**
- Modify: `src/repolens/cli/commands_review.py` (add `--ratchet: bool = False`)
- Modify: `src/repolens/pipeline/run.py` or review exit path: after report built, if ratchet flag or `cfg.graph.ratchet`, run `evaluate_ratchet`; if breached, exit 1 (after/alongside existing `--fail-on`). Document precedence: both can fail (either triggers exit 1).

- [ ] **Test:** scanners-only review on cycle fixture with baseline cyclicity 0 → exit 1 when `--ratchet`.  
- [ ] **Commit** `feat(cli): review --ratchet exit integration`

---

### Task 8: Simple user docs + CHANGELOG

**Files:**
- `docs/faq.md` — short ladder + Rule 1 one-liner + re-baseline after config change  
- `docs/ci.md` — one GHA/pre-commit snippet for `check --diff --require-baseline`  
- `docs/command-atlas.md` — command rows + exit codes  
- `README.md` — one feature bullet + FAQ link  
- `docs/CHANGELOG.md` — Added bullets  
- **Do not** expand `docs/publishing.md` beyond optional `--help` smoke

- [ ] **Commit** `docs: FAQ/ci/README for cyclicity ratchet (G2)`

---

### Task 9: Coverage + dogfood

- [ ] `pytest tests/test_graph_baseline.py tests/test_graph_ratchet.py tests/test_graph_diff_anchor.py tests/test_cli_baseline.py tests/test_cli_check.py -q --cov=repolens.graph.baseline --cov=repolens.graph.ratchet --cov=repolens.graph.diff_anchor` ≥ 85%  
- [ ] Dogfood on RepoLens: `repolens baseline set` then `repolens check --diff` (expect 0 if no new debt)  
- [ ] Update `docs/phases.md` G2 → `[~]` / PR link when opening PR  
- [ ] **Commit** if phases/docs tweaks needed; open PR closing #35

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Baseline JSON + fingerprints | 1 |
| Rule 1 evaluate | 2 |
| Config mismatch note | 2 |
| Diff anchor + Actions | 3, 6 |
| Config knobs | 4 |
| `baseline set/show` | 5 |
| `check --diff` | 6 |
| `review --ratchet` | 7 |
| Simple user docs | 8 |
| Coverage / dogfood | 9 |

## Placeholder scan

None intentional — APIs named above.

## Execution gate

**Do not dispatch implementers until G1 is on `main`.** Then: worktree `.worktrees/g2` from `main`, subagent-driven Tasks 1→9.
