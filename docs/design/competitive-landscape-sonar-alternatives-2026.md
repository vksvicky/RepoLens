# Competitive landscape — Sonar alternatives, linters & AppSec (2026)

**Audience:** maintainers / roadmap (what to adopt, integrate, complement, or refuse)  
**Date:** 2026-09-26  
**Status:** Ready as-is — internal rudder (block SaaS / compiler-engine scope creep) **and** external messaging foundation for README / FAQ / docs updates  
**Related:** [repolens-vs-appsec-tools.md](./repolens-vs-appsec-tools.md) · [complexity-and-cognitive-ai.md](./complexity-and-cognitive-ai.md) · [metis-agent-comparison.md](./metis-agent-comparison.md) · [scanners.md](../scanners.md) · [phases.md](../phases.md) · [zugel-comparison-and-roadmap.md](./zugel-comparison-and-roadmap.md)

**Primary references (external):**

- [SonarQube (SonarSource)](https://github.com/SonarSource/sonarqube) — continuous inspection / rules-based quality + security  
- [Best SonarQube alternatives for AI code review (2026) — Macroscope](https://macroscope.com/content/best-sonarqube-alternatives-2026) — AI-native vs rules-based framing  
- [Bearer CLI](https://www.bearer.com/bearer-cli) — OSS privacy/security SAST CLI  

Costs and capabilities below are industry ranges as of mid/late 2026. RepoLens is assessed as **alpha** (`repolens-audit` 0.1.0a1): Phases 0–9 (Gemini/Vertex/Bedrock) + Wave C + dogfood cost/change-set shipped; not an ASPM suite.

---

## 1. Bottom line (read this first)

### Headline wedge: zero infrastructure (not “magic free GPU”)

SonarQube wants a server, PostgreSQL, and auth. CodeRabbit and Macroscope want your source in their SaaS. RepoLens wants a venv (or `pipx`) — **no platform to operate**.

**Two zero-infra paths (be precise in marketing):**

| Path | What runs where | Honesty |
|------|-----------------|---------|
| **Air-gapped / local Ollama** | Fast Brain (regex, heuristics, grimp, AST, scanners) runs anywhere in seconds. Slow Brain deep P1→P2→P3 needs a **capable** local model (typically 14B–32B+). | Underpowered consultant laptops can be painfully slow or OOM. Air-gap is *enabled* by Ollama — not guaranteed snappy on every machine. |
| **Private BYOK (common enterprise path)** | Same CLI; model calls go to the org’s approved cloud (Bedrock / Vertex / Gemini / Anthropic / …) so code stays inside company-approved boundaries without a RepoLens SaaS. | Lowest friction for most enterprises; still zero *RepoLens* infrastructure. |

| Verdict | Meaning for RepoLens |
|---------|----------------------|
| **Zero infrastructure** | No dedicated Sonar host, no Postgres, no RepoLens vendor cloud. `pipx install repolens-audit` on a laptop or ephemeral CI runner → unified audit report without standing up a platform. Air-gap via Ollama (hardware caveats); everyday enterprise via private BYOK. |
| **We are not SonarQube / Qodana / DeepSource** | Do not rebuild quality profiles, LOC licensing, portfolio dashboards, or a full deterministic rule engine. |
| **We are not Macroscope / CodeRabbit / Kodus** | Do not make “inline PR velocity bot / auto-approve SaaS” the primary product. Optional Crit/High PR comments are fine; seat SaaS is not. |
| **We already sit beside Semgrep / Trivy / Gitleaks / OSV / Checkov** | Keep absorbing **evidence** from rules tools; do not reimplement their engines. |
| **Our wedge** | Portable **P1→P2→P3 dual-review** (security + reliability + architecture) with human-readable remediation, explain/diagrams, BYOK/Ollama, forge-agnostic CLI — **merged** with scanner evidence — **with zero platform to operate**. |
| **Strategic integration** | **SARIF 2.1 import** (`--import-sarif`) is **shipped** — ingest Sonar/CodeQL/ESLint/… into one narrative. Prefer it over writing language-specific scanner plugins. Defensive normaliser in place (§13). |
| **Adopt selectively** | Ideas and **integrations** (SARIF first, companion recipes, ratchet UX). Rarely: thin plugins. Almost never: reimplementation. |

**Who holds the CLI (buyer personas):**

| Persona | Why they reach for RepoLens (not a continuous linter) |
|---------|--------------------------------------------------------|
| **M&A / tech due-diligence auditor** | Needs a ~48-hour health report on an unfamiliar codebase **without** standing up Sonar/Qodana CI or sending IP to a review SaaS. |
| **Fractional CTO / consultant** | Inherits a client repo; needs an instant, defensible architecture + security diagnostic for leadership — portable, citeable Markdown/PDF. |
| **Security / platform lead** | Pre-release / tag gate: deterministic scanner passes **plus** architecture review in one confidence-aware package before a major ship. |

**Why not just `semgrep && trivy && gitleaks`?**

A shell script yields three disconnected JSON dumps, duplicated CVEs, no cross-tool dedupe, no import-graph cyclicity, no Critical/High remediation examples, and no unified confidence / fail-on gate. RepoLens turns raw scanner evidence — plus third-party SARIF via `--import-sarif` — into one **prioritized human decision**.

**External positioning sentence:**

> RepoLens is a **zero-infrastructure** open-source dual-review CLI for due-diligence and release gates — not a SonarQube alternative and not an AI PR bot. Install with `pipx`; run Fast Brain anywhere; for deep review use **private BYOK** (Bedrock/Vertex/Gemini/Anthropic, …) or **local Ollama** when air-gapped and hardware allows. Pair Semgrep/Trivy/Sonar/Qodana for deterministic SAST; use RepoLens for the portable security + reliability + architecture narrative with fix examples.

FAQ follow-up (when docs are refreshed): mirror the shell-script defense under a short “Why not glue scanners myself?” entry pointing here.

---

## 2. How the market actually splits (2026)

The Macroscope article’s core distinction is correct and useful:

| Lane | How it works | Catches well | Misses |
|------|--------------|--------------|--------|
| **A. Rules / continuous inspection** | Match AST/patterns/taint against fixed rule libraries; quality gates | Known smells, hotspots, many CVEs/misconfigs | Intent, cross-file logic the rule author never wrote |
| **B. AI PR review (SaaS)** | Diff + (sometimes) repo context; comments on every PR | Logic/intent, summaries, “does this PR make sense?” | Compliance attestations; offline/air-gap; architecture *audit* prose |
| **C. Programmable / focused SAST** | Custom rules, privacy/data-flow niches, language specialists | Org policy, language-specific vulns | Full dual-review narrative |
| **D. Supply-chain / ASPM platforms** | Deps, containers, IaC, reachability, dashboards | CVE hygiene, org risk posture | Deep architecture storytelling |

**RepoLens is lane “E”:** *audit / due-diligence dual review* that **composes** A+C evidence and uses AI for narrative + P2/P3 — not a drop-in for A or B.

Lane E exists because continuous linters and PR bots assume an already-wired org. The three personas in §1 (M&A auditor, fractional CTO, security/platform lead) often have **hours, a laptop, and a repo URL** — not a Sonar admin ticket or a SaaS data-processing agreement. Zero infrastructure is the distribution model that matches that constraint.

---

## 3. RepoLens today (capability snapshot)

| Capability | Status |
|------------|--------|
| **Zero-infra CLI** (pip/pipx, ephemeral CI, air-gap + Ollama/BYOK) | Core distribution model |
| Dual playbooks P1→P2→P3 + Critical/High code examples | Core |
| Explain + Mermaid diagrams; `.repolens-ignore` / feedback demotion | Shipped |
| Plugins: Semgrep, Gitleaks, OSV; opt-in Trivy, Checkov; CycloneDX SBOM | Shipped |
| CI Action, SARIF **export**, enterprise CI recipes, cyclicity ratchet (G2) | Shipped |
| SARIF **import** (`--import-sarif`; Sonar/CodeQL/ESLint/…) into narrative | Shipped |
| Providers: Ollama + cloud BYOK + Phase 8 aliases + Phase 9 Gemini/Vertex/Bedrock | Shipped |
| `--git-diff` change-set Slow Brain + deep cost knobs | Shipped |
| Hosted multi-repo portal, SSO ASPM, IDE extension product, auto-approve PRs | **Non-goal** |
| Full Sonar-class rule engine / taint DB / dedicated server | **Non-goal** |

---

## 4. Tool-by-tool — AI / quality platforms

Sources: SonarSource repo positioning; Macroscope 2026 alternatives guide; public product docs.

### 4.1 SonarQube (SonarSource)

| | |
|--|--|
| **Job** | Continuous inspection: bugs, smells, coverage, security hotspots, quality gates (Community → Data Center + Cloud) |
| **Strength** | Deep rule library; governance/portfolio in higher editions; self-host for residency; industry default for “quality culture” |
| **Weakness** | Rules miss intent; FP triage tax; LOC-metered pricing; not AI dual-review prose |
| **vs RepoLens** | Different moment: Sonar = continuous CI quality; RepoLens = portable audit narrative. Overlap on “reliability/smells” is **shallow**. |

**Adopt?** **Complement only.** Document “run Sonar in CI; RepoLens for release/M&A/dogfood gates.” Prefer **SARIF import** (§8.2) over any Sonar-specific plugin so Sonar findings land in the same P1→P2→P3 narrative.  
**Do not:** clone quality profiles, LOC billing metaphors, or “RepoLens Server.”

### 4.2 JetBrains Qodana

| | |
|--|--|
| **Job** | Bring IntelliJ inspections into CI/PR (linters + JetBrains IDE rule depth as a service/CI image) |
| **Strength** | Excellent for JVM/Kotlin/.NET shops already on JetBrains; CI-native reports |
| **Weakness** | Ecosystem-tied; not forge-agnostic AI architecture review |
| **vs RepoLens** | Qodana wins deterministic IDE-parity lint; RepoLens wins playbooks + explain + local LLM |

**Adopt?** **Complement + recipe.** Add a short `docs/ci.md` / FAQ recipe: “Qodana for inspection gates; RepoLens for P1–P3 audit.”  
**Do not:** reimplement IntelliJ inspections.

### 4.3 Semgrep

| | |
|--|--|
| **Job** | Fast pattern/AST SAST; custom org rules; CI gates (OSS + commercial) |
| **Strength** | Writable rules; speed; already a RepoLens first-class plugin |
| **Weakness** | Still rules-based — same intent blind spot as Sonar for logic bugs |
| **vs RepoLens** | Best friend. Semgrep proves patterns; RepoLens prioritises + explains + adds P2/P3 |

**Adopt?** **Already adopted (plugin).** Keep deepening merge/dedupe quality; encourage `REPOLENS_SEMGREP_CONFIG` / org packs.  
**Do not:** fork a competing rule DSL inside RepoLens.

### 4.4 Macroscope

| | |
|--|--|
| **Job** | GitHub-native, codebase-aware AI PR review; structural analysis on 8 languages; Approvability; Markdown Check Run Agents; Fix-it; usage-based pricing |
| **Strength** | Intent + cross-file on PRs; plain-English custom checks; dissolves queue wait on safe PRs |
| **Weakness** | GitHub-focused; SaaS; not a substitute for compliance SAST or offline CLI audits |
| **vs RepoLens** | Closest *AI* competitor on “reasons about the change,” different delivery: PR bot vs portable gate report |

**Adopt (ideas, not product clone)?**

| Idea | Verdict | Notes |
|------|---------|-------|
| Codebase-aware packing (not diff-only) | **Already directionally ours** (`--git-diff` Slow Brain + whole-tree Fast Brain/scanners) | Keep improving pack quality; don’t chase Macroscope agent UX |
| Plain-English custom checks | **Partial adopt later** | Domain packs / playbook snippets already exist; Markdown “agent files” as Check Runs = **non-goal** as primary UX |
| Auto-approve safe PRs | **Do not** | Trust/liability surface; leave to forge + human policy |
| Fix-it PRs | **Optional stretch** | Suggested-fix UX / Crit-High comments already in lane; auto-commit bots = non-goal |
| Usage-based SaaS metering | **Do not** | Stay OSS + BYOK |

### 4.5 CodeRabbit

| | |
|--|--|
| **Job** | Broad-platform AI PR comments (GitHub/GitLab/Bitbucket/Azure DevOps) |
| **Strength** | Thorough inline review; multi-forge |
| **Weakness** | Comment volume / noise; seat pricing; not an audit PDF with scanner merge |
| **vs RepoLens** | Complementary velocity layer (same conclusion as existing Sourcery/CodeRabbit note) |

**Adopt?** **Complement.** Keep optional Crit/High GitHub review comments bounded; do not compete on “comment everything.”  
**Do not:** seat SaaS conversational `@repolens` as primary UX.

### 4.6 DeepSource

| | |
|--|--|
| **Job** | Modern quality platform: deterministic analysis + AI review assist; quality-gate workflow |
| **Strength** | Familiar Sonar-like gates with cleaner FP story + AI assist |
| **Weakness** | Per-seat; AI often rides on rules rather than full dual playbooks |
| **vs RepoLens** | Competes for “Sonar replacement” budget; not for offline BYOK architecture audits |

**Adopt?** **Complement / ignore as peer replacement.** Learn from their FP discipline (calibrations, suppressions — we already have ignore + feedback demotion).  
**Do not:** rebuild DeepSource Cloud.

### 4.7 Kodus (and similar AI PR reviewers)

| | |
|--|--|
| **Job** | AI-assisted code review / engineering productivity (PR-centric) |
| **Strength** | Team review workflows |
| **Weakness** | Same lane as CodeRabbit/Macroscope — not portable dual-audit CLI |
| **vs RepoLens** | Complementary if teams want PR chat; we own gate reports |

**Adopt?** **Complement only.** Same non-goals as CodeRabbit.

---

## 5. Tool-by-tool — language & classic SAST specialists

### 5.1 PMD / Checkstyle / SpotBugs (JVM)

| Tool | Focus |
|------|--------|
| **PMD** | Java/Apex style + bug patterns |
| **Checkstyle** | Java style / conventions |
| **SpotBugs** (+ FindSecBugs) | Bytecode bug/security patterns |

**vs RepoLens:** Best-in-class *deterministic* JVM lint/SAST. RepoLens LLM will never beat SpotBugs on nullness/concurrency patterns.

**Adopt?**

| Action | Verdict |
|--------|---------|
| Document as companion for Java monorepos | **Yes** |
| Prefer SARIF/XML → report annex over native engines | **Yes — strategic** (§8.2) |
| Reimplement rules in Python | **No** |

### 5.2 ESLint (JS/TS)

**Job:** Extensible lint + security plugins (`eslint-plugin-security`, etc.).  
**Adopt?** **Complement.** Recommend in FAQ for JS shops; do not embed ESLint. Prefer **SARIF import** when enterprises already emit it (higher leverage than a dedicated ESLint plugin).

### 5.3 Brakeman (Ruby)

**Job:** Ruby on Rails SAST (path traversal, XSS, mass assignment, …).  
**Adopt?** **Complement via SARIF**, not a first-party Ruby engine. Prefer “run Brakeman → SARIF → RepoLens” over a Brakeman plugin. Semgrep covers some Rails patterns already.

### 5.4 nodejsscan

**Job:** Node.js security pattern scanner (often Semgrep-backed historically / similar niche).  
**Adopt?** **Do not duplicate.** Point Node teams at Semgrep configs + Trivy; RepoLens plugin already covers Semgrep.

### 5.5 betterer

**Job:** Gradual quality improvement — fail CI when a metric *worsens* vs a checked-in baseline (lint debt ratchet).  
**vs RepoLens:** Conceptually closest to our **G2 cyclicity ratchet** / baseline JSON — different domain (lint counts vs import cycles).

**Adopt?**

| Action | Verdict |
|--------|---------|
| Keep/extend **ratchet** product idea (debt must not rise) | **Yes — already ours for graph** |
| Adopt betterer as a dependency | **No** |
| Optional “issue-count ratchet” across scanner severities | **Interesting later** — separate issue; don’t scope-creep into Sonar quality gates |

---

## 6. Tool-by-tool — supply chain, privacy SAST, platforms

### 6.1 Trivy

**Job:** FS/image/IaC/misconfig/secrets + SBOM.  
**Adopt?** **Already adopted (plugin + SBOM).** Default enablement remains opt-in. Registry auth: [trivy-registry-auth.md](./trivy-registry-auth.md) (#94).  
**Do not:** claim live image-registry completeness in CI we don’t run.

### 6.2 Snyk

**Job:** Developer SCA + Code + Container + IaC; PR/IDE; reachability storytelling (commercial).  
**Adopt?** **Complement.** Prefer free OSV/Trivy evidence inside RepoLens; never claim Snyk-class reachability.  
**Do not:** build bump-PR bots or vendor CVE DB.

### 6.3 Aikido Security

**Job:** Unified AppSec / ASPM-style platform (SAST/SCA/secrets/cloud) aimed at reducing tool sprawl.  
**Adopt?** **Complement for buyers who want a portal.** RepoLens stays CLI/report.  
**Do not:** ASPM SSO multi-tenant cloud.

### 6.4 Bearer CLI

**Job:** OSS SAST focused on security **and privacy/data-flow** (sensitive data discovery + rules); CI/CLI. (Bearer Inc. also ships adjacent CI/supply-chain tools under broader branding.)  
**vs RepoLens:** Strong privacy/data-classification niche Semgrep doesn’t always own out of the box.

**Adopt?**

| Action | Verdict |
|--------|---------|
| Document as privacy companion | **Yes** |
| Optional plugin (JSON → findings merge) | **Candidate** — after Trivy/Checkov merge quality is solid; only if dogfood shows demand |
| Reimplement privacy data-flow engine | **No** |

### 6.5 Kodus / other “AI review startups”

Treat as **CodeRabbit-class** unless a specific OSS CLI emerges we can plugin. Default: complement, don’t clone.

---

## 7. Comparison matrix (honest)

Legend: ● strong · ◐ partial · ○ weak/absent · — N/A

| Capability | Sonar | Qodana | Semgrep | Macroscope | CodeRabbit | DeepSource | Trivy | Snyk | Bearer | **RepoLens** |
|------------|:----:|:------:|:-------:|:----------:|:----------:|:----------:|:-----:|:----:|:------:|:------------:|
| Deterministic rule SAST | ● | ● | ● | ◐ | ○ | ● | ◐ | ● | ● | ◐ (via plugins) |
| Intent / logic on PR | ○ | ○ | ○ | ● | ● | ◐ | ○ | ○ | ○ | ◐ (LLM deep; not PR-native) |
| Architecture narrative (P3) | ◐ | ◐ | ○ | ◐ | ◐ | ◐ | ○ | ○ | ○ | ● |
| Remediation prose + code examples | ◐ | ◐ | ○ | ● | ● | ◐ | ○ | ◐ | ◐ | ● |
| Offline / air-gapped / no platform server | ◐ | ◐ | ● | ○ | ○ | ○ | ● | ○ | ● | ● (**headline**) |
| Offline / BYOK / Ollama | ◐ | ◐ | ● | ○ | ○ | ○ | ● | ○ | ● | ● |
| Any Git host + local path | ◐ | ◐ | ● | ○ | ◐ | ◐ | ● | ◐ | ● | ● |
| Containers / IaC CVE | ○ | ○ | ○ | ○ | ○ | ○ | ● | ● | ○ | ◐ (Trivy/Checkov) |
| Privacy / sensitive-data SAST | ◐ | ○ | ◐ | ○ | ○ | ○ | ○ | ◐ | ● | ○ (defer to Bearer) |
| Compliance / portfolio dashboards | ● | ◐ | ◐ | ○ | ○ | ● | ○ | ● | ○ | ○ |
| Auto-approve PRs | ○ | ○ | ○ | ● | ○ | ○ | ○ | ○ | ○ | ○ (**non-goal**) |
| Import-graph cyclicity ratchet | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● (G2) |

---

## 8. Adopt / integrate / complement / refuse

### 8.1 Adopt (build or keep in RepoLens)

| Item | Why |
|------|-----|
| **Zero-infra CLI distribution** | Air-gap / ephemeral CI / consultant laptop — the distribution wedge Sonar and PR SaaS cannot match |
| Dual-review playbooks + explain/diagrams | Unique durable content wedge |
| Scanner **merge** + dedupe + SBOM from engines we trust | Honest AppSec without fake SAST depth; answer to “why not a shell script?” |
| Suppressions + local feedback demotion | FP discipline without a SaaS mute queue |
| Change-set / cost controls for deep LLM | Makes AI review affordable vs “scan everything” |
| Graph cyclicity **ratchet** (betterer-like idea) | Durable quality gate Sonar alternatives rarely own |
| Provider breadth (local + cloud natives) | Privacy / air-gap story Macroscope/CodeRabbit can’t match |

### 8.2 Integrate (thin plugins or artifact import)

**Principle:** SARIF import beats writing language-specific plugins. One SARIF 2.1.0 ingest path turns Sonar, CodeQL, ESLint, SpotBugs, Brakeman, Qodana, etc. into annex evidence inside the RepoLens narrative — **executive reporting layer without N new engines**.

| Priority | Integration | Notes |
|----------|-------------|-------|
| P0 (done) | Semgrep, Gitleaks, OSV | Keep |
| P0 (done, polish) | Trivy, Checkov | Opt-in; honesty on registry limits |
| **P0 (done)** | **SARIF 2.1 import** (`--import-sarif`; Sonar / CodeQL / ESLint / SpotBugs / Brakeman / Qodana / …) | **Shipped** — defensive schema-tolerant normaliser; merged into scanner runs + P1→P2→P3 narrative + dedupe (dialect sprawl — §13). |
| P2 | **Bearer CLI** plugin | Privacy niche; only with dogfood pull — or Bearer→SARIF if they emit it |
| P3 | Native Brakeman / PMD wrappers | **Avoid** if SARIF covers them; annex-only if not |
| — | Qodana / Sonar as **CI companions** | Docs recipes only |

### 8.3 Complement (recommend beside RepoLens — do not rebuild)

| Stack role | Tools |
|------------|-------|
| Quality gate / smells | SonarQube or Qodana or DeepSource |
| Custom SAST rules | Semgrep |
| JVM deep lint | PMD + Checkstyle + SpotBugs |
| JS lint | ESLint (+ security plugins) |
| Rails SAST | Brakeman |
| Privacy/data-flow | Bearer CLI |
| Containers / IaC / CVE | Trivy (+ Checkov) |
| Commercial SCA/reachability | Snyk (or org ASPM: Aikido, etc.) |
| PR velocity AI | Macroscope **or** CodeRabbit **or** Kodus |
| Gradual lint debt | betterer (or our ratchet for graphs) |

**Recommended free companion (update of existing):**

| Role | Tool |
|------|------|
| SAST patterns | Semgrep OSS |
| Secrets | Gitleaks |
| Deps / FS / IaC | Trivy |
| Privacy (optional) | Bearer CLI |
| Dep bumps (GitHub) | Dependabot |
| Runtime (optional) | OWASP ZAP |
| **Narrative gate** | **RepoLens** |

### 8.4 Refuse (explicit non-goals)

| Temptation | Why refuse |
|------------|------------|
| “SonarQube alternative” marketing | False; loses on rules/compliance; confuses buyers |
| Full rule engine / taint DB | Infinite surface; Semgrep/CodeQL/Sonar already exist |
| GitHub-only AI review SaaS with auto-approve | Different company; liability; abandons CLI wedge |
| IDE refactor product (vs Ruff/Sourcery/ESLint) | Wrong moment in SDLC |
| ASPM portal / SSO multi-tenant | Phase-beyond; enterprise sales motion we don’t have |
| Dependabot-like bump bots | Noise + maintenance; scanners + Dependabot win |
| Snyk-class reachability claims | Honesty debt |
| Reimplement PMD/Checkstyle/SpotBugs/ESLint/Brakeman/nodejsscan | Language specialists win; **SARIF import** or document — do not ship N engines |
| Bash “orchestrator” as the product | Shell scripts don’t dedupe, narrate, ratchet, or gate — see §1 |

---

## 9. What we can learn without copying

| From | Steal the idea (safely) |
|------|-------------------------|
| **Macroscope** | Codebase-aware context > diff-only; precision over comment spam; plain-language custom checks → enrich **playbooks/packs**, not Check Run SaaS |
| **CodeRabbit** | Multi-forge presence → keep RepoLens forge-agnostic; optional bounded PR comments only |
| **DeepSource / Sonar** | FP hygiene and quality-gate *discipline* → ratchet + ignore + confidence honesty |
| **Semgrep** | Org-writable policy → packs + `REPOLENS_SEMGREP_CONFIG`, not a new DSL |
| **betterer** | “Debt must not rise” → already G2; consider scanner-count baselines later |
| **Bearer** | Privacy as first-class theme → playbook coverage + optional plugin |
| **Qodana** | IDE-parity CI for JVM shops → recipe docs, not engine |
| **Trivy/Snyk** | Supply-chain evidence ownership → scanners own CVEs; LLM must not invent graphs |

---

## 10. Product bets (2026 refresh)

1. **Lead with zero infrastructure / air-gapped.** Sonar needs a server; PR AI needs a SaaS; we need `pipx` + optional Ollama/BYOK.
2. **Never market as a SonarQube alternative.** Market as the **dual-review / due-diligence layer** for the three personas in §1, sitting on free scanners and optional Sonar/Qodana.
3. **Never market as Macroscope/CodeRabbit.** Market as the **portable gate** (local, any git, offline AI) with optional PR annotations.
4. **SARIF import > language plugins.** Become the universal executive reporting layer; don’t write Brakeman/PMD engines.
5. **Plugin > reimplement** for remaining specialists (Bearer only if SARIF isn’t enough).
6. **Honesty is a feature:** FAQ already says AI ≠ CVE list — keep calling out what plugins prove vs what LLM opines; answer “why not a shell script?” explicitly.
7. **Ratchets are our Quiet Superpower:** cyclicity baseline today; resist boiling the ocean into a full Sonar quality dashboard.
8. **Paid vendors still win** SSO, portfolio, reachability SCA, IDE instant feedback — accept and compose.

---

## 11. Suggested roadmap cues (not commitments)

| Cue | Type | Trigger |
|-----|------|---------|
| FAQ + ci.md “companion stacks” + “Why not a shell script?” | Docs | Anytime (mirror §1) |
| **SARIF 2.1 import** (multi-tool → P1–P3 narrative) | **Feature (P1 strategic)** | Next integration bet — unpark ahead of Bearer/Brakeman/PMD plugins; budget for dialect sprawl (§13) |
| Bearer optional plugin | Feature | Only if SARIF path insufficient for privacy dogfood |
| Scanner severity count ratchet | Feature | After G2 lessons; separate issue |
| Macroscope-like auto-approve | **Reject** | — |
| “RepoLens Cloud ASPM” / Sonar-class server | **Reject** | Breaks zero-infra wedge |

---

## 12. One-page buyer guide

**Headline:** Zero infrastructure — no Sonar server, no PR-review SaaS. Fast Brain anywhere; deep review via private BYOK (common) or local Ollama when air-gapped **and** the machine can host 14B–32B+.

| Persona / need | Prefer… | Add RepoLens when… |
|----------------|---------|---------------------|
| **M&A / tech DD auditor** — 48h health check, unfamiliar repo | Clone + scanners | You need one citeable P1→P3 pack without standing up CI portals |
| **Fractional CTO / consultant** — client diagnostic for leadership | Ad-hoc Semgrep/Trivy | You need defensible architecture + security prose + fix examples (BYOK if laptop is weak) |
| **Security / platform lead** — pre-release / tag gate | Sonar/Qodana/Semgrep in CI | You want scanner evidence + architecture review + unified fail-on (`--fail-on`) **and** a separate Markdown/PDF pack |
| Compliance SAST + quality gates (ongoing) | SonarQube / Qodana / DeepSource | You also need offline narrative or SARIF woven into an audit pack |
| Custom security rules | Semgrep | You want P2/P3 + explain on top |
| PR-native AI review | Macroscope / CodeRabbit / Kodus | You need release/M&A packs, air-gap, or non-GitHub remotes |
| Containers / IaC CVEs | Trivy / Snyk | You want them merged into one gate report (not three JSONs) |
| Privacy/data flows | Bearer | You want privacy findings next to dual-review themes (or via SARIF) |
| JVM/JS/Rails lint depth | SpotBugs / ESLint / Brakeman | You want human-readable P1–P3 over raw rule dumps (**prefer SARIF in**) |
| Gradual debt control | betterer + our G2 ratchet | Graph cycles matter as much as lint counts |
| Portable dual review + **no platform** | **RepoLens** | That’s the primary job |

---

## 13. Execution risks to monitor (keep honest)

These do not invalidate the strategy; they are failure modes if messaging or implementation get sloppy.

### 13.1 Air-gapped ≠ free Slow Brain on every laptop

| Layer | Reality |
|-------|---------|
| **Fast Brain** | Regex, heuristics, grimp/AST, scanner plugins — seconds on ordinary hardware |
| **Slow Brain** | Deep dual review needs a capable model (14B–32B+ locally, or cloud BYOK) |
| **Marketing** | Say “air-gapped **via** Ollama (hardware-dependent)” — not “runs full deep audit instantly offline everywhere” |
| **Default enterprise pitch** | **Private BYOK** (Bedrock / Vertex / Gemini / Anthropic keys inside approved boundaries) as the low-friction path; Ollama for true air-gap / residency when the box can host it |

### 13.2 SARIF dialect sprawl

SARIF 2.1.0 is an OASIS standard; emitters are not. Expect:

- Absolute vs repo-relative paths  
- Missing snippets / message-only results  
- Divergent `rule` / `reportingDescriptor` / taxonomy nesting (Sonar ≠ CodeQL ≠ ESLint)  

**When implementing P1 SARIF import:** defensive parsing, path normalisation against `--path` root, graceful degrade when snippets/rules are thin, golden fixtures per major emitter — **not** a strict “one schema, one happy path” importer.

### 13.3 Dual role: CI gate vs executive audit pack

RepoLens legitimately serves both:

| Role | Consumer | Success signal |
|------|----------|----------------|
| **Ephemeral CI release gate** | Machines | Exit codes / `--fail-on` / SARIF-out / Action annotations |
| **Executive M&A / consultant pack** | Humans | Readable Markdown (PDF via pandoc/print) with impact, remediation, examples |

Current CLI already separates concerns (`--format`, exit codes, report writers). **Keep them decoupled:** never make gate interrupts depend on pretty-print layout, and never bury `sys.exit(1)` semantics inside “executive” prose flags. Future UX (flags, docs, Action inputs) should name the role explicitly so CI and auditors do not fight over one muddled mode.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-09-26 | Initial note: Sonar alternatives (Macroscope article), Qodana, language SAST, Trivy/Snyk/Aikido/Bearer/betterer/Kodus; adopt/refuse matrix |
| 2026-09-26 | Polish: zero-infra / air-gapped headline; three buyer personas; SARIF import as strategic P1 trojan horse; “why not a shell script?” defense |
| 2026-09-26 | Risks: air-gap vs BYOK hardware honesty; SARIF dialect sprawl; CI gate vs executive pack decoupling; status = ready rudder + messaging foundation |
