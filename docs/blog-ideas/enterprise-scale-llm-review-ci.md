# Why enterprises cannot LLM-scan 10,000 files on every PR — and how RepoLens resolves it

**Status:** Draft for CRC Club / RepoLens product blog  
**Audience:** Platform / AppSec / engineering leaders evaluating AI code review  
**Related design:** [phase-6.x-scanner-depth-ci-gates-and-credibility.md](../design/phase-6.x-scanner-depth-ci-gates-and-credibility.md) · [plan](../superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md)

---

## The issue

AI code review demos look great on a laptop repo. Then a platform team asks a simple question:

> We have a monorepo with **10,000+** files. How long will this take on every pull request?

A realistic dogfood signal: a **~200-file** project, **`--changed --deep`**, **32 files** in the LLM pack, local **32B** model — finished in about **seventy minutes**. Not because inventory was slow. Scanners finished in seconds with zero findings. The clock was three sequential deep LLM passes (~80–90k characters each), each spending roughly ten minutes waiting for the first token, then streaming a long structured report.

Extrapolate that shape naively to a large enterprise tree and you do not get “a bit slower.” You get **days of serial LLM time**, or a cloud bill that Finance will reject, plus merge queues that never clear.

Large organisations already know this. They do **not** run full semantic analysis of every file on every commit. They run:

1. **Fast deterministic tools** on the **diff** (and sometimes a small blast radius).  
2. **Policy gates** on those results.  
3. **Heavy analysis** on a schedule or release boundary, scoped to a service or risk slice.

If an AI review product ignores that operating model, it will never become a required check. Champions get blamed for pipeline latency; the tool gets uninstalled.

---

## What “waiting” really costs the organisation

| Cost | Why it matters |
|------|----------------|
| Merge SLA | PR checks are expected in minutes, not hours |
| Engineer time | Blocked merges compound across hundreds of developers |
| Infra / GPU / API spend | Full-repo context × every PR does not scale linearly — it explodes |
| Trust | An hour of narrative for mostly Medium/Low noise trains teams to ignore the tool |
| Compliance buyers | They still need deterministic, auditable scanner evidence for many programmes |

So the question is not “how do we make a 32B model finish 10k files faster?”  
It is “how do we **never put 10k files in the LLM pack for CI**?”

---

## How we resolve it

RepoLens is positioned as a **due-diligence and remediation layer**, not a Checkmarx replacement. Deployment splits into two paths.

### Path A — CI / pull request (must be cheap)

**Deterministic scanners own the gate.** Semgrep, Gitleaks, OSV, and (in Phase 6.x) Trivy/Checkov run on changed paths. The build fails on severity thresholds from **scanner** evidence.

**Triage routing for the LLM:**

```text
diff → scanners on changed paths
         │
         ├─ no hits (after suppressions) → pass/fail from scanners only
         │                                LLM bypassed entirely
         │
         └─ hits → LLM only on the cited file / function / snippet
                   → impact + fix example
                   gate severity still from scanners
```

`--changed` alone is not enough. It only shrinks the file list. **Triage** decides whether the model runs at all, and on how many tokens.

**Anchored SARIF** (when exporting to GHAS/Sonar): never ship raw LLM line numbers. Resolve an exact quote in the file first, or omit the result from SARIF. Hallucinated locations break Security tabs and destroy trust.

**Suppressions** (`.repolens-ignore` / disable comments): dismissed findings must not nag on every subsequent push, or developers will mute the entire check.

### Path B — Release / due diligence / scheduled audit (may be slow)

Full dual review (`security → reliability → architecture`), deep multi-pass, and per-issue explain are appropriate for:

- Pre-release or M&A-style audits  
- Nightly jobs on a **bounded scope** (one service, one package, hot paths)  
- Human-readable Markdown/PDF with code examples  

Waiting overnight is fine. Waiting on every PR is not.

### Hard product limits (enterprise hygiene)

Ship and document ceilings so the tool fails safe:

- Max files / max characters per LLM pass  
- `--ci` (or equivalent) defaults to triage + scanners-as-gate  
- Path allowlists for monorepos (`services/checkout/**`)  
- Many small project configs, not one mega-review of the whole tree  

---

## What to tell a customer

> RepoLens does not LLM-scan your 10,000-file monorepo on every PR. Deterministic scanners cover the diff and own the gate. RepoLens explains and remediates what those scanners (and scoped audits) surface, and runs deeper dual reviews on a schedule or release boundary. That is how you get architecture and reliability narrative without destroying merge velocity.

Headline positioning that survives enterprise scrutiny:

1. **The tool that audits whether you are using SAST correctly** — including flagging missing Dependabot, CodeQL, Semgrep, or secret scanning.  
2. **Remediation, not only detection** — impact, fix plans, and code examples that raise fix rate / lower MTTR.  
3. **CI-safe hybrid** — scanners gate; triage-routed LLM explains hits; anchored SARIF never invents line numbers.

---

## Roadmap pointer

The detailed slices live under Phase **6.x** (before enterprise CI packaging in Phase 7):

| Slice | Enterprise outcome |
|-------|-------------------|
| 6.1–6.2 | Trivy/Checkov + SBOM; scanner-owned dependency facts |
| **6.3** | Triage routing + scanners-as-gate + provenance |
| **6.4** | Anchored SARIF handoff to GHAS/Sonar |
| 6.6 | Benchmarks led by **remediation rate / MTTR**, not F1 alone |
| **6.7** | `.repolens-ignore` so dismissed findings stay dismissed |

Implementation plan: [2026-08-06-enterprise-ci-triage-routing.md](../superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md).

---

## Closing

Enterprises can afford RepoLens on large codebases only if **LLM pack size stays small and event-driven**. Inventory can see 10k files. Scanners can sweep a diff in minutes. The model must see **hits and risk slices**, not the whole company on every push.

That is not a limitation of the product vision. It is the difference between a demo and a deployable AppSec programme.
