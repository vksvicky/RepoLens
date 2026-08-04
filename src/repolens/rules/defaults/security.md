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
- General best practices improvements if applicable

This document is the **P1** authority for RepoLens (`repolens sentinel` and the security band of `repolens review`). Pair with [architecture.md](./architecture.md) for P2/P3 and release audits.

---

# Steps for Analysis:

Analyze and report in priority order when the change set is large:

**P1 (this document — do first):** Security  
**P2:** Bugs, reliability, performance (RepoLens `review` reliability band)  
**P3:** Architecture & quality ([architecture.md](./architecture.md), scoped or full)

1. **Scan for Common Security Vulnerabilities:**
   - Injection risks (SQL Injection, Command Injection)
   - Cross-Site Scripting (XSS)
   - Cross-Site Request Forgery (CSRF)
   - Insecure Authentication & Authorization mechanisms
   - Hardcoded secrets (API keys, passwords, tokens)
   - Unsafe deserialization
   - Insecure file uploads
   - Improper error handling / verbose error messages
   - Use of outdated or vulnerable dependencies
   - Unvalidated or unsanitized input handling
   - Missing security headers (for web apps)
   - Improper use of cryptographic functions (weak algorithms, incorrect usage)
   - Excessive permissions (least privilege violations)
   - Information leakage (exposing internal structure or sensitive info)

2. **Code Quality & Practice Review:**
   - Check for lack of input/output validation
   - Review logging practices (ensure no sensitive data is logged)
   - Review session management and token expiry
   - Analyze access control at critical operation points
   - Check for open redirect vulnerabilities

3. **Dependency & Configuration Review:**
   - Flag outdated libraries
   - Flag libraries known to have CVEs (Common Vulnerabilities and Exposures)
   - Check configuration files for misconfigurations (e.g., debug mode on, unrestricted CORS)
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
- List of outdated or vulnerable libraries
- Misconfigurations found
- Recommendations (including enabling CI scanners where missing)

## 4. General Recommendations
- High-level suggestions to improve overall project security posture (automated secret/CVE scanning, security headers, dependency process, etc.)

---

# Important Notes:
- Prioritize Critical and High severity issues for immediate attention.
- **Do not mark Critical/High complete without a code example fix.**
- Medium severity issues should be included in upcoming development cycles.
- Low severity and best practices can be progressively addressed.
- Use CVSS (Common Vulnerability Scoring System) scores to prioritize where possible.
- Highlight any systemic patterns that increase risk (e.g., recurring lack of input validation).
- Prefer evidence from actual code paths; avoid speculative findings.

---

# Output File Name:

`security_analysis_report_[date].md`

For RepoLens dual reviews, prefer the combined export name `gate_review_report_YYYY-MM-DD.md` when the user asks to export.

---

**End of Analysis Instructions**
