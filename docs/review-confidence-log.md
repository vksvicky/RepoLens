# Review confidence log

Durable record of dual-review gate confidence over time.

| Date | Ref | Confidence | Counts (C/H/M/L) | Note | Chat / export |
|------|-----|------------|------------------|------|---------------|
| 2026-08-04 | 6c9cc10 | 78% | 0/0/5/4 | Retroactive Phase 3–4 gate (process miss) | [gate_review_report_2026-08-04.md](./reviews/gate_review_report_2026-08-04.md) |
| 2026-08-04 | 9704834 | 88% | 0/0/1/1 | Phase 3 scanners (chat-only; not exported) | chat |

## How to use

1. After a pre-commit / pre-push dual review, append a row **and** keep a report under `docs/reviews/` when shipping.  
2. Do not paste secrets, tokens, or private code into the Note column.
