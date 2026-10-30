# Review confidence log

Durable record of dual-review gate confidence over time.

| Date | Ref | Confidence | Counts (C/H/M/L) | Note | Chat / export |
|------|-----|------------|------------------|------|---------------|
| 2026-08-04 | 6c9cc10 | 78% | 0/0/5/4 | Retroactive Phase 3–4 gate (process miss) | local export |
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

1. After a pre-commit / pre-push dual review, append a row. Keep the full export on the maintainer machine. Do not commit it.  
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
| 2026-08-06 | WIP→commit | 96% | 0/0/0/0 | Docs: command-atlas + honest LLM hour-scale timings | chat |
| 2026-08-06 | WIP→commit | 90% | 0/0/1/1 | Phase 6.11 Fast Brain Two-Lane + summary Metrics polish; fixed triage pack from fast inventory | chat |
| 2026-09-05 | 2abe7f7 | 92% | 0/0/0/0 | Wire vacuous pass floors in deep_exec before audit metrics (#21) | chat / .superpowers/sdd/task-3-report.md |
| 2026-09-06 | WIP→commit | 94% | 0/0/0/0 | CI unblock PR #22: docs path for cli package + ruff; remove shadowed transport helpers | chat |
| 2026-09-06 | WIP→commit | 96% | 0/0/0/0 | Wave A docs: #14/#17 specs+plans, Phase 7 checklist, phases.md interrupt queue | chat |
| 2026-09-06 | WIP→commit | 93% | 0/0/0/0 | #14 cross-source SCA dedupe (scanner baseline; gate penalty on unique) | chat |
| 2026-09-06 | WIP→commit | 94% | 0/0/0/0 | #17 MVP gate UX copy + Unique Critical/High (raw) | chat |
| 2026-09-26 | WIP→PR-A | 96% | 0/0/0/0 | Tracker hygiene: Wave C close, #12 refresh, #11 triage (docs only) | chat |
| 2026-09-26 | WIP→PR-B/C/D | 90% | 0/0/1/0 | #15 cost knobs + #16 --git-diff restrict + close #13 | chat |
| 2026-09-27 | WIP→commit | 88% | 0/0/1/1 | Split run_review/_run_mode under High; gitleaks history; CI least privilege + Dependabot/CodeQL | chat |
| 2026-09-30 | WIP→commit | 88% | 0/0/2/0 | Hollow pass stays unanswered; suppressed rows leave Plan to fix; audit ledger | chat |
| 2026-10-01 | WIP→push blocked | 92% | 0/0/0/1 | which-command docs + pass_cache version in keys; nothing committed; main==origin | chat |
| 2026-10-01 | WIP→commit | 93% | 0/0/0/0 | which-command + sonargraph docs; pass_cache version keys; mega-file splits; pack_scope DRY | chat |
| 2026-10-01 | 2102760→push | 91% | 0/0/0/0 | role_packs + journal; override-and-push with 8f2b86d | chat |
| 2026-10-01 | 96624af→push | 88% | 0/0/1/0 | Metis Steps 3–6 + A–E thin MVPs; plan/diff-audit/verify/blast/NA/prefs/attest; dogfood plan chars ~same budget fill | chat |
| 2026-10-06 | WIP→commit | 92% | 0/0/0/0 | Split deep_exec/report_sections under 500; DRY CLI source options vs selfdog …_2054 | chat |
| 2026-10-06 | WIP→commit | 90% | 0/0/0/1 | #86–#89 CLI: journal/resume/blast notes/check SARIF/graph/duplicates/ignore; 0.1.0 prep no tag | chat |
| 2026-10-06 | WIP→commit | 93% | 0/0/0/0 | C3 `graph breakup --omit-edge` preview (no tree edits) | chat |
| 2026-10-06 | WIP→push | 92% | 0/0/0/1 | C4 optional baseline `metrics`; ratchet extras independently | chat |
| 2026-10-06 | WIP→commit | 90% | 0/0/0/1 | C7 git hotspots + vscode thin client; extra baseline measure kept; #86 no role_packs Audit | chat |
| 2026-10-06 | WIP→commit | 89% | 0/0/0/1 | VS Code palette C2–C6 + Zed/IntelliJ READMEs; parked issues #91–#96; #86 Audit running | chat |
| 2026-10-06 | 530898a→push | 91% | 0/0/0/0 | Publish 0.1.0: changelog fold, install pins; no token-cut claim | chat |
| 2026-10-06 | WIP→commit | 91% | 0/0/0/1 | Parked #92–#96: heuristics, Trivy registry, multi-lang graph, arch strict/`*` | chat |
| 2026-10-06 | fa87353→push | 90% | 0/0/1/0 | Hotfix GraphConfig.require_baseline + merge FAILED/SKIPPED/empty-OK semantics | chat |
| 2026-10-06 | c47e755→push | 91% | 0/0/1/1 | Metis slice C: sniff, hybrid P3, journal post-mortem; ahead of origin | chat |
| 2026-10-06 | WIP→push | 96% | 0/0/0/0 | CI: pytest pythonpath + tests/__init__ for `from tests.…` under SAFEPATH | chat |
| 2026-10-09 | WIP→main | 90% | 0/0/0/2 | Robust-product + High fix (pipeline degraded_passes); selfdog clean 0 findings | chat |
| 2026-10-09 | v0.1.1 | 94% | 0/0/0/0 | Version bump + changelog fold; tag for PyPI Trusted Publish | chat |
| 2026-10-09 | WIP→commit | 93% | 0/0/0/1 | M1 adoption: sample report, BYOK docs, SARIF recipe, `repolens audit` | chat |
| 2026-10-10 | WIP→commit | 92% | 0/0/0/1 | M2 deliverables: evidence pack, executive summary, diff-audit md/html | chat |
| 2026-10-10 | WIP→commit | 91% | 0/0/0/1 | M3 DX: fix / blast-radius / view / portfolio | chat |
| 2026-10-10 | WIP→commit | 90% | 0/0/0/1 | M4 ecosystem: workspace graph, overlays, VS Code panel, Docker | chat |
| 2026-10-10 | v0.1.2 | 92% | 0/0/1/0 | M5 release: 0.1.2 + GHCR workflow + first-week recipe; unpinned docker/* actions (Med) | chat |
| 2026-10-10 | WIP→push | 94% | 0/0/0/0 | Dependabot #97/#98/#99: checkout@v7, setup-python@v7, tree-sitter&lt;0.27; 96 graph tests | chat |
| 2026-10-10 | WIP→push | 92% | 0/0/0/2 | which catalog + sanitized argv provenance; URL userinfo stripped; 118 related pytest | chat |
| 2026-10-10 | WIP→push | 91% | 0/0/0/2 | Selfdog hygiene: HEALTHCHECK, cycle-tree split, mega-file and 80-line spans; 69 related pytest | chat |
| 2026-10-11 | industrial-0.1.3 | 91% | 0/0/1/1 | 0.1.3 provenance query strip, wheel SHA-256, image sha256sum; pip deps and Docker Semgrep extra stay unhashed; not tagged | chat |
| 2026-10-11 | WIP→commit | 94% | 0/0/0/0 | Overlay scanners: extract Issue builders so fintech/healthtech clear deep-nesting; 5 overlay pytest | chat |
| 2026-10-13 | WIP→commit | 84% | 0/0/0/1 | Post-0.1.3: hash-locked Semgrep/Checkov, learn notes, clean-code heuristics; scanners extra still unhashed; blog drafts left out | chat |
| 2026-10-13 | WIP→commit | 90% | 0/0/0/1 | Internal notes leave the published tree; older commits on origin still contain plans, recipes, and one review | chat |
| 2026-10-18 | WIP→push | 90% | 0/0/0/0 | Fast Brain signature objects and boolean splits; selfdog 2026-10-18 0/0/0/0; version stays 0.1.3 | chat |
| 2026-10-21 | WIP→commit | 92% | 0/0/0/0 | Report title names the reviewed project; one magic-number Low per file; local commit only | chat |
| 2026-10-21 | 6a0efd5→push | 92% | 0/0/0/0 | Same report-identity commit pushed; optional provenance fields; git branch via list-form rev-parse | chat |
| 2026-10-21 | issue-140→push | 92% | 0/0/0/1 | Opt-in RSS ceiling exits 2 only before the model; 32B notice does not name a cloud model or stop the run | chat |
| 2026-10-21 | overlap→push | 91% | 0/0/0/1 | Scanners overlap Fast Brain; supply chain waits for the scanner future; duration only when a tool ran | chat |
| 2026-10-21 | review-time→push | 91% | 0/0/0/1 | Per-pass first-token rows; plan uses the last same-model sample; coverage closure is not the plan sample | chat |
| 2026-10-21 | memory-footprint→push | 91% | 0/0/0/1 | One read for per-file checks; bounded excerpt and FTS; workers 0 leaves one core free | chat |
| 2026-10-23 | v0.1.4 | 94% | 0/0/0/0 | Release from main: version bump, changelog move, README links are GitHub blobs; benchmark branch left out | chat |
| 2026-10-23 | docs→push | 95% | 0/0/0/0 | Linked docs install 0.1.4; local learning matches the store; missing design filenames removed | chat |
| 2026-10-23 | phases-sync | 96% | 0/0/0/0 | Issue #12: phases.md names 0.1.4, closed trackers, and the open benchmark and DSPy tracks | chat |
| 2026-10-23 | dspy-local | 93% | 0/0/0/1 | Instruction file loads on review; untrusted project toml cannot set it; live compile stays manual. Local main only | chat |
| 2026-10-23 | dspy-docs→push | 94% | 0/0/0/1 | Docs name the instruction file as done. A live optimizer call stays manual. Push is to main, not a master branch | chat |
| 2026-10-23 | dspy-compile→push | 93% | 0/0/0/1 | COPRO runs only when dspy is installed by hand. CI covers the writer, the metric, and the model fields. Review still does not import DSPy | chat |
| 2026-10-23 | explain-span→commit | 94% | 0/0/0/1 | Line-span explain reads the function and skips the model. Closure timing is a helper. Step list stops at 12. Local main only | chat |
| 2026-10-24 | ci-schedules→commit | 95% | 0/0/0/0 | Docs only. Pull request stays scanners-only. Weekly audit is a separate scheduled job. Keys stay in each host's secret store | chat |
| 2026-10-30 | hygiene→commit | 94% | 0/0/0/0 | Explain logs a parse or read failure at debug. Resume and retry tests share one stand-in. Local main only | chat |
| 2026-10-30 | ui-bench→commit | 93% | 0/0/0/1 | Local-UI exposure demotes when no network or IPC path. CI benchmark row is a measured zero. Model row writer stays out. Local main only | chat |
