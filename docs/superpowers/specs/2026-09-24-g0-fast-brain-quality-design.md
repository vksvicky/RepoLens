# G0 — Fast Brain quality: near-clones & scorecard (design)

**Status:** Draft for review  
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

1. **FR1 — Near-clones:** Detect duplicate / near-duplicate code blocks via content hash and/or fixed token windows; emit `source=heuristic` findings with file:line (and optional second location in explanation).  
2. **FR2 — Scorecard:** Add a compact quality block to Markdown + JSON reports aggregating mega-files, nesting, clone clusters, and counts.  
3. **FR3 — Config:** Knobs under `[fast_brain]` (and/or `[quality]`) in `.repolens.toml`.  
4. **FR4 — Tests + docs:** Right-BICEP tests; FAQ / rules note; explicit non-goal of Sonargraph-class clone UX.

## 3. Non-goals

* Sonargraph / IDE clone browser product  
* Semantic clone detection (AST isomorphism, ML embeddings)  
* Import-graph cycles (G1)  
* Changing `--fail-on` so heuristics fail CI under `scanner_only` (unchanged: heuristics stay soft under CI scanner-only)

## 4. Existing surface (reuse)

| Already present | Module |
|-----------------|--------|
| Mega-files | `heuristics/mega_files.py` |
| Deep nesting | `heuristics/deep_nesting.py` |
| Fast Brain orchestration | `heuristics/runner.py` |
| Config | `[fast_brain]`, `[deep].mega_file_*` |

G0 **adds** clone detection + scorecard aggregation; does not reimplement mega/nesting.

## 5. Architecture

```text
Fast Brain inventory
        │
        ├── mega_files (existing)
        ├── deep_nesting (existing)
        ├── near_clones (new)
        └── … other hygiene …
        │
        ▼
QualityScorecard.from_issues(+ inventory stats)
        │
        ▼
FindingReport.quality (optional block) + Markdown section
```

### Module layout (proposed)

| Module | Responsibility |
|--------|----------------|
| `src/repolens/heuristics/near_clones.py` | Window/hash clone clusters → `Issue`s |
| `src/repolens/quality.py` | `QualityScorecard` model + builder from issues/stats |
| `src/repolens/schema.py` | Optional `quality: QualityScorecard \| None` on `FindingReport` |
| `src/repolens/report.py` | Markdown “Quality scorecard” section |
| `heuristics/runner.py` | Wire `find_near_clones` |

## 6. Near-clone algorithm (MVP)

Keep it Fast Brain–honest: **no AST**.

1. Restrict to code suffixes (reuse nesting set or shared constant).  
2. Normalize: strip blank lines; optional strip leading indent for window text.  
3. Sliding windows of **N lines** (default 12; config) with stride **S** (default 6).  
4. Hash normalized window text (e.g. sha256 truncated).  
5. Clusters with **≥ 2** occurrences across **distinct files** (or same file ≥ 2 non-overlapping windows) → finding.  
6. Cap findings (e.g. top 50 clusters by occurrence count) to avoid report floods.  
7. Severity: **LOW** default; **MEDIUM** when occurrences ≥ threshold (e.g. 4) or window large.

Exact constants live in config; document defaults in FAQ.

### Finding shape

* `category`: e.g. `quality.near_clone`  
* `source`: `heuristic`  
* `file` / `line`: primary occurrence  
* `explanation`: list other paths:lines (bounded)  
* `recommendedFix`: extract shared helper / accept intentional duplication  

## 7. Quality scorecard

```text
QualityScorecard:
  megaFileCount: int
  deepNestingCount: int
  nearCloneClusters: int
  nearCloneOccurrences: int
  filesScanned: int
  notes: list[str]   # e.g. "near_clones capped at 50"
```

Markdown example:

```markdown
## Quality scorecard (Fast Brain)

| Signal            | Count |
|-------------------|------:|
| Mega-files        |     3 |
| Deep nesting      |     7 |
| Near-clone clusters |  12 |
| Files scanned     |  1840 |

_Deterministic DRY/KISS signals — not an architecture certification._
```

JSON: `report.quality` object (omit when Fast Brain disabled / zero scanned).

## 8. Config

```toml
[fast_brain]
# existing max_files, parallel_workers, …

[fast_brain.near_clones]
enabled = true
window_lines = 12
stride = 6
min_occurrences = 2
max_clusters = 50
medium_at_occurrences = 4
```

## 9. Testing (Right-BICEP)

| Case | Expect |
|------|--------|
| Right | Two files sharing a 12-line block → ≥1 near-clone finding |
| Boundary | Window longer than file → no finding |
| Inverse | Unique files → zero clone findings |
| Cross-check | Same content different indent → still hash-match after normalize |
| Error | Unreadable file → skip; no crash |
| Perf | Synthetic 200 small files finishes quickly in unit test |
| Edge | Same file repeated adjacent windows → do not double-count overlapping as multi-file cluster |
| Scorecard | Known fixture issues → expected mega/nesting/clone tallies |

## 10. Coordination with G1

* **No shared module ownership** required; scorecard does **not** include cyclicity (G1 owns graph metrics).  
* If both land in one release, Markdown may show Quality scorecard **and** Import graph as sibling sections.  
* Prefer separate PRs/branches; rebase if both touch `schema.py` / `report.py`.

## 11. Success criteria

- [ ] Near-clone heuristic wired into Fast Brain  
- [ ] Scorecard in MD + JSON  
- [ ] Config knobs documented  
- [ ] Tests ≥ 85% on new modules  
- [ ] FAQ states non-goal (no Sonargraph clone UX)

---

## Explicit deferrals

* Tokenizers beyond whitespace normalize  
* Cross-language clone matching  
* UI / interactive clone explorer
