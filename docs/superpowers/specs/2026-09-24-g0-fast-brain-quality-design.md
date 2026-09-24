# G0 — Fast Brain quality: near-clones & scorecard (design)

**Status:** Approved for plan (rev 2) · Plan: [../plans/2026-09-24-g0-fast-brain-quality.md](../plans/2026-09-24-g0-fast-brain-quality.md)  
**Date:** 2026-09-24  
**Issue:** [#33](https://github.com/vksvicky/RepoLens/issues/33) (companion track)  
**Umbrella:** [#18](https://github.com/vksvicky/RepoLens/issues/18) · [zugel-comparison-and-roadmap.md](../../design/zugel-comparison-and-roadmap.md)  
**Anchor:** [#34](https://github.com/vksvicky/RepoLens/issues/34) / [G1 spec](./2026-09-24-g1-python-import-graph-design.md)  
**Extends:** [Phase 6.11 Fast Brain](./2026-08-06-phase-6.11-fast-brain-whole-tree-heuristics.md)

---

## 1. Problem

Fast Brain already flags **mega-files** and **deep nesting**, but lacks:

1. Cheap **near-clone / duplicate-block** detection (DRY signal), and  
2. A rolled-up **quality scorecard** so operators see DRY/KISS posture without reading every finding.

This track is intentionally **graph-free** and parallel to G1.

## 2. Goals

1. **FR1 — Near-clones:** Detect duplicate / near-duplicate code blocks via fixed line windows + content hash; emit `source=heuristic` findings with **physical** file:line (and peer location in explanation).  
2. **FR2 — Scorecard:** Compact quality block in Markdown + JSON aggregating mega-files, nesting, clone clusters, and counts.  
3. **FR3 — Config:** Knobs under `[fast_brain.near_clones]` in `.repolens.toml`.  
4. **FR4 — Noise control:** Coalesce overlapping windows; suppress boilerplate; dual caps (scorecard vs emitted findings) — §6.  
5. **FR5 — Tests + docs:** Right-BICEP; FAQ; explicit non-goal of Sonargraph-class clone UX.

## 3. Non-goals

* Sonargraph / IDE clone browser product  
* Semantic clone detection (AST isomorphism, ML embeddings)  
* Import-graph cycles (G1)  
* Changing `--fail-on` so heuristics fail CI under `scanner_only` (heuristics stay soft under CI scanner-only)

## 4. Existing surface (reuse)

| Already present | Module |
|-----------------|--------|
| Mega-files | `heuristics/mega_files.py` |
| Deep nesting | `heuristics/deep_nesting.py` |
| Fast Brain orchestration | `heuristics/runner.py` |
| Config | `[fast_brain]`, `[deep].mega_file_*` |
| Ignore / exclude patterns | Mega-file excludes, inventory skips, `.gitignore` where already applied |

G0 **adds** clone detection + scorecard aggregation; does not reimplement mega/nesting.

## 5. Architecture

```text
Fast Brain inventory
        │
        ├── mega_files (existing)
        ├── deep_nesting (existing)
        ├── near_clones (new: window → coalesce → suppress → dual-cap)
        └── … other hygiene …
        │
        ▼
QualityScorecard.from_issues(+ inventory stats + omitted-clone notes)
        │
        ▼
FindingReport.quality (optional block) + Markdown section
```

### Module layout (proposed)

| Module | Responsibility |
|--------|----------------|
| `src/repolens/heuristics/near_clones.py` | Normalize+map, window hash, coalesce, suppress, dual-cap → `Issue`s |
| `src/repolens/quality.py` | `QualityScorecard` model + builder |
| `src/repolens/schema.py` | Optional `quality` on `FindingReport` |
| `src/repolens/report.py` | Markdown “Quality scorecard” section |
| `heuristics/runner.py` | Wire `find_near_clones` |

## 6. Near-clone algorithm (MVP)

Keep it Fast Brain–honest: **no AST** for clone matching (line/hash only).

### 6.1 Normalize with physical line map

For each file:

1. Read lines as physical 1-based source lines.  
2. Build parallel arrays: `norm_lines[]` and `norm_to_phys[]` where each kept line records its **original** line number.  
3. Drop blank lines from the normalized buffer **only after** recording the map (so index `i` in the hash buffer maps to `norm_to_phys[i]`).  
4. For hashing text, optionally strip leading indent from each kept line; **do not** use normalized indices as `Issue.line` — always emit `norm_to_phys[start]` / end via the map.

### 6.2 Sliding windows

* Window **N** lines (default 12); stride **S** (default 6).  
* Hash normalized window text (e.g. sha256 truncated).  
* Record each hit as `(hash, file, phys_start, phys_end, norm_start, norm_end)`.

### 6.3 Coalesce contiguous overlaps (stride trap)

With N=12, S=6, a 30-line copied function yields multiple overlapping window matches between the same file pair. **Before** emitting findings:

* Group matches by `(file_a, file_b, hash-run connectivity)`.  
* Merge windows that **overlap or abut** on both sides into one **clone block**: e.g. `A.py:1–30` duplicated in `B.py:45–74`.  
* One coalesced block ⇒ at most one cluster candidate (not four).

### 6.4 Boilerplate & false-positive suppression

Skip a window / block when **any** of:

1. **Header comments:** match occurs entirely within the first 15 **physical** lines **and** every line in the window is comment-only (`#`, `//`, or `/* … */` / `*` continuation — language-aware light check).  
2. **Import-only windows:** every non-blank normalized line is an `import` / `from … import` (Python) or obvious import form for JS/TS (`import ` / `require(`) — extend per suffix lightly.  
3. **Ignored paths:** honor existing mega-file / inventory exclude globs and common generated patterns (e.g. `**/migrations/**`, `**/*_pb2.py`, `**/generated/**`, lockfiles already excluded by inventory). Configurable extra globs under `[fast_brain.near_clones].exclude_globs`.

### 6.5 Dual caps (scorecard vs findings)

| Cap | Default | Purpose |
|-----|---------|---------|
| `max_clusters` | **50** | Scorecard tally / internal cluster list ceiling |
| `max_findings` | **10** | Max `Issue` objects emitted into `report.issues` (top by occurrence count, then block line length) |

* `nearCloneClusters` on the scorecard reflects clusters **before** the findings cap (up to `max_clusters`).  
* Scorecard `notes` must record omission, e.g. `40 additional clone clusters omitted from findings`.  
* Emitting 50 Issues is **forbidden** by default — that drowns security/architecture signal in the CLI.

### 6.6 Severity & finding shape

* Severity: **LOW** default; **MEDIUM** when occurrences ≥ `medium_at_occurrences` (default 4) or coalesced block length ≥ threshold.  
* `category`: `quality.near_clone`  
* `source`: `heuristic`  
* `file` / `line`: primary block physical start  
* `explanation`: peer path + physical range; occurrence count  
* `recommendedFix`: extract shared helper / accept intentional duplication  

## 7. Quality scorecard

```text
QualityScorecard:
  megaFileCount: int
  deepNestingCount: int
  nearCloneClusters: int      # up to max_clusters
  nearCloneOccurrences: int
  nearCloneFindingsEmitted: int  # ≤ max_findings
  filesScanned: int
  notes: list[str]            # e.g. "40 additional clone clusters omitted from findings"
```

Markdown example:

```markdown
## Quality scorecard (Fast Brain)

| Signal              | Count |
|---------------------|------:|
| Mega-files          |     3 |
| Deep nesting        |     7 |
| Near-clone clusters |    12 |
| Files scanned       |  1840 |

_40 additional clone clusters omitted from findings._

_Deterministic DRY/KISS signals — not an architecture certification._
```

JSON: `report.quality` (omit when Fast Brain disabled / zero scanned).

## 8. Config

```toml
[fast_brain]
# existing max_files, parallel_workers, …

[fast_brain.near_clones]
enabled = true
window_lines = 12
stride = 6
min_occurrences = 2
max_clusters = 50          # scorecard / internal tally
max_findings = 10          # Issues emitted to report.issues
medium_at_occurrences = 4
header_comment_lines = 15
# exclude_globs = ["**/migrations/**", "**/*_pb2.py", "**/generated/**"]
```

## 9. Testing (Right-BICEP)

| Case | Expect |
|------|--------|
| Right | Two files sharing a 12-line block → ≥1 near-clone finding |
| Coalesce | 30-line copy with stride 6 → **one** coalesced finding, not 4 |
| Line map | Blank lines stripped for hash; `Issue.line` matches physical source |
| Boundary | Window longer than file → no finding |
| Inverse | Unique files → zero clone findings |
| Cross-check | Same content different indent → still hash-match after normalize |
| Error | Unreadable file → skip; no crash |
| Perf | Synthetic 200 small files finishes quickly in unit test |
| FP | Copyright header / import-only block → no finding |
| Cap | 25 clusters → scorecard 25 (or capped 50); Issues ≤ 10; note lists omitted count |
| Scorecard | Known fixture → expected mega/nesting/clone tallies |

## 10. Coordination with G1

* Scorecard does **not** include cyclicity (G1 owns graph metrics).  
* Separate PRs/branches; rebase if both touch `schema.py` / `report.py`.

## 11. Success criteria

- [ ] Near-clone heuristic wired into Fast Brain with coalesce + line map + FP suppress  
- [ ] Dual caps enforced (50 tally / 10 findings)  
- [ ] Scorecard in MD + JSON with omission notes  
- [ ] Config knobs documented  
- [ ] Tests ≥ 85% on new modules  
- [ ] FAQ states non-goal (no Sonargraph clone UX)

---

## Explicit deferrals

* Tokenizers beyond whitespace normalize  
* Cross-language semantic clones  
* UI / interactive clone explorer
