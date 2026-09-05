# Vacuous LLM pass confidence floor (design)

**Status:** Approved for plan  
**Date:** 2026-09-05  
**Issue:** [#21](https://github.com/vksvicky/RepoLens/issues/21)  
**Consumer requirement:** LogViewer `docs/reviews/2026-09-05-repolens-vacuous-confidence-requirement.md`  
**Depends on:** Declarative `[coverage]` seeding (`feat/declarative-coverage-seeding`)  
**Dogfood evidence:** LogViewer `gate_review_report_review_2026-09-05_2147` (gate 0% with missed 0, scanners ran, vacuous LLM packs)

## 1. Problem

Deep mode sets `gate = min(ran pass confidences + scored band confidences) − global coverage penalties`. Each deep pass contributes the model’s self-reported `confidence`. Local models often return schema-valid empty packs (`issues: []`, `confidence: 0`), which floors every band and the gate at 0% even when:

- Checklist is complete (covered + valid N/A, including project seeds)
- Scanners all `ran`
- Only Medium heuristics remain (no Critical/High)

`is_vacuous_llm_report` already exists but is not used to adjust pass confidence before `compute_audit_metrics`.

**Root cause (two layers):**

1. **Prompt / schema contract:** Confidence is easy to read as “confidence in reported issues”; with zero issues, `0` is consistent but wrong for package adequacy.
2. **Aggregation floor:** Stubborn models still emit `0` on empty packs; defensive substitution remains required.

## 2. Goals

1. **FR0** — Clarify empty-pack confidence in prompts so well-behaved models can report high confidence on genuine clean packs.
2. **FR1** — Floor **genuine** vacuous passes to scanners-only baselines (75 / 55) when preconditions hold, so clean repos are not false-failed on gate %.
3. **False-clean guard** — Project `[coverage]` seeds alone must not unlock flooring for hung/stub empty JSON.
4. **Observability** — Durable floored / skipped notes with a fixed skip-reason enum.
5. **Docs** — FAQ: package adequacy ≠ “% secure”; `--fail-on` is severity; dual-review-style confidence gates often want ≥70 (floored clean packages land at 75).

## 3. Non-goals

- Invent or suppress findings
- Remove LLM confidence when the model returned issues or finding-like gaps
- Require `--trust-project-config`
- LogViewer-specific thresholds or theme ids
- Replace coverage seeding
- New required schema fields in v1 (`analysisNotes` deferred)
- Band-specific deterministic validators beyond Option G (scanners as global integrity proxy)
- Change `--fail-on` to gate on confidence %

## 4. Design decisions

| Decision | Choice |
|----------|--------|
| Approach | **Prompt (FR0) + floor backstop (FR1)** together |
| Auto floor | **75** if configured scanners all `ran`; else **55** (reuse scanners-only baselines) |
| Scanner +5 bonus | **Keep** after flooring → Security **80**, p2/p3 **75**, gate **75** (no special-case in `compute_band_confidence`) |
| Scanner precondition | **Option G** — scanners-all-ran is **global pipeline integrity**, not proof p2/p3 were reviewed by Semgrep |
| Analysis evidence (v1) | Cascade: optional future string fields (`analysisNotes` / `narrative` / `notes`) **or** `len(raw_response_text.strip()) ≥ 100`. Do **not** treat `Summary` counts as prose. Do **not** require model coverage notes (would fight seeding). |
| Vacuous definition | `confidence == 0`, empty issues, no finding-like durability gaps; ignore Two-Lane / non-coverage transport noise; **refuse** degraded / schema-invalid / hard transport failure |
| Config | `[deep] vacuous_pass_confidence_floor: Optional[int] = None` — `None` → auto 75/55; `0` → off; `1–100` → pin |
| Observability | Durability notes (see §6); candidate rule + skip precedence |
| Language | British English in user-facing strings |

## 5. Architecture & data flow

```text
per pass: analyze_structured → PassOutcome{name, report, raw_text, degraded?}

merge issues/gaps
  → evaluate_coverage(+ project seeds)
  → for each PassOutcome:
        if eligible → pass_confidences[name] = floor_value
        else        → pass_confidences[name] = raw confidence
        append floored or skipped note when flooring was considered
  → compute_audit_metrics(pass_confidences, coverage, scanner_runs, issues)
     # +5 scanner bonus still applies on security band
```

Substitution happens only on `pass_confidences`. Downstream band math is unchanged.

### Eligibility (all must hold)

1. Pass is vacuous (refined helper) and **not** degraded / schema-invalid.
2. Analysis evidence cascade passes (raw ≥ 100 or future string notes).
3. After merge + seeds, scored-band checklist is complete (`missed` empty and no invalid N/A for scored prefixes).
4. Config allows substitution (`vacuous_pass_confidence_floor is not 0`; `None` means auto).

Seeds alone never satisfy (2).

### Floor value

| Condition | Auto floor |
|-----------|------------|
| Scanners all `ran` | 75 |
| Otherwise | 55 |
| Config `vacuous_pass_confidence_floor = N` (1–100) | N for all eligible passes |
| Config `= 0` | Substitution disabled |
| Config omitted / `None` | Auto baseline (75 / 55) |

**Config type (`DeepConfig`):**

```python
vacuous_pass_confidence_floor: Optional[int] = None
# None → dynamic auto-baseline (75 if scanners ran, else 55)
# 0    → disabled
# 1..100 → pin to explicit integer
```

## 6. Observability

### When flooring was “considered” (candidate)

A pass is a flooring **candidate** only if it looks like an empty pack:

```python
is_candidate = report.confidence == 0 and len(report.issues) == 0
```

- If `is_candidate` and eligible → emit `metrics.vacuous_pass_confidence_floored:…`
- If `is_candidate` and not eligible → emit exactly one `metrics.vacuous_pass_floor_skipped:…`
- If not a candidate (e.g. 5 findings, confidence 80) → **no** floor/skip note

### Applied

```text
metrics.vacuous_pass_confidence_floored:<pass>=<N> (scanners_ran=<true|false>, checklist=complete)
```

### Skipped (enum) and precedence

| Reason code | When |
|-------------|------|
| `pass_degraded` | Transport error, timeout, or schema repair failure |
| `no_analysis_evidence` | Stub JSON / raw &lt; 100 / no future string notes |
| `checklist_incomplete` | missed &gt; 0 or invalid N/A on scored prefixes |

When multiple skip preconditions fail, emit **one** note using this priority:

```text
pass_degraded > no_analysis_evidence > checklist_incomplete
```

Transport failure is the most actionable signal and precedes analysis-evidence or coverage checks.

```text
metrics.vacuous_pass_floor_skipped:<pass>=pass_degraded
metrics.vacuous_pass_floor_skipped:<pass>=no_analysis_evidence
metrics.vacuous_pass_floor_skipped:<pass>=checklist_incomplete
```

Never raise on skip; keep raw confidence. Never invent findings.

## 7. FR0 — Prompt / schema clarification

Update `SYSTEM_PROMPT` and repair-prompt confidence wording (and any deep-pass reminder) so that:

- If issues were found → rate confidence in those findings (0–100).
- If `issues` is empty → rate confidence that the examined scope is **free of in-band issues** (0–100). An empty array with **high** confidence is valid after a thorough review.

No new JSON fields in v1. Snapshot/unit test locks the instruction string.

## 8. Worked examples

| Scenario | Result |
|----------|--------|
| LogViewer-like: vacuous + raw≥100 + missed 0 + scanners ran | Bases 75 → sec **80**, rel/arch **75**, gate **75** + floored notes |
| Same, scanners not all ran | Bases/gate **55** |
| Seeds complete + stub `{"issues":[],"confidence":0}` (~35 chars) | No floor; `no_analysis_evidence` |
| Vacuous + missed coverage | No floor; `checklist_incomplete` |
| Vacuous + Critical from scanner/peer | Floor then Crit/High penalty still applies |
| Degraded / schema_invalid pass | No floor; `pass_degraded` |
| `vacuous_pass_confidence_floor = 0` | No substitution |

## 9. Testing (TDD)

1. Genuine clean vacuous p1/p2/p3 + complete coverage + scanners ran → gate **75**, sec **80**, rel/arch **75** + floored notes  
2. Same without scanners all ran → gate **55**  
3. Stub empty JSON + seeds complete → no floor; `no_analysis_evidence`  
4. Vacuous + missed coverage → no floor; `checklist_incomplete`  
5. Issues present with confidence 0 → no floor  
6. Vacuous + Critical scanner finding → still heavily penalised after floor  
7. Degraded / schema_invalid → no floor; `pass_degraded`  
8. Coverage-seed + theme notes regression unchanged  
9. FR0 prompt snapshot contains empty-pack confidence wording  
10. Config: `None` → auto 75/55; `floor=0` disables; `floor=N` overrides  
11. Candidate rule: non-empty issues → no floored/skipped note; multi-fail skips emit only highest-priority reason (`pass_degraded` first)  

## 10. Docs

Update FAQ “What do report metrics mean?”:

- Why models often emitted `confidence: 0` on empty packs (old contract)
- New empty-pack confidence meaning (FR0)
- When flooring applies vs skip reasons
- Scanners-all-ran as **global integrity** proxy (not p2/p3 content validation)
- Floored 75 is package adequacy, not “% secure”
- `--fail-on` remains **severity-based**; dual-review-style **confidence** gates often want ≥70 — floored clean packages meet that at 75

## 11. Touchpoints

- `src/repolens/llm/setup.py` / `llm/parse.py` — FR0 prompt strings  
- `src/repolens/llm_structured.py` / `pipeline/deep_exec.py` — retain raw text per pass; refined vacuous + substitution  
- `src/repolens/config.py` — `DeepConfig.vacuous_pass_confidence_floor`  
- `src/repolens/metrics.py` — unchanged formula; consume substituted pass bases  
- `docs/faq.md`, `.repolens.example.toml`  
- Tests: new module + prompt snapshot  

## 12. Exit criteria

Given a LogViewer-class package (missed 0, scanners ran, genuine vacuous empty packs):

1. Gate confidence **75** (not 0; not merely &gt; 0)
2. Security **80**, reliability/architecture **75** (absent Crit/High penalties)
3. Stub + seeds does **not** floor
4. Theme coverage / seed notes unchanged
5. Tests above green; no consumer hard-coding

## 13. Follow-ups (out of v1)

- Optional `analysisNotes` schema field as primary proof-of-work  
- Near-vacuous empty packs with confidence 1–20  
- Band-specific integrity hooks (Option B)
