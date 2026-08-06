# Two-Lane presentation & CQ parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RepoLens reports read as clearly as SecureVibes’ Two-Lane headline, cut heuristic↔LLM twin noise, add a Fast Brain indent-nesting signal, and document an honest dogfood recipe — without SaaS gamification or false scanner claims.

**Architecture:** Extend existing provenance + report/CLI summary surfaces; tighten Phase 6.9 clustering; add one line-based heuristic under `heuristics/` (no AST); docs-only positioning. Remains local CLI; no cross-repo percentiles.

**Tech Stack:** Python 3.11+, Pydantic schema, Rich CLI table, pytest, Markdown report writer.

**Spec:** [../specs/2026-08-06-two-lane-presentation-and-cq-parity.md](../specs/2026-08-06-two-lane-presentation-and-cq-parity.md)

## Global Constraints

- British English in user-facing strings.
- Fast Brain: regex / line / stat / hash only — **no AST** (Phase 6.11).
- Do not claim gitleaks finds missing `.gitignore` rules; do not equate env-fallback scripts with hardcoded secrets.
- Do not invent SaaS “better than N% of repos” scores.
- Gate confidence remains review-adequacy, not “% secure”.
- Leave untracked `docs/assets/` alone.
- Dual-review gate before commit/push; never push without explicit override.

## File map

| Path | Responsibility |
|------|----------------|
| `src/repolens/schema.py` | Optional `fastBrainSeconds` / `llmSeconds` on `ProvenanceBlock` |
| `src/repolens/pipeline/run.py` | Record lane timings into provenance when measurable |
| `src/repolens/report.py` | Two-Lane headline + metrics rows for lane times |
| `src/repolens/cli/export.py` | Rich summary rows / one-liner |
| `src/repolens/cluster.py` | Cross-source theme clustering |
| `src/repolens/heuristics/deep_nesting.py` | Indent-depth heuristic |
| `src/repolens/heuristics/runner.py` | Wire nesting heuristic |
| `src/repolens/themes.py` | Map `heuristic.deep_nesting` → `arch.readability_complexity` |
| `tests/test_report.py`, `tests/test_cluster.py`, `tests/test_heuristics_*.py` | Coverage |
| `docs/faq.md`, `docs/command-atlas.md`, `docs/CHANGELOG.md` | Recipe + positioning |

---

### Task 1: Two-Lane headline helper + Markdown/CLI surface

**Files:**
- Modify: `src/repolens/report.py`
- Modify: `src/repolens/cli/export.py`
- Modify: `tests/test_report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Produces: `format_two_lane_headline(report: FindingReport) -> str`
- Consumes: `report.provenance.fastBrainFiles`, `llmPackFiles`, `triageRouting`, `llmBypassed`; `report.summary`; `report.durationSeconds`

- [ ] **Step 1: Write the failing test**

```python
from repolens.report import format_two_lane_headline
from repolens.schema import FindingReport, ProvenanceBlock, Summary


def test_two_lane_headline_includes_counts():
    report = FindingReport(
        confidence=59,
        summary=Summary(critical=0, high=4, medium=28, low=8),
        issues=[],
        provenance=ProvenanceBlock(fastBrainFiles=184, llmPackFiles=26, triageRouting=True),
        durationSeconds=120.0,
    )
    line = format_two_lane_headline(report)
    assert "Fast Brain: 184" in line
    assert "Slow Brain: 26" in line
    assert "4 high" in line.lower() or "High 4" in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py::test_two_lane_headline_includes_counts -v`  
Expected: FAIL (`format_two_lane_headline` missing)

- [ ] **Step 3: Implement helper + wire Markdown**

Add near top of `report.py` (or after `format_duration`):

```python
def format_two_lane_headline(report: FindingReport) -> str:
    """Punchy SecureVibes-style opener — provenance-honest."""
    prov = report.provenance
    fb = prov.fastBrainFiles if prov else None
    llm = prov.llmPackFiles if prov else None
    s = report.summary
    counts = (
        f"{s.critical} critical · {s.high} high · "
        f"{s.medium} medium · {s.low} low"
    )
    dur = format_duration(report.durationSeconds)
    parts: list[str] = []
    if fb is not None:
        parts.append(f"Fast Brain: {fb} file(s)")
    if llm is not None:
        if prov and prov.llmBypassed:
            parts.append("Slow Brain: bypassed (triage clean)")
        else:
            parts.append(f"Slow Brain: {llm} file(s)")
    if dur:
        parts.append(dur)
    parts.append(counts)
    return " · ".join(parts)
```

In `render_markdown`, after the Duration / Gate confidence metadata block and **before** `## Gate verdict`, insert:

```python
headline = format_two_lane_headline(report)
if headline:
    lines.extend(["", f"**Two-Lane:** {headline}", ""])
```

- [ ] **Step 4: Wire Rich CLI summary**

In `_print_summary` (`cli/export.py`), after building provenance rows, print the headline above the table:

```python
from repolens.report import format_two_lane_headline

headline = format_two_lane_headline(report)
if headline:
    console.print(f"[bold]Two-Lane[/bold]: {headline}")
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_report.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/repolens/report.py src/repolens/cli/export.py tests/test_report.py
git commit -m "$(cat <<'EOF'
feat: add punchy Two-Lane headline to reports and CLI summary

EOF
)"
```

---

### Task 2: Optional lane timing provenance

**Files:**
- Modify: `src/repolens/schema.py` (`ProvenanceBlock`)
- Modify: `src/repolens/pipeline/run.py`
- Modify: `src/repolens/report.py` (`format_two_lane_headline`, metrics table)
- Modify: `tests/test_report.py`

**Interfaces:**
- Produces: `ProvenanceBlock.fastBrainSeconds: float | None`, `llmSeconds: float | None`
- Consumes: monotonic timers around Fast Brain heuristics block and LLM/deep block in `run.py`

- [ ] **Step 1: Failing test for headline with lane seconds**

```python
def test_two_lane_headline_includes_lane_seconds_when_present():
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[],
        provenance=ProvenanceBlock(
            fastBrainFiles=158,
            llmPackFiles=17,
            fastBrainSeconds=2.1,
            llmSeconds=32.0,
        ),
    )
    line = format_two_lane_headline(report)
    assert "2.1s" in line or "2s" in line
    assert "32" in line
```

- [ ] **Step 2: Extend schema**

```python
# ProvenanceBlock
fastBrainSeconds: float | None = Field(default=None, ge=0)
llmSeconds: float | None = Field(default=None, ge=0)
```

- [ ] **Step 3: Record timings in `pipeline/run.py`**

Wrap existing Fast Brain heuristics call and LLM/deep section with `time.monotonic()`; pass into `ProvenanceBlock(...)`. If a lane is skipped/bypassed, leave that field `None`.

- [ ] **Step 4: Include seconds in headline when set**

```python
if fb is not None:
    fb_bit = f"Fast Brain: {fb} file(s)"
    if prov and prov.fastBrainSeconds is not None:
        fb_bit += f" in {prov.fastBrainSeconds:.1f}s"
    parts.append(fb_bit)
# similarly for Slow Brain + llmSeconds
```

Add metrics table rows when present (British English labels).

- [ ] **Step 5: Tests + commit**

Run: `pytest tests/test_report.py tests/test_pipeline*.py -q --tb=line` (or the repo’s existing pipeline test module names)  
Commit: `feat: record Fast/Slow Brain lane timings in provenance`

---

### Task 3: Cluster heuristic ↔ LLM twins by theme family

**Files:**
- Modify: `src/repolens/cluster.py`
- Modify: `tests/test_cluster.py` (create if missing; else extend)
- Check: where `cluster_near_duplicates` is called in `pipeline/run.py` (ensure still on)

**Interfaces:**
- Produces: updated `_cluster_key` / `_theme_family` so `heuristic.gitignore_secrets` and `sec.repo_hygiene_secrets` on the same file collapse when titles normalize similarly **or** when theme family matches
- Preference on severity tie: `scanner` > `llm` > `heuristic` (never drop LLM prose for a heuristic stub)

Design rule (implement exactly):

```python
_THEME_FAMILY = {
    "heuristic.gitignore_secrets": "secrets_hygiene",
    "sec.repo_hygiene_secrets": "secrets_hygiene",
    "heuristic.scripts_hygiene": "secrets_hygiene",
    "heuristic.mega_file": "structure_size",
    "arch.structure_size": "structure_size",
    "heuristic.sibling_duplication": "duplication",
    "arch.duplication": "duplication",
    "heuristic.deep_nesting": "readability",
    "arch.readability_complexity": "readability",
}

def _theme_family(category: str) -> str:
    c = (category or "").strip().lower()
    return _THEME_FAMILY.get(c, c)

def _cluster_key(issue: Issue) -> tuple[str, str, str]:
    identity = (issue.cwe or "").strip().lower()
    if not identity:
        # Same file + theme family collapses heuristic/LLM twins even if titles differ slightly
        identity = _theme_family(issue.category) or _norm_title(issue.title)
    return (_norm_file(issue.file), _theme_family(issue.category), identity)
```

When two issues share file + theme family, keep highest severity; if tie, prefer
`source == "scanner"`, then **`llm`**, then **`heuristic`**.

Rationale: heuristics are fast but generic (“Mega-file detected”). The LLM often
carries the rich explanation and code example. Preferring heuristic on a
severity tie would discard actionable text. Scanners still win ties (trusted,
non-hallucinated). On unequal severity, highest severity still wins even if that
row is heuristic-only.

- [ ] **Step 1: Failing test**

```python
from repolens.cluster import cluster_near_duplicates
from repolens.schema import Issue, Severity


def test_clusters_heuristic_and_llm_gitignore_twins():
    a = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.gitignore_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore missing .env",
        explanation="x",
        impact="y",
        recommendedFix="z",
        codeExample="#",
        source="heuristic",
    )
    b = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.repo_hygiene_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore Missing .env / Secret Patterns",
        explanation="x",
        impact="y",
        recommendedFix="z",
        codeExample="#",
        source="llm",
    )
    out = cluster_near_duplicates([a, b])
    assert len(out) == 1
    assert out[0].severity == Severity.HIGH
    assert out[0].source == "llm"  # higher severity wins
    assert out[0].clusteredCount == 2


def test_cluster_tie_prefers_llm_text_over_heuristic():
    """Same severity: keep LLM row (rich text), not generic heuristic stub."""
    heur = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="heuristic.mega_file",
        file="src/big.py",
        line=1,
        title="Mega-file detected",
        explanation="File is large.",
        impact="Harder to review.",
        recommendedFix="Split it.",
        codeExample="# n/a",
        source="heuristic",
    )
    llm = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="arch.structure_size",
        file="src/big.py",
        line=1,
        title="Mega-file: big.py has 637 lines",
        explanation="The `_run_mode` function is 175 lines; split by command.",
        impact="Merge conflicts and review fatigue.",
        recommendedFix="Extract `_run_mode` into run_mode.py.",
        codeExample="+ from .run_mode import _run_mode",
        source="llm",
    )
    out = cluster_near_duplicates([heur, llm])
    assert len(out) == 1
    assert out[0].source == "llm"
    assert "_run_mode" in out[0].explanation
    assert out[0].clusteredCount == 2
```

- [ ] **Step 2: Run — expect FAIL (currently different category keys / wrong tie order)**

- [ ] **Step 3: Implement theme-family clustering + source tie-break**

Source rank for **equal severity only**:

```python
_SOURCE_RANK = {"scanner": 3, "llm": 2, "heuristic": 1}  # higher wins ties
# compare: severity first, then _SOURCE_RANK.get(source, 0)
```

- [ ] **Step 4: Run tests + commit**

```bash
pytest tests/test_cluster.py -q
git commit -m "fix: cluster heuristic and LLM twin findings by theme family"
```

---

### Task 4: Fast Brain indent-depth nesting heuristic

**Files:**
- Create: `src/repolens/heuristics/deep_nesting.py`
- Modify: `src/repolens/heuristics/runner.py`
- Modify: `src/repolens/themes.py`
- Create/Modify: `tests/test_heuristics_deep_nesting.py`

**Interfaces:**
- Produces: issues with `category="heuristic.deep_nesting"`, `source="heuristic"`
- Constraint: read file text; count lines whose leading whitespace depth ≥ threshold (default 6 levels × 4 spaces, or tab count ≥ 6); **no `ast` import**
- Noise note (acceptable for a heuristic): may flag deeply indented multi-line strings / block comments / Python docstrings. Do not try to perfect-parse strings in Fast Brain; if dogfood noise is loud, raise `min_lines` or exclude `"""`/`'''`-heavy ranges later — not in v1.

```python
# deep_nesting.py — sketch
CODE_SUFFIXES = {".swift", ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt"}

def find_deep_nesting(files, *, min_depth: int = 6, min_lines: int = 12) -> list[Issue]:
    ...
```

Wire into runner after mega_files / siblings. Map theme:

```python
"heuristic.deep_nesting": "arch.readability_complexity",
```

- [ ] **Step 1: Fixture + failing test** (temp file with 20 lines at 24-space indent)

- [ ] **Step 2: Implement line-based detector**

- [ ] **Step 3: Wire runner + theme**

- [ ] **Step 4: Tests + commit**

```bash
pytest tests/test_heuristics_deep_nesting.py -q
git commit -m "feat: add Fast Brain indent-depth nesting heuristic"
```

---

### Task 5: Docs — fair dogfood recipe + positioning

**Files:**
- Modify: `docs/faq.md`
- Modify: `docs/command-atlas.md`
- Modify: `docs/CHANGELOG.md` (Unreleased)
- Modify: `docs/phases.md` (optional one-line under 6.11 / follow-ups)

**Content requirements (British English):**

1. **Fair compare recipe** (PatternSorcerer-class):
   - Prefer `--ci` / triage (or default adaptive) — **not** `--full` — when demoing Two-Lane speed.
   - Expect: Fast Brain ≈ whole tree; Slow Brain ≈ hit files / pack cap.
   - Local 32B will still be slower than Haiku API; say so.

2. **Positioning:**
   - RepoLens remediation: `repolens explain` produces moves + diffs.
   - Prompt-paste tools generate ChatGPT prompts; different product.
   - No cross-tenant percentile grades (privacy-first local CLI).
   - Scanners find secret *content*; missing `.gitignore` patterns are heuristics.

3. **CHANGELOG** bullet under Unreleased for Two-Lane headline, clustering, nesting heuristic.

- [ ] **Step 1: Edit FAQ + atlas sections**

- [ ] **Step 2: CHANGELOG**

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: Two-Lane dogfood recipe and SecureVibes-style positioning"
```

---

### Task 6: Verification dogfood (manual)

**Not committed code — evidence for gate confidence.**

- [ ] **Step 1: Re-run PatternSorcerer without `--full`**

```bash
TARGET=/Users/vivek/Development/PatternSorcerer
repolens review --path "$TARGET" --out "$TARGET/reports" --deep \
  --model qwen2.5-coder:32b --verbose --timeout 3600 --ci
```

(Adjust flags to whatever enables triage in current CLI; prefer documented atlas recipe.)

- [ ] **Step 2: Confirm report header**

Expect Markdown to show something like:

`**Two-Lane:** Fast Brain: N file(s) in Xs · Slow Brain: M file(s) in Ys · … · 0 critical · …`

with **M ≪ N** when triage hits are sparse.

- [ ] **Step 3: Confirm clustering**

`.gitignore` / LocalizedString should not appear as 3 near-identical rows.

- [ ] **Step 4: Note results in chat / optional `docs/reviews/` gate export only if shipping**

---

## Out of scope (explicit)

| Item | Why |
|------|-----|
| SaaS percentile / Grade D | Privacy-first; no cross-tenant corpus |
| Claiming SecureVibes free = triage | May be quota; unproven |
| AST nesting in Fast Brain | Phase 6.11 forbid |
| Auto “fix everything” PR bot | Phase 6.8 deferred (#11) |

## Self-review checklist

- [x] Spec coverage: presentation, timings, clustering, nesting, docs, dogfood
- [x] No SaaS gamification task
- [x] Fast Brain stays non-AST
- [x] Honesty constraints in Global Constraints

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-06-two-lane-presentation-and-cq-parity.md` (spec alongside).

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans checkpoints  

Which approach?
