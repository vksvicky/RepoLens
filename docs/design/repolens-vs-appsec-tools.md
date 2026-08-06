# RepoLens vs AppSec tools — honest comparison

**Audience:** product / roadmap (how to build a better RepoLens)  
**Date:** 2026-08-06  
**Status:** Working note (not a vendor bake-off scorecard)

Costs below are industry ranges. Capabilities reflect typical 2025–2026 positioning. RepoLens is assessed at **alpha** (Phases 0–6). Semgrep is listed once (OSS + commercial).

Related: [scanners.md](../scanners.md) · [faq.md](../faq.md) · [rules.md](../rules.md) · [phase-6.x-scanner-depth-ci-gates-and-credibility.md](./phase-6.x-scanner-depth-ci-gates-and-credibility.md) · [phase-7-enterprise-ci-and-report-delivery.md](./phase-7-enterprise-ci-and-report-delivery.md)

---

## Bottom line

RepoLens is **not** a peer replacement for Checkmarx, Veracode, Fortify, Snyk, or CodeQL. Those win at deterministic SAST/SCA, policy, and compliance. RepoLens wins at portable, human-readable **dual reviews** (security + reliability + architecture) with optional scanner merge and per-issue explain.

**Build as the layer that orchestrates and explains — not as a CVE database.**

**External positioning sentence:**

> RepoLens is an open-source dual-review CLI that produces auditor-friendly security, reliability, and architecture reports — and can merge Semgrep, Gitleaks, and OSV evidence. Use it with (not instead of) your SAST/SCA stack.

---

## Tool-by-tool

| Tool | Category | Primary job | Cost band | Strength | Weakness | vs RepoLens |
|------|----------|-------------|-----------|----------|----------|-------------|
| **Checkmarx** | Enterprise SAST (+ platform) | Deep multi-language SAST, policy, compliance reporting | Enterprise ($100k+/yr typical) | Mature governance, broad language/rules, auditor-friendly | Heavy, noisy without tuning, slow developer loop | Wins on deterministic SAST depth & compliance. Loses on architecture narrative & BYOK local AI. |
| **Veracode** | Enterprise SAST/SCA | Binary/source AppSec + policy gates for regulated orgs | Enterprise | Compliance programmes, policy enforcement, vendor assessments | Upload/scan friction; weak as a daily local CLI companion | Different buyer. Veracode = gate for auditors; RepoLens = due-diligence narrative for engineers. |
| **Fortify (OpenText)** | Enterprise SAST | Classic enterprise static analysis + SSC dashboards | Enterprise | Long history in banks/gov; deep rule packs | UI/ops burden; often disliked by modern app teams | Same lane as Checkmarx for compliance. Not a product peer for AI dual-review. |
| **Snyk** | Dev AppSec (SCA + SAST + IaC) | Developer-first SCA + Code + Container + IaC | Free tier → Team → Enterprise | PR/IDE loop, auto-fix PRs, reachability on SCA | SAST not as deep as CodeQL/Checkmarx; vendor lock-in risk | Better CVE/dep/container hygiene. RepoLens better at written review + architecture + explain. |
| **Semgrep** | SAST (+ Supply Chain) | Fast pattern/AST rules; custom org rules; CI gates | OSS free; Teams/Enterprise paid | Speed, writable rules, low friction, great CI fit | Not full dataflow like CodeQL; FP if rules are crude | Already a RepoLens plugin. Semgrep finds pattern bugs; RepoLens explains & prioritises across P1–P3. |
| **CodeQL / GHAS** | Semantic SAST + GitHub platform | Query-based semantic analysis inside GitHub | Free public; GHAS paid for private | Deep taint/dataflow; PR annotations; GH ecosystem | GitHub-centric; query authoring has a learning curve | Stronger on precise code vulns in GH. RepoLens works any remote/local + architecture + explain IDs. |
| **Dependabot** | SCA / dependency updates | Open PRs for vulnerable/outdated deps on GitHub | Free on GitHub | Zero-ops updates; advisory DB; native GH | Shallow analysis; noisy bumps; GitHub-only | Complementary. Dependabot patches versions; RepoLens/OSV surfaces risk in a review report. |
| **GitHub Advanced Security** | Platform bundle | CodeQL + secret scanning + Dependabot + security overview | Paid (private repos) | One pane if you live in GitHub | Not portable; cost scales with seats/commits | Best if org is GH-native. RepoLens is portable CLI + dual review beyond GH Security tab. |
| **Trivy** | SCA + containers + IaC | CVE scan images, FS, deps, misconfig | OSS free (Aqua commercial optional) | Excellent free baseline for containers/deps/IaC | Not first-party logic SAST; not architecture review | Should be a future plugin. Today RepoLens uses OSV for deps, not image layers. |
| **Checkov** | IaC / policy-as-code | Terraform/K8s/CloudFormation misconfig policies | OSS free (Prisma Cloud paid) | IaC depth RepoLens does not match deterministically | Narrow scope (infra only) | Complement. RepoLens may comment on IaC in LLM pass; Checkov proves policy failures. |
| **Gitleaks** | Secrets | Find leaked credentials in git history/files | OSS free | Deterministic secrets; already a RepoLens plugin | Not app logic or CVEs | Integrated today. RepoLens wraps it into the same gate report. |
| **SonarQube** | Quality + security | Bugs, smells, coverage, security hotspots, quality gates | Community free → Developer/Enterprise | Quality culture + security in one gate | Security depth varies by edition/lang; not AI narrative | Overlaps reliability/quality. Sonar is continuous CI; RepoLens is audit/review prose + dual playbooks. |
| **OWASP ZAP** | DAST | Attack a running app (XSS, auth, API probes) | OSS free | Finds runtime issues static tools miss | Needs deployable target; different SDLC stage | Not comparable head-to-head. ZAP = black-box runtime; RepoLens = static dual review. |
| **RepoLens** | AI dual review (+ optional scanners) | P1 security → P2 reliability → P3 architecture reports with fixes/explain | OSS MIT; you pay model (cloud key or Ollama) | Portable CLI; human-readable audits; explain + diagrams; merges Semgrep/gitleaks/OSV | Alpha; not CVE-complete alone; LLM FP/FN; no enterprise policy SSO yet | — |

---

## Capability coverage

**Enterprise** = Checkmarx / Veracode / Fortify / Snyk Enterprise / GHAS.  
**Free stack** = Semgrep OSS + Trivy + Checkov + Gitleaks + Dependabot/OSV + CodeQL (public) + ZAP.

| Capability | Enterprise platforms | Free OSS stack | RepoLens today |
|------------|---------------------|----------------|----------------|
| First-party code vulns (injection, XSS, …) | Strong (Checkmarx/Veracode/Fortify/CodeQL) | Strong (Semgrep OSS, CodeQL public) | AI themes + Semgrep plugin — not CodeQL-depth |
| Dependency CVEs / SBOM / licenses | Strong (Snyk, Checkmarx SCA, Veracode) | Strong (Trivy, OSV, Dependabot) | OSV plugin only — no licenses/SBOM/reachability yet |
| Secrets in git | Yes (GHAS, vendor packs) | Gitleaks / GH secret scanning | Gitleaks plugin (merged into report) |
| Containers / image CVEs | Snyk / Checkmarx / Trivy commercial | Trivy (best free) | Trivy plugin (`fs`; full registry matrix later) |
| IaC misconfig | Snyk IaC / Checkmarx / Prisma | Checkov, Trivy | Checkov + Trivy misconfig plugins (opt-in) |
| Runtime / DAST | Vendor DAST add-ons | OWASP ZAP | Out of scope |
| Architecture / maintainability narrative | Weak / separate (Sonar partial) | Weak (Sonar Community partial) | **Core differentiator** (P3 + playbooks) |
| Remediation prose + code examples | Improving (AI add-ons); uneven | Thin (rule messages) | **Core** (Critical/High examples + explain) |
| Compliance / auditor dashboards | Best-in-class | Weak | Markdown/PDF reports — not ASPM |
| Works offline / local AI / any Git host | Rare | Partial (CLI tools) | **Strong** (Ollama + remotes + local path) |
| Determinism & repeatable CI gates | Strong | Strong (Semgrep/Trivy/CodeQL) | Scanners yes; LLM pass is probabilistic |

---

## Where each category wins

### Enterprise (Checkmarx / Veracode / Fortify)

Buy when you need auditor-ready policy, multi-BU reporting, and contractual AppSec coverage. Slow, expensive, and often ignored by developers unless gated in CI.

**RepoLens:** do not displace — sit beside for narrative reviews.

### Dev platforms (Snyk / Semgrep / Sonar)

Win the daily PR loop: fast findings, auto-fix, quality gates. Semgrep is the closest “friend” — already wired as a plugin.

**RepoLens:** merge their SARIF/JSON; add P2/P3 + explain.

### GitHub-native (CodeQL / Dependabot / GHAS)

Best if the org lives in GitHub. CodeQL’s semantic queries beat LLM pattern guessing for many injection classes. Dependabot owns dep bumps.

**Gap / advantage:** Bitbucket / Hugging Face / local / any-git portability.

### Free specialists (Trivy / Checkov / Gitleaks / ZAP)

Best-in-class for one job. Trivy/Checkov expose RepoLens’s biggest coverage holes (containers + IaC). ZAP covers runtime — a different phase of testing.

**Product debt:** Trivy + Checkov plugins before any “full AppSec” claims.

---

## Honest scorecard for RepoLens

### Lead here

- Dual-review playbooks (P1 → P2 → P3)
- Critical/High code-example remediation
- Per-issue explain + foolproof diagrams
- BYOK / Ollama / portable remotes
- Merged scanner + AI report

### Catch up via Phase 6.x (before Phase 7)

See **[phase-6.x-scanner-depth-ci-gates-and-credibility.md](./phase-6.x-scanner-depth-ci-gates-and-credibility.md)**:

- **6.1–6.6 (core):** Trivy/Checkov → SBOM (scanner-owned graph) → triage-routed CI gates → **anchored** SARIF → playbook gaps → remediation-led benchmark  
- **6.7–6.10 (extended):** `.repolens-ignore` + feedback → PR suggested-fix UX → best-effort reachability/verify → optional domain packs  

**Phase 7:** Jenkins/CircleCI/email/webhook, SARIF/SBOM artifact notify, forge push-protection *recipes* (not a RepoLens pre-receive server).  
**Beyond / non-goal:** Dependabot-like bump PRs, hosted ASPM/SSO, native DAST plugin, Snyk-class reachability.

### Leave to others

- Full enterprise SAST rule engines
- DAST / IAST (ZAP, Burp, Contrast)
- Managed vuln DB / threat intel
- SSO AppSec portals / ASPM suites
- Binary-only analysis (Veracode niche)

---

## Product bets

1. **Do not compete as “another Checkmarx”**  
   You will lose on rule depth, CVE databases, compliance attestations, and sales cycles. Position as the review layer that sits on top of (and merges) free scanners.

2. **Own the narrative gap**  
   No tool in this list produces a durable P1→P2→P3 audit with impact, fix plan, code examples, and per-issue explain/diagrams. That is the wedge — due diligence, M&A, contractor handoff, dogfood, pre-release.

3. **Absorb the free stack as plugins**  
   Semgrep + Gitleaks + OSV already exist. Next high-ROI plugins: Trivy (containers/IaC), Checkov (IaC policy), optionally CodeQL SARIF import. Become the merger/normaliser, not a reimplementation.

4. **Honesty as a product feature**  
   The FAQ already says AI ≠ CVE list. Double down: confidence/coverage metrics, FP calibrations, scanner evidence vs AI opinion. Enterprises buy tools that admit what they miss.

5. **Free baseline to recommend beside RepoLens**  
   Document a companion stack: Semgrep OSS + Gitleaks + Trivy + Dependabot/OSV + optional ZAP. RepoLens reviews; the stack proves. Market the combo, not AI alone.

6. **Where paid vendors still win (accept it)**  
   SSO, policy-as-code org rules, SBOM export for procurement, reachability SCA, SOC2 evidence packs, IDE instant feedback. Phase 7 CI delivery helps; do not pretend alpha CLI replaces GHAS.

---

## Recommended free companion stack

Document next to install / scanners docs:

| Role | Tool |
|------|------|
| SAST | Semgrep OSS |
| Secrets | Gitleaks |
| Deps / containers / IaC | Trivy |
| Dep updates (GitHub) | Dependabot (or OSV via RepoLens) |
| Runtime (optional) | OWASP ZAP |

RepoLens already merges Semgrep, Gitleaks, and OSV when installed — see [scanners.md](../scanners.md).
