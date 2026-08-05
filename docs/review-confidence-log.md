# Review confidence log

Durable record of dual-review gate confidence over time.

| Date | Ref | Confidence | Counts (C/H/M/L) | Note | Chat / export |
|------|-----|------------|------------------|------|---------------|
| 2026-08-04 | 6c9cc10 | 78% | 0/0/5/4 | Retroactive Phase 3–4 gate (process miss) | [gate_review_report_2026-08-04.md](./reviews/gate_review_report_2026-08-04.md) |
| 2026-08-04 | 9704834 | 88% | 0/0/1/1 | Phase 3 scanners (chat-only; not exported) | chat |
| 2026-08-04 | feat/guided-review-script WIP | 86% | 0/0/2/2 | Deep coverage + rules registry + guided (pre local merge) | chat |
| 2026-08-04 | 15b2cd9 | 92% | 0/0/0/0 | Docs-only: Phase 5.1/6 designs + enterprise→7 (chat gate) | chat |
| 2026-08-05 | WIP→commit | 88% | 0/0/1/1 | Streamed LLM wait + report stamps/mode/duration; sentinel metrics; Phase 8/9 designs | chat |
| 2026-08-05 | WIP→commit | 88% | 0/0/1/1 | Phase 5.2 themes; reuse last LLM (+ MD bootstrap); CRC About; wall-clock timeout | chat |
| 2026-08-05 | WIP→push | 92% | 0/0/0/0 | FAQ + report Metrics/Coverage formula glossary (docs/UX only) | chat |
| 2026-08-05 | WIP→commit | 90% | 0/0/0/0 | PR1 self-review noise + British English report prose | chat |
| 2026-08-05 | WIP→commit | 90% | 0/0/0/1 | PR3 mega-file splits (cli/llm/pipeline/guided packages); 272 pytest green | chat |

## How to use

1. After a pre-commit / pre-push dual review, append a row **and** keep a report under `docs/reviews/` when shipping.  
2. Do not paste secrets, tokens, or private code into the Note column.
