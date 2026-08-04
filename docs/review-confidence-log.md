# Review confidence log (template)

Optional durable record of dual-review gate confidence over time. Copy rows after each gate.

| Date | Ref | Confidence | Counts (C/H/M/L) | Note | Chat / export |
|------|-----|------------|------------------|------|---------------|
| YYYY-MM-DD | sha or wip | NN% | 0/0/0/0 | one-line note | link or n/a |

## How to use

1. After a pre-commit / pre-push dual review, append a row.  
2. Keep this file in-repo if you want history; otherwise keep a private copy.  
3. Do not paste secrets, tokens, or private code into the Note column.

Example:

| 2026-08-04 | 8ff8aa2 | 88% | 0/0/1/1 | Phase 3 scanners gate | chat |
