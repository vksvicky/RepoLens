# Phase 6.x — Scanner depth, CI gates & credibility (design)

**Status:** In progress (6.1–6.2 implemented; 6.3+ remaining)  
**Date:** 2026-08-06  
**Depends on:** Phase 6 (issue explain + diagrams — complete), Phase 3 scanners, Phase 5.1 metrics  
**Inserts before:** Phase 7 (enterprise CI/CD & report delivery)  
**Does not modify:** [phase-6-issue-explain-diagrams.md](./phase-6-issue-explain-diagrams.md) (Phase 6 stays closed)

**Inputs synthesised from:**

- [repolens-vs-appsec-tools.md](./repolens-vs-appsec-tools.md) (in-repo comparison)
- External references (2026-08-06): `RepoLens_Comparison_Reference.md`, `repolens_comparison_and_strategy.md`, `repolens-competitive-analysis.md`

**ASPM stance (approved):** thin handoff only — SARIF/SBOM export + recipes for GHAS/Sonar/external portals. **No** RepoLens-hosted ASPM, SSO, or compliance portal.

**Design corrections (2026-08-06 review):** SARIF must be **anchored** (no raw LLM line numbers); CI must use **triage routing** (LLM only on scanner hits in the diff); suppressions via **`.repolens-ignore` / disable comments**; SCA graph reasoning is **scanner-only**; benchmarks must lead with **remediation rate / MTTR**, not only P/R/F1.

---

## 1. Problem

Phase 6 closed the **explain / diagram** gap. Competitive analysis still shows RepoLens **behind** on product debt that blocks “use with (not instead of) your SAST/SCA stack” credibility:

| Debt | Today | Target in 6.x |
|------|--------|----------------|
| Containers / image CVEs | Missing | Trivy plugin |
| IaC policy | LLM comments only | Checkov + Trivy misconfig |
| SBOM / licenses / SCA depth | OSV only | SBOM + license summary; **LLM must not invent dep graphs** |
| ASPM / portals / SSO | None | Anchored SARIF (+ SBOM) + ingest recipes (no SaaS) |
| Deterministic CI gates | LLM probabilistic; scanners optional | Scanners gate; **triage-routed** LLM narrative on hits only |
| Playbook category gaps | SSRF, path traversal, XXE, … unnamed | Explicit sentinel checklist + evidence-first |
| Trust / provenance | Thin | Source tags; versions; **suppressions so findings don’t nag** |
| Public credibility | No benchmark | Methodology + **remediation-rate** headline metrics |

Phase 7 remains **Jenkins/CircleCI/email/dashboard delivery**. 6.x makes the **signal and gate** trustworthy before that packaging work.

---

## 2. What we already have (do not rebuild)

- Plugins: Semgrep, gitleaks, OSV ([scanners.md](../scanners.md))
- Merge into FindingReport; `--scanners-only`; `--fail-on` / Action inputs (confirm & harden in 6.3)
- FP calibrations (`[deep].fp_calibrations`); Phase 5.1 confidence metrics; Phase 5.2 themes
- Playbooks already say LLM does **not** replace Dependabot/CodeQL/Semgrep — keep and strengthen
- Phase 6: `stableId` / `runId`, `repolens explain`

---

## 3. Phase slices (Approach 1 — approved)

Ship in order. Each phase has its own exit criteria and can land as one or more PRs.

### Phase 6.1 — Trivy + Checkov plugins

**Status:** Implemented (2026-08-06) — FS/IaC adapters; opt-in enabled list  
**Plan:** [2026-08-06-phase-6.1-trivy-checkov-plugins.md](../superpowers/plans/2026-08-06-phase-6.1-trivy-checkov-plugins.md)

**Goal:** Deterministic containers, filesystem/deps (via Trivy), and IaC policy evidence in the same report as Semgrep/gitleaks/OSV.

| Item | Notes |
|------|--------|
| `trivy` plugin | Pinned `trivy fs` (vuln + misconfig + secret); SHA-256 archives |
| `checkov` plugin | Pip pin in `checkov-venv`; failed_checks → Issues |
| Report merge | Categories `trivy` / `checkov`; soft-skip if missing |
| LLM pack | `format_scanner_evidence_for_prompt` prefix on deep/single-shot |
| Docs | scanners.md + example.toml opt-in |

**Exit:** `repolens plugins install trivy checkov` (or `all`) works on supported platforms; findings appear in Markdown/JSON; missing tools never break LLM review unless `--require-scanners`. → **Met** (image registry auth matrix still out of scope)

**Out of 6.1:** Full image registry auth matrix; paid Trivy/Checkov cloud features.

---

### Phase 6.2 — SBOM, licenses & SCA enrichment

**Status:** Implemented (2026-08-06) — CycloneDX via Trivy; SPDX still out of scope  
**Plan:** [2026-08-06-phase-6.2-sbom-licenses-sca.md](../superpowers/plans/2026-08-06-phase-6.2-sbom-licenses-sca.md)

**Goal:** Procurement-friendly inventory without claiming enterprise reachability SCA — and **without LLM dependency-graph hallucinations**.

| Item | Notes |
|------|--------|
| SBOM export | CycloneDX from Trivy (`sbom.cdx.json` beside report) |
| License summary | `supplyChain.licenses` + notes; Markdown **Supply chain** |
| OSV + Trivy SCA | Dedupe by advisory+package hint; prefer `osv` |
| **Scanner owns the graph** | Vulnerable package / CVE facts come **only** from Trivy/OSV JSON. LLM must **not** reason over lockfile resolution trees |
| **LLM role for SCA** | Remediation advice from scanner facts only; never invent reachability |
| Prompt / schema guardrails | Evidence prefix + `SupplyChainBlock`; playbook/FAQ |
| Reachability | Only if a **scanner field** provides it; otherwise omit |

**Exit:** SBOM + license section available; SCA findings in the report are traceable to scanner JSON; FAQ + playbook state LLM does not determine dep reachability. → **Met**

**Out of 6.2:** Auto-open Dependabot-style bump PRs; proprietary vuln intel feeds; LLM-as-SCA-engine; SPDX export.

---

### Phase 6.3 — Deterministic CI gates, triage routing & provenance

**Implementation plan:** [2026-08-06-enterprise-ci-triage-routing.md](../superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md) · **Blog:** [enterprise-scale-llm-review-ci.md](../blog-ideas/enterprise-scale-llm-review-ci.md)

**Goal:** CI hard-gates on **scanner** evidence; LLM is never the sole production gate; PR runs stay affordable via **triage routing** (not “stuff the whole repo into the model”).

#### Triage routing architecture (required for CI / PR mode)

```text
diff → scanners on changed paths (Semgrep / Trivy / gitleaks / OSV / …)
         │
         ├─ no scanner hits (after suppressions) → FAIL/PASS from scanners only
         │                                         LLM **bypassed entirely**
         │
         └─ hits → for each hit (or clustered hit):
                      LLM only on the cited file/function/snippet
                      → impact + fix example (narrative)
                   gate severity still from scanner findings
```

| Item | Notes |
|------|--------|
| Scanners default-on for `sentinel` | Opt-out still possible; playbook already prefers Semgrep for injection |
| **`--ci` / PR recipe** | Default: triage routing on; LLM off when scanners clean; LLM scoped to hit snippets when not |
| Gate clarity | Harden `--fail-on`, `--scanners-only`, Action `fail-on`; document “scanners gate, LLM explains” |
| Parallel scanner orchestration | Run enabled scanners concurrently on the diff/pack |
| Finding source tags | `source = scanner \| heuristic \| llm`; CI gates should prefer `scanner` |
| Report provenance | Model id, scanner versions, ruleset/config ids, RepoLens version, git SHA |
| Diff + triage (not `--changed` alone) | `--changed` selects files; **triage** decides whether the LLM runs at all and on which snippets |
| Budget honesty | Aim for practical PR latency; do **not** claim a hard “&lt;5 minutes” SLA — document typical path: scanners-only when clean |
| Policy-lite config | Paths, required scanners, severity floor — not full enterprise policy engine |

**Exit:** Action/docs show required check failing on scanner High; clean PR → no LLM call; hit → LLM only on snippet(s); provenance + source tags in report.

**Out of 6.3:** Push protection; SSO; Jenkins/CircleCI deep recipes → Phase 7; full-repo LLM on every PR.

---

### Phase 6.4 — Thin ASPM handoff (anchored SARIF + recipes)

**Goal:** Drop findings into GitHub Security tab / Sonar / other ingest **without breaking UIs** via hallucinated locations.

#### SARIF hallucination trap (must fix before export)

SARIF consumers (GHAS, Sonar) expect **exact** path + line (+ column). LLMs routinely off-by-one or invent ranges. Exporting raw LLM `file:line` will mis-highlight or drop findings.

#### Verification & Anchor (required before any SARIF write)

1. Finding must include an **anchor quote** (exact substring from the file) and/or come from a scanner that already has verified locations.  
2. Deterministic **anchor resolve** (Python): literal search (and optional light AST/node match) in the cited file to compute the real start/end line (and column when feasible).  
3. Prefer **scanner locations** when `source=scanner` (already trusted).  
4. If anchor cannot be resolved → **omit from SARIF** (keep in Markdown report with a “location unverified” note) — never emit guessed lines to GHAS.  
5. Unit tests: known snippet → correct line; wrong quote → excluded from SARIF.

| Item | Notes |
|------|--------|
| Anchor schema | `anchorQuote` (+ optional `anchorContext`) on issues destined for SARIF |
| `repolens.sarif` / export path | Runs Verification & Anchor; only emits verified results |
| SBOM artifact | Wire 6.2 output into CI upload recipes |
| Recipes | GHAS code scanning upload, Sonar external issues, generic ASPM ingest |
| Optional SARIF **import** | Ingest CodeQL/Semgrep SARIF (locations already trusted) — stretch |

**Exit:** SARIF export never includes unverified LLM line numbers; GHAS recipe documented; Markdown may still show unverified LLM locations with a clear flag.

**Out of 6.4:** ASPM product, compliance dashboards, org SSO; “best effort” SARIF without anchoring.

---

### Phase 6.5 — Playbook depth & calibration

**Goal:** Close cheap, high-value **checklist** gaps vs CodeQL/Checkmarx defaults; strengthen evidence-first behaviour. Not a new SAST engine.

| Add / expand in `security.md` (and rules defaults) | Why |
|-----------------------------------------------------|-----|
| SSRF | Cloud-native prevalence; named in competitors |
| Path traversal / Zip Slip | CWE-22; currently unnamed |
| XXE / XML attacks | CWE-611 |
| NoSQL injection | Named “SQL” only today |
| ReDoS | Often missed by LLM unless named |
| Log injection / forgery | Named gap |
| Insecure randomness (PRNG) | Under crypto today |
| JWT / token pitfalls | Expand auth (alg=none, missing exp, weak secret) |
| Rate limiting / resource exhaustion | Sec ∩ reliability |
| Supply-chain integrity | Unpinned Actions, download-without-integrity (beyond CVE list) |
| Optional CWE / OWASP fields | Compliance readers |

Also:

| Item | Notes |
|------|--------|
| Evidence-first prompting | Prefer scanner evidence; LLM invents only with strong code proof |
| More FP calibrations | Test-only secrets, intentional vuln examples, etc. |
| Architecture playbook | Explicit “cite Trivy/Checkov when present” for IaC/containers |

**Exit:** Playbooks/rules updated; at least one new calibration + tests; FAQ lists expanded categories without claiming CodeQL parity.

**Out of 6.5:** Mobile-only packs (optional later domain pack). Azure Sentinel/SOAR → **6.10**.

---

### Phase 6.6 — Public benchmark & credibility

**Goal:** Defensible, publishable methodology whose **headline** matches RepoLens’s value prop: developers **fix** issues faster because of explanation + code examples — not only raw detection P/R.

#### Headline metrics (required)

| Metric | Why |
|--------|-----|
| **Remediation rate** | % of true positives that a blinded developer (or timed study) actually fixes / accepts a correct fix for within a fixed window |
| **MTTR (mean time to remediate)** | Wall-clock from first seeing the finding to a correct fix (or “understands how to fix”) vs Semgrep/CodeQL-only baselines |
| **% auto-fix / suggested-fix applied** | Where a code example is offered: how often reviewers apply or lightly adapt it (study or instrumented dogfood) |

Detection metrics (Precision / Recall / F1), variance, and actionability scores remain **supporting** — necessary but not the marketing lead. Narrative to preserve: *Semgrep finds 100, team fixes 10; RepoLens+scanners finds 80, team fixes 75 because of examples* → RepoLens wins on remediation even if recall trails.

| Item | Notes |
|------|--------|
| Methodology doc | Pre-register corpora, hit definition, configs, **remediation study protocol** |
| Corpora (MVP) | OWASP Benchmark and/or Juliet subset + small real-CVE set + qualitative Juice Shop/WebGoat |
| Detection metrics | P / R / F1; variance across runs; actionability (1–5) |
| **Remediation metrics** | Remediation rate, MTTR, suggested-fix apply rate (primary story) |
| Comparators | Semgrep CE + CodeQL; RepoLens configs broken out (scanners-only / LLM-only / combined / triage CI) |
| Publish path | `docs/` methodology + results; honest losses included |

**Exit:** Methodology published with remediation metrics defined; at least one MVP table that includes remediation or timed-fix evidence (even partial), not P/R alone.

**Out of 6.6:** Leading only with synthetic-suite F1; claiming SAST superiority on detection depth alone.

---

### Phase 6.7 — Suppressions, local feedback & Critical self-consistency

**Goal:** Stop **nagging** across commits/PRs; improve calibration with local-only signals; optional Critical agreement pass.

#### State management (required — “Won’t Fix” must stick)

If an architectural smell or LLM finding is dismissed on Monday, re-flagging it on every Tuesday push will get RepoLens uninstalled.

| Mechanism | Notes |
|-----------|--------|
| **`.repolens-ignore`** | Project file: stable finding keys / `stableId` / path+rule fingerprints with reason (`false_positive`, `wont_fix`, expiry optional) |
| **Inline disable** | `# repolens:disable-next-line` / block comments (language-aware) for LLM/heuristic noise; scanners may still report unless also suppressed in tool config |
| **Fingerprint** | Prefer Phase 6 `stableId` + file path + rule/category; ignore list checked before report emit and before SARIF |
| **CI** | Suppressed findings excluded from fail-on and from SARIF; still optionally listed under “Suppressed” in Markdown for audit |

Also:

| Item | Notes |
|------|--------|
| Thumbs up/down + reason | Local-only; can write/suggest `.repolens-ignore` entries |
| Self-consistency (optional) | Critical/High second pass; agree or demote / “unconfirmed” |
| Temperature defaults | Low temp for security band |

**Exit:** Documented ignore file + disable comments; suppressions honored in review/CI/SARIF; feedback path opt-in; Critical self-consistency behind a cost-aware flag.

**Out of 6.7:** Cloud upload of feedback; training a global RepoLens model; silently dropping scanner Criticals without an explicit ignore entry.

---

### Phase 6.8 — PR suggested-fix UX

**Goal:** Make remediation easier in the PR loop after SARIF/gates exist — without becoming Dependabot.

| Item | Notes |
|------|--------|
| Richer PR / annotation format | Markdown summary + expandable details from report/SARIF |
| Suggested-fix presentation | Surface Critical/High code examples as review comments or Action job summary |
| Optional apply hints | Doc/recipe for applying examples; no mandatory auto-commit |

**Exit:** Action/docs show PR-oriented summary + suggested-fix presentation for at least GitHub.

**Out of 6.8:** Auto-opened dependency bump PRs (→ beyond); push protection (→ Phase 7 recipes).

---

### Phase 6.9 — Best-effort reachability & optional finding verification

**Goal:** Narrow SCA noise and raise trust on Critical findings where free tooling allows — without Snyk Enterprise claims.

| Item | Notes |
|------|--------|
| Reachability (best-effort) | **Scanner fields only** (extends 6.2 guardrail); never LLM lockfile reasoning |
| Optional sandbox verify | Experimental: agent proposes a minimal repro/test; never blocks report on failure |
| Dedup / clustering | Near-duplicate finding collapse post-merge |
| Reuse anchors | Location verify for narrative may share 6.4 anchor resolver (Markdown can warn; SARIF still strict) |

**Exit:** FAQ states reachability limits; if a free **scanner** signal exists it is wired; verify mode is opt-in and non-fatal.

**Out of 6.9:** Full proprietary reachability graphs; mandatory sandbox; LLM-inferred “devDependency hits prod”.

---

### Phase 6.10 — Optional domain packs (starting point: Azure Sentinel / SOAR)

**Goal:** Niche declarative/workflow packs where AST SAST is weak; not core default path.

| Item | Notes |
|------|--------|
| Azure Sentinel / Logic Apps pack | Hardcoded tenant IDs, connector pollution, MSI/RBAC, SOAR loops — LLM + light deterministic checks |
| Pack packaging | Same rules/playbook registry pattern; opt-in |
| Future packs | Mobile, etc. — same mechanism |

**Exit:** At least one opt-in domain pack installable/documented; core `sentinel` unchanged when pack off.

**Out of 6.10:** Replacing Checkov/ARM-TTK; Azure-only product pivot.

---

## 4. Placement of formerly “deferred” items

| Idea | Placement | Rationale |
|------|-----------|-----------|
| Local thumbs-up/down calibration | **6.7** | Credibility after playbook/FP work |
| `.repolens-ignore` / disable-next-line | **6.7** | Prevent nagging across PRs |
| Critical self-consistency | **6.7** | Trust on highest severity |
| Triage routing (LLM only on scanner hits) | **6.3** | CI velocity / token cost |
| SARIF Verification & Anchor | **6.4** | Avoid GHAS UI breakage |
| Remediation rate / MTTR as headline metrics | **6.6** | Market the real value prop |
| LLM forbidden from lockfile/graph SCA | **6.2** (+ **6.9**) | Stop dep FP hallucinations |
| PR suggested-fix UX | **6.8** | Needs 6.3/6.4 gates + anchored SARIF |
| Best-effort reachability (scanner-only) | **6.9** | After SBOM/SCA (6.2) |
| Optional sandbox verify finding | **6.9** | Experimental trust layer |
| Azure Sentinel / SOAR domain lens | **6.10** | Niche pack, not core debt |
| Jenkins / CircleCI / GitLab recipes | **Phase 7** | Delivery surface, not detection |
| Artifact → email / webhook / dashboard ingest | **Phase 7** | Corporate handoff |
| Adaptive cache on ephemeral CI | **Phase 7** | Ops guidance |
| Push protection / pre-receive (forge-side recipes) | **Phase 7** | Document GH/gitlab secret push protection + how RepoLens audits what already landed — do **not** build a RepoLens pre-receive server |
| Wire SARIF/SBOM into CI artifact + notify flows | **Phase 7** | Consumes 6.4 outputs |
| Provider aliases / native SDKs | **Phase 8 / 9** | Unrelated to scanner depth |
| Auto dependency bump PRs (Dependabot-like) | **Beyond 6.x / Phase 7+ wishlist** | Different product surface; prefer Dependabot + RepoLens narrative |
| Hosted ASPM / SSO / org policy console | **Non-goal** | Option B; export only |
| Native DAST (ZAP as first-class plugin) | **Beyond** (companion docs OK in Phase 7) | Different SDLC stage |
| Full Snyk-class reachability | **Non-goal** | Honesty over marketing |
| Modifying Phase 6 explain core | **Non-goal** | Only consume new scanner fields if needed |

---

## 5. Explicit non-goals (remain out of RepoLens core)

- RepoLens SaaS, ASPM UI, SSO, org policy console  
- Replacing Checkmarx / Veracode / Fortify / CodeQL as the detection engine  
- Full SCA reachability comparable to Snyk Enterprise  
- Building push-protection infrastructure inside RepoLens  

---

## 6. Suggested sequencing & dependencies

```text
6.1 Trivy/Checkov ──► 6.2 SBOM/licenses (+ LLM must not own dep graph)
         │                    │
         └────────┬───────────┘
                  ▼
         6.3 Gates + triage routing + provenance
                  │
                  ▼
         6.4 Anchored SARIF / ASPM recipes  ◄── Verification & Anchor hard gate
                  │
                  ▼
         6.5 Playbooks + calibrations
                  │
                  ▼
         6.6 Benchmark (remediation rate / MTTR lead; P/R support)
                  │
                  ▼
         6.7 Suppressions (.repolens-ignore) + feedback + Critical consistency
                  │
                  ▼
         6.8 PR suggested-fix UX ◄── needs anchored 6.4
                  │
                  ▼
         6.9 Reachability (scanner-only) + optional verify
                  │
                  ▼
         6.10 Optional domain packs (Sentinel/SOAR, …)
                  │
                  ▼
              Phase 7 (enterprise CI delivery, notify, forge push-protection recipes)
                  │
                  ▼
              Phase 8 / 9 (providers)
```

**Core debt bar (ship before calling 6.x “credible”):** **6.1–6.6** including triage routing, SARIF anchoring, SCA guardrails, and remediation-led benchmark.  
**Extended 6.x (6.7–6.10):** suppressions are **strongly recommended before wide CI rollout** even though listed as extended — treat **6.7 ignore file as a soft gate** before declaring CI “production-ready.”

6.5 playbook text updates can start early (docs-only PR) but should not claim Trivy/Checkov until 6.1 ships.

---

## 7. Positioning (keep consistent)

Use in README/FAQ/marketing:

> RepoLens is the open-source due-diligence layer: structured security → reliability → architecture reviews with impact and code examples. Deterministic scanners (Semgrep, Gitleaks, OSV, Trivy, Checkov, …) are the floor; the LLM is the synthesis. Use it **with** CodeQL/GHAS/Snyk — not instead of them.

Headline differentiators:

1. **The tool that audits whether you are using SAST correctly** — can flag missing Dependabot/CodeQL/Semgrep/secret scanning, not only code bugs.  
2. **Remediation, not just detection** — code examples + explain that raise fix rate / lower MTTR.  
3. **CI-safe hybrid** — scanners gate; triage-routed LLM explains hits; anchored SARIF never invents line numbers.

---

## 8. Tracker

Implementation checkboxes live in [phases.md](../phases.md) under **Phase 6.1–6.10**. This file is the design umbrella; per-phase implementation plans may be added under `docs/superpowers/plans/` when a slice starts.
