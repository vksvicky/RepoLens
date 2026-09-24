# G0 Fast Brain Quality (Near-clones + Scorecard) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Fast Brain near-clone detection (coalesced windows, physical line map, FP suppress, dual caps) and a Quality scorecard block in Markdown/JSON — without touching the import graph.

**Architecture:** Extend `heuristics/near_clones.py` with normalize→hash→coalesce→suppress→dual-cap; build `QualityScorecard` from heuristic issues + scan stats; attach to `FindingReport.quality` and render in `report.py`. Remains `source=heuristic`; CI `scanner_only` unchanged.

**Tech Stack:** Python 3.11+, stdlib hashlib, Pydantic, pytest.

**Spec:** [../specs/2026-09-24-g0-fast-brain-quality-design.md](../specs/2026-09-24-g0-fast-brain-quality-design.md) · Issue [#33](https://github.com/vksvicky/RepoLens/issues/33)  
**Anchor plan:** [2026-09-24-g1-python-import-graph.md](./2026-09-24-g1-python-import-graph.md)

---

## Global Constraints

- No AST for clone matching (line/hash only).
- `Issue.line` must be **physical** source line via `norm_to_phys`.
- Coalesce overlapping/abutting windows for the same file pair into **one** clone block.
- Dual caps: `max_clusters=50` (scorecard), `max_findings=10` (emitted Issues); omission note required.
- Suppress: header comments (first 15 phys lines), import-only windows, exclude globs.
- British English in user-facing copy.
- Scorecard does **not** include cyclicity (G1 owns that).
- Branch: `feat/g0-fast-brain-quality` off `main` (rebase if `schema.py`/`report.py` collide with G1).
- TDD; coverage ≥ 85% on `near_clones` + `quality`.

---

## File Map

| Path | Responsibility |
|------|----------------|
| `src/repolens/heuristics/near_clones.py` | Window hash, coalesce, suppress, dual-cap → Issues + cluster stats |
| `src/repolens/quality.py` | `QualityScorecard` builder |
| `src/repolens/schema.py` | `quality` field on `FindingReport` (coordinate with G1 if both open) |
| `src/repolens/config.py` | `NearClonesConfig` under `FastBrainConfig` |
| `src/repolens/heuristics/runner.py` | Call `find_near_clones` |
| `src/repolens/pipeline/run.py` | Attach scorecard to report |
| `src/repolens/report.py` | Markdown Quality scorecard section |
| `.repolens.example.toml` | `[fast_brain.near_clones]` |
| `tests/test_near_clones.py` | Algorithm tests |
| `tests/test_quality_scorecard.py` | Scorecard aggregation |
| `docs/faq.md` | Non-goal + knobs |

---

### Task 1: Normalize + physical line map + window hash

**Files:**
- Create: `src/repolens/heuristics/near_clones.py`
- Create: `tests/test_near_clones.py`

**Interfaces:**
- Produces: `normalize_lines(text: str) -> tuple[list[str], list[int]]`  
  `iter_windows(norm: list[str], phys: list[int], *, window: int, stride: int) -> Iterator[WindowHit]`  
  `WindowHit(hash: str, phys_start: int, phys_end: int, norm_start: int, norm_end: int)`

- [ ] **Step 1: Failing tests**

```python
def test_normalize_preserves_physical_lines():
    text = "a = 1\n\nb = 2\n"
    norm, phys = normalize_lines(text)
    assert norm == ["a = 1", "b = 2"]
    assert phys == [1, 3]

def test_issue_line_uses_physical_not_norm_index(tmp_path):
    # Full find_near_clones tested in Task 3; here window phys_start == 3
    text = "x\n\n" + "\n".join(f"line{i}" for i in range(12))
    norm, phys = normalize_lines(text)
    hits = list(iter_windows(norm, phys, window=12, stride=6))
    assert hits[0].phys_start == phys[0]
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
def normalize_lines(text: str) -> tuple[list[str], list[int]]:
    norm: list[str] = []
    phys: list[int] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        norm.append(raw.lstrip())  # strip leading indent for hash text
        phys.append(i)
    return norm, phys

def window_hash(lines: Sequence[str]) -> str:
    payload = "\n".join(lines).encode()
    return hashlib.sha256(payload).hexdigest()[:16]
```

- [ ] **Step 4–5: pytest; commit** `feat(quality): near-clone normalize and window hashing`

---

### Task 2: Coalesce overlapping matches

**Files:**
- Modify: `src/repolens/heuristics/near_clones.py`
- Modify: `tests/test_near_clones.py`

**Interfaces:**
- Produces: `coalesce_pair_hits(hits_a_to_b: list[PairHit]) -> list[CloneBlock]`  
  `CloneBlock(file_a, file_b, phys_start_a, phys_end_a, phys_start_b, phys_end_b, occurrences)`

- [ ] **Step 1: Failing test — 30-line copy with N=12 S=6 → one block**

```python
def test_coalesce_stride_trap():
    # Simulate 4 overlapping window matches between A and B for one 30-line region
    hits = [
        PairHit("A.py", "B.py", 1, 12, 45, 56),
        PairHit("A.py", "B.py", 7, 18, 51, 62),
        PairHit("A.py", "B.py", 13, 24, 57, 68),
        PairHit("A.py", "B.py", 19, 30, 63, 74),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 1
    assert blocks[0].phys_start_a == 1 and blocks[0].phys_end_a == 30
    assert blocks[0].phys_start_b == 45 and blocks[0].phys_end_b == 74
```

Coalesce rule: sort by `phys_start_a`; merge if ranges overlap or abut (`next.start <= cur.end + 1`) **and** the B-side ranges similarly overlap/abut.

- [ ] **Step 2–5: Implement; commit** `feat(quality): coalesce overlapping near-clone windows`

---

### Task 3: FP suppress + dual caps + find_near_clones

**Files:**
- Modify: `src/repolens/heuristics/near_clones.py`
- Modify: `tests/test_near_clones.py`
- Create: `tests/fixtures/near_clones/` (optional)

**Interfaces:**
- Produces: `find_near_clones(entries: list[FileEntry], *, config: NearClonesConfig) -> NearCloneResult`  
  `NearCloneResult(issues: list[Issue], cluster_count: int, occurrence_count: int, notes: list[str])`

- [ ] **Step 1: Failing tests**

```python
def test_header_comment_suppressed(tmp_path, make_entries):
    header = "\n".join(f"# copyright line {i}" for i in range(12))
    a = tmp_path / "a.py"; b = tmp_path / "b.py"
    a.write_text(header + "\n"); b.write_text(header + "\n")
    result = find_near_clones(make_entries(tmp_path), config=NearClonesConfig())
    assert result.issues == []

def test_import_only_suppressed(tmp_path, make_entries):
    block = "\n".join(f"from typing import A{i}" for i in range(12))
    ...
    assert result.issues == []

def test_dual_cap_emits_ten_and_notes_omission(tmp_path, make_entries):
    # Create 15 distinct duplicated 12-line bodies across file pairs
    ...
    assert len(result.issues) <= 10
    assert result.cluster_count >= 15 or result.cluster_count == 15
    assert any("omitted from findings" in n for n in result.notes)

def test_copied_function_one_finding(tmp_path, make_entries):
    body = "\n".join(f"    x = {i}" for i in range(30))
    fn = f"def copied():\n{body}\n"
    (tmp_path / "a.py").write_text(fn)
    (tmp_path / "b.py").write_text("def other():\n    pass\n\n" + fn)
    result = find_near_clones(make_entries(tmp_path), config=NearClonesConfig())
    assert len(result.issues) == 1
    assert result.issues[0].source == "heuristic"
    assert result.issues[0].category == "quality.near_clone"
    assert result.issues[0].line >= 1  # physical
```

Suppress helpers:

```python
def _is_comment_line(line: str, suffix: str) -> bool: ...
def _is_import_line(line: str, suffix: str) -> bool: ...
def _should_skip_window(phys_lines_text: list[str], phys_start: int, suffix: str, header_n: int) -> bool:
    if phys_end := ...  # if entire window phys numbers <= header_n and all comments: skip
    if all(_is_import_line(l, suffix) for l in phys_lines_text): return True
```

Exclude: reuse mega-file style globs + defaults `**/migrations/**`, `**/*_pb2.py`, `**/generated/**`.

Dual cap: sort clusters by `(-occurrences, -(phys_end-phys_start), file_a)`; scorecard uses up to `max_clusters`; Issues from top `max_findings`; note `f"{omitted} additional clone clusters omitted from findings"`.

- [ ] **Step 2–5: Implement; commit** `feat(quality): near-clone suppress and dual finding caps`

---

### Task 4: Config + runner wire

**Files:**
- Modify: `src/repolens/config.py`
- Modify: `src/repolens/heuristics/runner.py`
- Modify: `.repolens.example.toml`
- Modify: `tests/test_heuristics.py` (smoke)

**Interfaces:**
- `NearClonesConfig` nested on `FastBrainConfig.near_clones`

```python
class NearClonesConfig(BaseModel):
    enabled: bool = True
    window_lines: int = 12
    stride: int = 6
    min_occurrences: int = 2
    max_clusters: int = 50
    max_findings: int = 10
    medium_at_occurrences: int = 4
    header_comment_lines: int = 15
    exclude_globs: list[str] = Field(default_factory=list)

class FastBrainConfig(BaseModel):
    ...
    near_clones: NearClonesConfig = Field(default_factory=NearClonesConfig)
```

In `run_heuristics`, after nesting:

```python
if near_clones_config is None:
    near_clones_config = NearClonesConfig()
if near_clones_config.enabled:
    nc = find_near_clones(entries, config=near_clones_config)
    issues.extend(nc.issues)
    # stash nc stats on HeuristicResult — extend dataclass:
```

Extend `HeuristicResult`:

```python
@dataclass
class HeuristicResult:
    issues: list[Issue] = field(default_factory=list)
    hot_paths: list[str] = field(default_factory=list)
    near_clone_clusters: int = 0
    near_clone_occurrences: int = 0
    near_clone_notes: list[str] = field(default_factory=list)
```

Pass config from `pipeline/run.py`: `near_clones_config=cfg.fast_brain.near_clones`.

- [ ] **Steps: failing smoke → implement → pytest → commit** `feat(quality): wire near-clones into Fast Brain runner`

---

### Task 5: QualityScorecard schema + report

**Files:**
- Create: `src/repolens/quality.py`
- Modify: `src/repolens/schema.py`
- Modify: `src/repolens/pipeline/run.py`
- Modify: `src/repolens/report.py`
- Create: `tests/test_quality_scorecard.py`

**Interfaces:**
- `build_quality_scorecard(*, mega, nesting, near_clusters, near_occurrences, findings_emitted, files_scanned, notes) -> QualityScorecard`
- `FindingReport.quality: QualityScorecard | None = None`

```python
class QualityScorecard(BaseModel):
    megaFileCount: int = 0
    deepNestingCount: int = 0
    nearCloneClusters: int = 0
    nearCloneOccurrences: int = 0
    nearCloneFindingsEmitted: int = 0
    filesScanned: int = 0
    notes: list[str] = Field(default_factory=list)
```

Count mega/nesting from issue categories already used (`heuristic.mega_file` / nesting category — **read existing category strings** from `mega_files.py` / `deep_nesting.py` and match exactly).

Markdown:

```markdown
## Quality scorecard (Fast Brain)

| Signal | Count |
|--------|------:|
| Mega-files | N |
| Deep nesting | N |
| Near-clone clusters | N |
| Files scanned | N |

_…omission notes…_

_Deterministic DRY/KISS signals — not an architecture certification._
```

Call `build_quality_scorecard` once when assembling the final `FindingReport` (all exit paths that include heur_issues). Prefer a small helper `_attach_quality(report, heur_result, files_scanned)` used in scanners-only and LLM paths.

- [ ] **Steps: TDD → commit** `feat(quality): Quality scorecard in JSON and Markdown reports`

---

### Task 6: Docs + coverage

**Files:**
- Modify: `docs/faq.md`
- Modify: `docs/command-atlas.md` (brief)
- Run coverage on new modules

- [ ] FAQ: near-clones are heuristic; dual caps; not Sonargraph UX; no cyclicity in scorecard.  
- [ ] `pytest tests/test_near_clones.py tests/test_quality_scorecard.py tests/test_heuristics.py -q --cov=repolens.heuristics.near_clones --cov=repolens.quality`  
- [ ] Commit `docs(quality): FAQ for near-clones and scorecard`

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Physical line map §6.1 | 1 |
| Sliding windows | 1 |
| Coalesce stride trap §6.3 | 2 |
| FP suppress §6.4 | 3 |
| Dual caps §6.5 | 3 |
| Runner + config | 4 |
| Scorecard MD/JSON | 5 |
| Docs / non-goals | 6 |

## Coordination with G1

If both PRs touch `schema.py` / `report.py` / `run.py`, merge G1 first (anchor) or rebase G0 and resolve by keeping both `report.graph` and `report.quality` fields and both Markdown sections.
