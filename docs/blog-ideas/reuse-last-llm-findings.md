# Blog idea — Reuse last LLM findings when nothing changed

**Status:** Stub for later (CRC Club / RepoLens product blog)  
**Spec:** [../superpowers/specs/2026-08-05-reuse-last-llm-findings-design.md](../superpowers/specs/2026-08-05-reuse-last-llm-findings-design.md)

## Angle

“Don’t make users pay for a 32B pass twice when the tree didn’t move — and don’t lie with a green empty report either.”

## Outline

1. **The trap:** `--changed` + warm cache → LLM pack 0/N → looks like a clean review.  
2. **Wrong fix:** Pick newest file in `reports/` (skipped runs win).  
3. **Right fix:** Canonical “last successful LLM” snapshot in `.repolens/`; merge fresh scanners; label the report as reused.  
4. **When to force:** `--full` / real edits for a new AI pass.  
5. **Honest confidence:** Carried-forward findings are useful, not a fresh audit.

## Notes to expand later

- Dogfood story on PatternSorcerer (hour-long 32B vs 1s reuse).  
- Screenshot of summary row: `LLM | reused from …`.  
- Tie-in to adaptive fingerprint cache (Phase 5).
