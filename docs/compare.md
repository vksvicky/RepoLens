# RepoLens vs coding-agent harnesses (compare)

**Status:** public positioning (2026-10-01)  
**Related:** [metis-agent-comparison.md](./design/metis-agent-comparison.md) · [which-command.md](./which-command.md) · [repolens-vs-appsec-tools.md](./design/repolens-vs-appsec-tools.md)

## Bottom line

**We audit. They edit.**

RepoLens is a **zero-infra dual-review / audit CLI**: scanners + Fast Brain + Slow Brain (P1→P2→P3) → gate report. It does **not** rewrite your tree until tests pass.

Coding-agent harnesses (for example [Metis](https://metisagent.tech/compare/)) plan, edit, test, and self-heal. That is a different product category. RepoLens borrows **mechanisms** (compaction, journals, verification language) and refuses **product shape** (autonomous edit loops, implementer agents, video evidence).

## Operator vocabulary

| Word | Meaning in RepoLens | Command |
| --- | --- | --- |
| **Plan** (recon) | Inventory + pack forecast + optional scanners — **no LLM synthesis** | `repolens plan` (pack preview). Closest scanner path: `--scanners-only`. **Not** `--dry-run` (inventory dump only; semantics protected). |
| **Audit** (synthesis) | Slow Brain role passes + optional verify | `repolens review --deep` / recommended full-audit recipes in [which-command.md](./which-command.md) |

Progress copy may say `Plan (Fast Brain)` / `Audit (Slow Brain)` with the same meanings.

## What we refuse

- Autonomous edit / self-heal loops  
- Recursive “implementer” agents and worktree builders  
- Marketing “~60% token cut” claims without measured chars-in/out on your machine  
- Overloading `--dry-run` with scanners or forecast tables  

## What we adopt (mechanisms)

| Mechanism | RepoLens |
| --- | --- |
| Role-aware packing | `[deep] role_packs` |
| Interrupt visibility | `.repolens/journal.jsonl` |
| Pre-flight forecast | `repolens plan` |
| Verification honesty | `--verify-findings` → Grounded / Suspect + gate penalty |
| Change-set + neighbours | `--git-diff` with blast-radius expansion |
| Attestation | `ProvenanceBlock` dirty tree, digests, template + journal tip |

## Honest measurement

Enable `role_packs`, run `repolens plan --role-packs` vs `--no-role-packs`, then compare journal `chars_in` / `chars_out` after a real Audit. Claim a cut only from that baseline — never from Metis marketing numbers.
