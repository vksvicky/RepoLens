**RepoLens Security Playbook (P1 / `sentinel`)**

---

# Objective:
Conduct a thorough security analysis of the target repository (prefer the active change set when reviewing a diff; expand when cross-cutting or when a full audit is requested). Identify any potential security vulnerabilities, bad practices, and risks. Then generate a structured output that clearly outlines:

- Security issues found (grouped by severity: Critical, High, Medium, Low)
- The file and line number where each issue occurs
- A natural, detailed explanation of the problem
- **Impact** (what can go wrong / attacker outcome)
- Recommended remediation steps
- **Code example fixes** (mandatory for Critical and High)
- Optional **CWE** / **OWASP** tags when clearly applicable
- General best practices improvements if applicable

This document is the **P1** authority for RepoLens (`repolens sentinel` and the security band of `repolens review`). Pair with [architecture.md](./architecture.md) for P2/P3 and release audits.

**Evidence-first:** Prefer scanner evidence (Semgrep, gitleaks, OSV, Trivy, Checkov) when present. Invent or escalate findings only with a strong, cited code proof. Do not invent CVE IDs, dependency graphs, or reachability.

---

# Steps for Analysis:

Analyse and report in priority order when the change set is large:

**P1 (this document — do first):** Security  
**P2:** Bugs, reliability, performance (RepoLens `review` reliability band)  
**P3:** Architecture & quality ([architecture.md](./architecture.md), scoped or full)

1. **Scan for Common Security Vulnerabilities:**
   - **Injection** — SQL, command, and **NoSQL** injection. **Not** command injection: list-form `subprocess.run(argv, …)` / `shell=False` (Python default). Only flag when `shell=True` or a single shell string is executed; prefer Semgrep evidence for real injection.
   - **SSRF** — server-side requests to attacker-controlled URLs (cloud metadata, internal services).
   - **Path traversal / Zip Slip** — unsanitised paths, archive extract to unexpected locations (CWE-22).
   - **XXE / XML attacks** — unsafe XML parsers / external entities (CWE-611).
   - **ReDoS** — catastrophic backtracking in user-influenced regex.
   - **Log injection / forgery** — unsanitised newlines or control chars in logs/audit trails.
   - Cross-Site Scripting (XSS) and Cross-Site Request Forgery (CSRF)
   - Insecure Authentication & Authorization; **JWT / token pitfalls** (alg=none, missing `exp`, weak secrets, confused audience)
   - Hardcoded secrets (API keys, passwords, tokens) — prefer gitleaks evidence
   - Unsafe deserialization
   - Insecure file uploads
   - Improper error handling / verbose error messages
   - Unvalidated or unsanitised input handling
   - Missing security headers (for web apps)
   - Cryptography: weak algorithms, incorrect usage; **insecure randomness / weak PRNG** for security decisions
   - Excessive permissions (least privilege violations)
   - Information leakage (exposing internal structure or sensitive info)
   - **Rate limiting / resource exhaustion** on auth and expensive endpoints
   - **Supply-chain integrity** (beyond CVE lists): unpinned GitHub Actions, downloads without checksum/signature

2. **Code Quality & Practice Review:**
   - Check for lack of input/output validation
   - Review logging practices (ensure no sensitive data is logged; watch log injection)
   - Review session management and token expiry
   - Analyse access control at critical operation points
   - Check for open redirect vulnerabilities

3. **Dependency & Configuration Review:**
   - Flag outdated libraries **only when scanner evidence lists them** (OSV/Trivy). Do **not** invent CVE IDs, dependency-graph edges, or reachability (“hits production”) by reading lockfiles.
   - For SCA: remediate from scanner facts; if reachability was not assessed by a scanner, say so.
   - Check configuration files for misconfigurations (e.g., debug mode on, unrestricted CORS)
   - For IaC / containers / workflows: cite **Trivy** / **Checkov** findings when those scanners ran; do not invent cloud policy IDs without evidence
   - Note gaps in **mature automated scanning** (Dependabot/Renovate, Snyk or equivalent SCA, CodeQL/Semgrep, secret scanning). LLM review does not replace these in CI.

---

# Output Format:

## 1. Executive Summary
- Total number of issues found
- Breakdown by severity (Critical / High / Medium / Low)
- Gate **confidence %** when used as part of a pre-merge or release review

## 2. Detailed Findings
For each issue:

- **Severity:** (Critical / High / Medium / Low)
- **Priority:** P1 (security) unless explicitly classified otherwise
- **File:** path/to/file.ext
- **Line Number:** 123
- **Issue Summary:** Short description
- **CWE / OWASP:** (optional — include when clearly applicable, e.g. CWE-22, A03:2021)
- **Detailed Explanation:**
  > Natural, in-depth explanation of why this is a security concern in *this* codebase.
- **Impact:**
  > Concrete attacker outcome or failure mode (data loss, account takeover, RCE, etc.).
- **Recommended Fix:**
  > Step-by-step remediation.
- **Code Example:** (REQUIRED for Critical and High; preferred for Medium/Low)
  > Show the corrected code in the project's language — runnable or near-runnable, not slogans.
- **Best Practice Note (if applicable):**
  > Suggested improvement even if not directly a security flaw.

## 3. Dependency and Configuration Issues
- List of outdated or vulnerable libraries (scanner-backed)
- Misconfigurations found
- Recommendations (including enabling CI scanners where missing)

## 4. General Recommendations
- High-level suggestions to improve overall project security posture (automated secret/CVE scanning, security headers, dependency process, etc.)

---

# Important Notes:
- Prioritise Critical and High severity issues for immediate attention.
- **Do not mark Critical/High complete without a code example fix.**
- Medium severity issues should be included in upcoming development cycles.
- Low severity and best practices can be progressively addressed.
- Use CVSS (Common Vulnerability Scoring System) scores to prioritise where possible.
- Highlight any systemic patterns that increase risk (e.g., recurring lack of input validation).
- Prefer evidence from actual code paths; avoid speculative findings.
- Naming categories (SSRF, XXE, ReDoS, …) does **not** claim CodeQL/Checkmarx parity — deterministic scanners remain the evidence layer.
- Note gaps in **mature automated scanning** (Dependabot/Renovate, Snyk or equivalent SCA, CodeQL/Semgrep, secret scanning). LLM review does not replace these in CI.

---

# Output File Name:

`security_analysis_report_[date].md`

For RepoLens dual reviews, prefer the combined export name `gate_review_report_YYYY-MM-DD.md` when the user asks to export.

---

# Theme checklist (Phase 5.2 / 6.5)

When emitting findings or coverage N/A notes, address these themes (use the theme id in `category` when possible):

* Theme: Injection & unsafe code (`sec.injection`)
* Theme: XSS / CSRF / web surface (`sec.xss_csrf`)
* Theme: Auth & access control (`sec.authn_authz`)
* Theme: Repo hygiene, secrets & credentials (`sec.repo_hygiene_secrets`)
* Theme: Data exposure (`sec.data_exposure`)
* Theme: Dependencies & supply chain (`sec.deps_supply_chain`)
* Theme: Transport & TLS (`sec.transport_tls`)
* Theme: Crypto & deserialization (`sec.crypto_deser`)
* Theme: Input validation (`sec.input_validation`)
* Theme: Config & environment safety (`sec.config_env`) — full audit
* Theme: Privacy & PII handling (`sec.privacy_pii`) — full audit
* Theme: File upload & path traversal (`sec.upload_path`) — full audit
* Theme: Session & cookie security (`sec.session_cookies`) — full audit
* Theme: Rate limiting & abuse (`sec.rate_abuse`) — full audit
* Theme: Build & release integrity (`sec.build_release`) — full audit
* Theme: SSRF & outbound request abuse (`sec.ssrf`) — full audit
* Theme: XXE & unsafe XML (`sec.xxe`) — full audit
* Theme: ReDoS & unsafe regex (`sec.redos`) — full audit
* Theme: Log injection & forgery (`sec.log_injection`) — full audit
* Theme: JWT & token pitfalls (`sec.jwt_tokens`) — full audit
* Theme: Insecure randomness / weak PRNG (`sec.weak_prng`) — full audit

**End of Analysis Instructions**
