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
| 2026-08-05 | WIP→commit | 94% | 0/0/0/0 | PR4 try-on-your-repo Low nits + FAQ dogfood hardening pointer | chat |
| 2026-08-05 | WIP→commit | 91% | 0/0/0/0 | FP calibrations via [deep].fp_calibrations; subprocess list-form demote; 278 pytest | chat |
| 2026-08-06 | WIP→commit | 90% | 0/0/1/1 | Phase 6 explain/IDs/diagrams + 6.x design + enterprise triage plan/blog; 17 Phase 6 tests | chat |

## How to use

1. After a pre-commit / pre-push dual review, append a row **and** keep a report under `docs/reviews/` when shipping.  
2. Do not paste secrets, tokens, or private code into the Note column.
| 2026-08-06 | WIP→commit | 91% | 0/0/0/1 | Phase 6.1 Trivy+Checkov plugins; evidence→LLM; 17 tests | chat |
| 2026-08-06 | WIP→commit | 92% | 0/0/0/1 | Phase 6.2 SBOM/licenses/SCA dedupe + LLM guardrails; 38 related pytest | chat |
| 2026-08-06 | WIP→commit | 91% | 0/0/1/1 | Phase 6.3 CI triage routing, provenance, parallel scanners; 58 related pytest | chat |
| 2026-08-06 | WIP→commit | 96% | 0/0/0/0 | UX: LLM summary label for triage bypass; 3 focused tests | chat |
| 2026-08-06 | WIP→commit | 92% | 0/0/0/1 | Phase 6.4 anchored SARIF + GHAS recipe; 7 SARIF tests | chat |
| 2026-08-06 | WIP→commit | 97% | 0/0/0/0 | UTC stamps for MD/JSON/SARIF + shared report_when | chat |
| 2026-08-06 | WIP→commit | 93% | 0/0/0/0 | Phase 6.5 playbook depth + FP calibrations + themes | chat |
| 2026-08-06 | WIP→commit | 94% | 0/0/0/1 | Phase 6.6 methodology + MVP + score-report; 2 pytest | chat |
| 2026-08-06 | WIP→commit | 91% | 0/0/1/1 | Phase 6.7 suppressions; fixed path escape in disable read; 11 pytest | chat |
| 2026-08-06 | WIP→commit | 92% | 0/0/1/1 | Phase 6.7 consistency + feedback calibrations; 8 focused pytest | chat |
| 2026-08-06 | WIP→commit | 93% | 0/0/0/1 | Phase 6.8 pr-summary + annotations; SARIF glob fix; 4 pytest | chat |
| 2026-08-06 | WIP→commit | 91% | 0/0/1/1 | Phase 6.9 usage hints/cluster/verify; 8 pytest; no reachability claims | chat |
| 2026-08-06 | WIP→commit | 92% | 0/0/0/1 | Phase 6.10 packs + azure-sentinel + quickcheck doc; 8 pytest | chat |
