# Phase 6 — Issue explain + foolproof diagrams (design)

**Status:** Design approved (Approach 1 §2)  
**Date:** 2026-08-04  
**Depends on:** Phase 5.1 deep hardening (honest metrics + quieter reports)  
**Renames:** Former Phase 6 enterprise CI → **Phase 7**

## 1. Problem

Gate reports list many findings; users need a **deep dive on one issue**: detailed explanation, possible solutions, and a diagram. Past diagram generation often failed and aborted the flow — that must never happen.

## 2. Goals

1. Stable + per-run issue IDs on every finding.  
2. Global explain toggle + optional UUID list.  
3. `repolens explain <uuid>` and `repolens review --explain <uuid>[,…]`.  
4. Explain artifact: problem, impact, 2–3 solutions, diagram, next step.  
5. **Foolproof diagrams:** Mermaid primary → validate → one repair → textual fallback; optional image never blocks exit 0.

## 3. Identity (hybrid)

| Field | Type | Meaning |
|-------|------|---------|
| `stableId` | UUID | Derived (UUID v5 / namespace hash) from normalized `(category, file, title)` |
| `runId` | UUID v4 | Unique per finding row in this report |

CLI accepts either. Prefer exact `runId` match in the latest report; else latest `stableId`.

## 4. Feature toggle

```toml
[explain]
enabled = true
diagram = "mermaid"       # mermaid | off
render_image = "auto"     # auto | always | never
```

- `enabled=false` → explain commands fail with guidance; review still emits IDs.  
- `--explain uuid[,uuid…]` on review runs deep-dives after the report is written (when enabled).

## 5. Commands & lookup

- `repolens explain <uuid> [--path ROOT] [--out DIR] [--no-diagram] [--render-image]`  
- Resolve issue from: `--out` / config `report_dir` latest `gate_review_report_*.json`, or `.repolens/last_report.json` pointer written by review.

## 6. Explain artifact

Write `reports/explain_<id>_<date>.md` (+ optional JSON) containing:

1. Problem restatement + evidence (file excerpt)  
2. Impact  
3. Possible solutions (2–3, with trade-offs)  
4. Diagram (Mermaid and/or textual fallback)  
5. Recommended next step  

LLM path uses the same 4-layer spine; **always** write a file (degraded text OK).

## 7. Foolproof diagram spine

1. Ask for constrained Mermaid (`flowchart` / `sequence` only; size limits).  
2. Validate (parser / `mmdc --check` if present / strict structural checks).  
3. One micro-repair on failure.  
4. Still invalid → ASCII/structured textual diagram + `diagram.mermaid_invalid`.  
5. Optional PNG/SVG only if Mermaid valid and renderer available; on render failure keep Mermaid + `diagram.render_skipped`.  
6. Process exit **0** unless issue UUID not found / explain disabled.

## 8. Testing & acceptance

- Unit: stableId stability; invalid Mermaid → fallback; render failure does not raise.  
- Integration: mocked LLM explain writes MD with solutions + diagram section.  
- Manual: explain a PatternSorcerer heuristic UUID end-to-end.

## 9. Non-goals

- Auto-explain every issue in a full audit  
- Hosted UI  
- Guaranteed image beauty  

## 10. Related

- [2026-08-04-phase-5.1-deep-hardening-design.md](./2026-08-04-phase-5.1-deep-hardening-design.md)  
- [phase-7-enterprise-ci-and-report-delivery.md](../../design/phase-7-enterprise-ci-and-report-delivery.md)  
