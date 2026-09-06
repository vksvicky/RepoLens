# Two-Lane presentation & CQ parity (design)

**Status:** Draft for plan  
**Date:** 2026-08-06  
**Trigger:** PatternSorcerer dogfood vs SecureVibes free report  
**Depends on:** Phase 6.11 Fast Brain (done), Phase 6 explain credibility (done)

## 1. Problem

SecureVibes free reports open with a crisp Two-Lane line (`158 scanned · 17 read · 34s`) and dense code-quality (nesting / duplication) findings. RepoLens already has Fast/Slow Brain provenance and stronger remediation (`explain` diffs), but:

1. Markdown / CLI summaries do not lead with a punchy Two-Lane headline.
2. PatternSorcerer was dogfooded with `--full` (LLM pack = 184), so we cannot honestly claim SecureVibes-style “17 files explained” from that run.
3. Heuristic + LLM twins inflate counts (e.g. `.gitignore` / LocalizedString thrice).
4. Fast Brain lacks an indent/nesting signal (line-based only — no AST, per 6.11).
5. Marketing risk: over-claiming “gitleaks caught .gitignore” or “SecureVibes = our triage” when free tier may be quota-capped.

## 2. Goals

1. **Presentation:** One-line Two-Lane summary in Markdown + CLI (files + optional lane timings + severity counts).
2. **Honesty:** Provenance exposes Fast vs Slow file counts and, when available, lane durations; docs teach triage/`--ci` dogfood for fair speed demos.
3. **Signal quality:** Stronger near-duplicate clustering across `heuristic` ↔ `llm` twins (same file + theme).
4. **CQ parity (scoped):** Optional Fast Brain **indent-depth** heuristic (regex/line/stat only — no AST).
5. **Positioning:** FAQ/atlas note — remediation via `explain` diffs vs prompt-paste tools; no SaaS percentile grades.

## 3. Non-goals

- Cloud benchmarking / “better than N% of repos”
- Claiming SecureVibes free “17 files” is identical to triage routing without evidence
- AST-based nesting in Fast Brain (violates 6.11)
- Replacing scanners with heuristics for secret *content* (gitleaks stays content; gitignore stays heuristic)

## 4. Design decisions

| Decision | Choice |
|----------|--------|
| Headline location | Top of Markdown after title metadata; echo in Rich summary table |
| Lane timings | Best-effort `provenance.fastBrainSeconds` / `llmSeconds` when pipeline can measure; omit if unavailable |
| Clustering | Extend Phase 6.9 cluster key: same normalized file + theme family collapses heuristic+LLM twins; keep highest severity; on severity **tie** prefer `scanner` > **`llm` > `heuristic`** (keep rich LLM text over generic heuristic stubs); set `clusteredCount` |
| Nesting heuristic | Count lines with indent ≥ N spaces/tabs in code-like suffixes; emit `heuristic.deep_nesting` → theme `arch.readability_complexity`. May false-hit indented strings/docstrings — acceptable for Fast Brain v1 |
| Dogfood recipe | Document PatternSorcerer-class compare: scanners + Fast Brain + `--ci`/triage (not `--full`) |

## 5. Exit criteria

- New report opens with a Two-Lane one-liner that matches provenance numbers.
- Twin findings for `.gitignore` / mega-file style pairs collapse to one row when clustering on.
- At least one indent-nesting fixture produces `heuristic.deep_nesting`.
- FAQ/atlas state fair compare recipe + remediation positioning.
- No claim that gate % ≡ SecureVibes security score.

## 6. References

- [phase-6.11 Fast Brain spec](./2026-08-06-phase-6.11-fast-brain-whole-tree-heuristics.md)
- PatternSorcerer report: `…/PatternSorcerer/reports/gate_review_report_review_2026-08-06_2128.md`
- Plan: [../plans/2026-08-06-two-lane-presentation-and-cq-parity.md](../plans/2026-08-06-two-lane-presentation-and-cq-parity.md)
