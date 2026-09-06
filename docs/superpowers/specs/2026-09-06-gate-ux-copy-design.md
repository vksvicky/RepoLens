# Gate UX & copy alignment (design)

**Status:** Approved for plan  
**Date:** 2026-09-06  
**Issue:** [#17](https://github.com/vksvicky/RepoLens/issues/17)  
**Parent:** [#13](https://github.com/vksvicky/RepoLens/issues/13) (Gate honesty interrupt)  
**Scope:** Wave A2 Copy MVP (Split scope; `#17b` local UI calibrations deferred to post-Phase 7)  
**Preceded by:** [#14](https://github.com/vksvicky/RepoLens/issues/14) (Cross-source SCA dedupe)  
**Followed by:** [#3](https://github.com/vksvicky/RepoLens/issues/3) (Phase 7 Enterprise CI/CD)

---

## 1. Problem

Users and CI review consumers frequently misinterpret the single `Confidence` percentage in RepoLens reports and CLI output:
1. **Misinterpreted as "% secure":** A gate confidence score of 39% or 75% is often misread as "the application is 39% secure" or "the codebase failed security", even when the security band is 80% and the lower score is driven by missing architecture coverage or non-security penalties.
2. **Dual-review confusion:** Dual-review gate policies typically require high review adequacy (e.g. ≥70%), but teams confuse adequacy with CleanVibes-style clean-bill-of-health posture metrics.
3. **Advisory count disconnect:** After #14 collapses duplicate advisories across scanners and LLM passes, users need immediate visibility that raw findings across tools were synthesized into unique actionable findings (e.g. `2 unique (4 raw across tools)`).

---

## 2. Scope & Split Decision

Per the approved program plan, Issue #17 is **split** into two discrete milestones:

- **Wave A2 (#17 MVP - This Spec):**
  - CLI & Report summary copy alignment matching `docs/faq.md` (British English).
  - Explicit one-liner clarifying that gate confidence measures review-package adequacy (checklist coverage + open severity penalties), not a "% secure" rating.
  - Surface unique vs raw Critical/High finding counts (`Unique Critical/High: N (M raw)`) feeding directly from #14 deduplication data.
- **Post-Phase 7 start (#17b):**
  - Tracked as a pinned checklist / child task on GitHub issue #17.
  - Adds `attack_surface=local_ui` detection for desktop / local applications.
  - Soft demotions / clustering for repetitive local UI "data exposure in memory/storage" Medium findings.

---

## 3. Goals

1. **FR1 — FAQ-aligned CLI one-liner:** Add an unambiguous one-liner beneath the metrics table in CLI console output:
   `Gate confidence reflects review-package adequacy (checklist coverage + open severity penalties), not a "% secure" score.`
2. **FR2 — Markdown report callout:** In the generated Markdown report header and summary table, embed an alert note reiterating that confidence evaluates audit completeness and open findings, pointing to `docs/faq.md`.
3. **FR3 — Surface unique vs raw Critical/High:** Present finding counts clearly in both CLI and Markdown summaries:
   - When raw findings exceed unique findings: `Open Critical/High: N unique (M raw across tools)`
   - When no deduplication occurred: `Open Critical/High: N`
4. **FR4 — British English consistency:** Standardize user-facing copy to British English (`penalised`, `behaviour`).

---

## 4. Non-goals

- Changing the numerical formula of `compute_audit_metrics` (already hardened in #21 and #14).
- Altering `--fail-on` behaviour (which remains strictly severity-based, e.g. failing on HIGH or CRITICAL).
- Local UI attack surface tagging (deferred to #17b).

---

## 5. User Experience & Design Specifications

### 5.1 CLI Console Output

In `src/repolens/cli/` (when printing summary tables after `repolens review` or `repolens sentinel`):

```text
── Audit Metrics ──────────────────────────────────────────────────────────────
Gate confidence:           75%
Security audit:            80%
Reliability audit:         75%
Architecture audit:        75%

Open Critical/High:        1 unique (3 raw across scanner and LLM layers)
Total findings:            4 unique (6 raw)

* Gate confidence reflects review-package adequacy (checklist coverage + open severity penalties), not a "% secure" score.
───────────────────────────────────────────────────────────────────────────────
```

### 5.2 Markdown Report Header (`reports/gate_review_report_*.md`)

Beneath the primary metadata block in `render_report_markdown`:

```markdown
> [!NOTE]
> **Audit Confidence & Gate Interpretation**  
> Gate confidence (**75%**) measures the adequacy and completeness of this review package (checklist coverage minus open severity penalties). It is **not** a "% secure" posture score or an assurance of zero vulnerabilities. See [docs/faq.md](docs/faq.md) for metric definitions.
```

### 5.3 Markdown Summary Section

In the summary table:

| Metric | Count |
|--------|-------|
| Critical | 0 |
| High | 1 *(3 raw across tools)* |
| Medium | 2 |
| Low | 1 |
| **Unique Critical/High** | **1 (3 raw)** |

---

## 6. Schema & Presentation Interface

Data is retrieved directly from `FindingReport`:
- `report.confidence`: Gate confidence percentage
- `report.rawCriticalHighCount`: Raw count populated by #14
- `report.rawTotalFindings`: Raw total count populated by #14
- `report.summary`: Deduplicated unique counts

When `report.rawCriticalHighCount is not None and report.rawCriticalHighCount > unique_crit_high`:
- Render the dual notation: `f"{unique_crit_high} unique ({report.rawCriticalHighCount} raw across tools)"`.
Otherwise:
- Render standard count: `f"{unique_crit_high}"`.

---

## 7. Testing Strategy (TDD)

1. **CLI rendering snapshot test:**
   - Verify terminal formatting includes the FAQ-aligned one-liner.
   - Verify `Unique Critical/High: N (M raw)` renders when raw count exceeds unique count.
2. **Markdown report snapshot test:**
   - Verify the `[!NOTE]` alert appears in the generated Markdown report.
   - Verify the summary table reflects unique and raw counts accurately.
3. **No-dedupe baseline test:**
   - When raw count equals unique count, output stays clean (`Open Critical/High: 1`).

---

## 8. Exit Criteria

1. CLI output displays the review-package adequacy one-liner and unique vs raw counts.
2. Markdown reports render the explanatory note alert.
3. No user can reasonably read "39% gate confidence" as "the repository is 39% secure".
4. #17b is pinned on GitHub issue #17 as a follow-up task.
