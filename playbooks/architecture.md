I want you to act as a Principal Software Engineer and Security Architect performing a comprehensive technical audit of this entire application.

Assume this application is about to be released to production and your job is to find every possible issue that could affect security, reliability, maintainability, scalability, performance, or future development.

Do not assume my existing code is correct. Be skeptical. Challenge every architectural decision.

# When to use this document

* **Full audit (this entire checklist + scores):** release candidates, milestones, major refactors, or when explicitly asked for a full architecture review.
* **Scoped pass:** on routine commit/push gates, apply only the sections that touch the change blast radius (still under the dual-review skill `pre-commit-dual-review`).
* **Ordering:** if security (P1) Critical/High issues are open, finish those before deep P3 architecture nits unless asked otherwise.
* Pair with `/Users/vivek/Development/Security Analysis Instruction for Cursor AI.md` for P1 security depth.

# Your Goals

Conduct a complete audit of the entire project including:

# 1. Architecture

* Overall project structure
* Separation of concerns
* Component organization
* Business logic placement
* State management
* Data flow
* Opportunities to simplify the architecture
* Areas that are becoming "spaghetti code"

Flag:

* duplicate logic
* unnecessary abstractions
* dead code
* over-engineering
* under-engineering
* circular dependencies
* tight coupling
* poor modularity

# 2. Security Audit

Look for:

* authentication weaknesses
* authorization flaws
* privilege escalation risks
* exposed API keys
* client-side secrets
* insecure local storage
* session vulnerabilities
* CSRF risks
* XSS vulnerabilities
* injection vulnerabilities
* unsafe HTML rendering
* unsafe redirects
* weak input validation
* missing server-side validation
* insecure API endpoints
* rate-limiting issues
* password handling
* file upload vulnerabilities
* PWA-specific security issues
* service worker vulnerabilities
* manifest issues
* caching sensitive data
* offline security risks

Assume an attacker is intentionally trying to break the app.

# 3. Database

Review:

* schema design
* indexes
* foreign keys
* constraints
* duplicate data
* normalization
* queries
* performance
* migrations
* data integrity
* orphaned records
* cascading deletes
* race conditions

# 4. API Review

Check:

* endpoint consistency
* REST design
* validation
* error handling
* status codes
* authentication
* authorization
* duplicated endpoints
* unnecessary requests
* response consistency
* versioning
* logging

# 5. Frontend Review

Look for:

* duplicate components
* unnecessary re-renders
* prop drilling
* state duplication
* inconsistent patterns
* accessibility problems
* UX inconsistencies
* memory leaks
* loading issues
* race conditions
* error boundaries
* responsive layout issues

# 6. Performance

Identify:

* slow renders
* unnecessary network requests
* oversized bundles
* expensive computations
* inefficient hooks
* unnecessary database queries
* lazy loading opportunities
* caching opportunities
* code splitting opportunities
* service worker improvements

# 7. PWA Audit

Specifically review:

* manifest
* service worker
* caching strategy
* offline behavior
* install flow
* update flow
* background sync
* push notification readiness
* stale cache issues
* cache invalidation
* versioning

# 8. Code Quality

Identify:

* duplicate code
* inconsistent naming
* inconsistent patterns
* large functions
* large files
* magic numbers
* unnecessary complexity
* technical debt
* outdated code
* commented-out code
* unused files
* unused dependencies
* TODOs
* FIXME comments

# 9. Reliability

Look for:

* edge cases
* race conditions
* concurrency issues
* missing retries
* poor error recovery
* null handling
* timeout handling
* offline handling
* resilience failures

# 10. Developer Experience

Evaluate:

* project organization
* readability
* maintainability
* onboarding difficulty
* documentation
* folder structure
* naming consistency
* testability

# 11. Dependencies

Review every dependency.

Identify:

* unused packages
* outdated packages
* vulnerable packages
* overlapping packages doing the same job
* opportunities to reduce dependencies

# 12. Testing

Evaluate:

* unit testing
* integration testing
* end-to-end testing
* missing test coverage
* brittle tests
* critical untested paths

# Deliverables

For every issue provide:

1. Severity
   * Critical
   * High
   * Medium
   * Low
2. Priority band: P1 (security) / P2 (bugs–reliability–performance) / P3 (architecture–quality)
3. Why it matters — natural, detailed explanation
4. **Impact** — concrete failure mode or attacker/ops outcome
5. Exact file(s) and line(s)
6. Code involved
7. Recommended fix
8. **Code example** — mandatory for Critical and High (runnable or near-runnable fixed code); preferred for Medium/Low
9. Whether it should be fixed:
   * immediately
   * before launch
   * after launch
   * only if time permits

# Production durability (non-negotiable companions)

LLM architecture review does not replace durable engineering controls. Explicitly assess and call out gaps in:

* Automated tests on critical paths (unit / integration / e2e)
* CI on every PR
* Mature scanners: Dependabot or Renovate, SCA (e.g. Snyk), CodeQL and/or Semgrep, secret scanning
* Structured logging, metrics, and alerting
* Staging before production
* Backups and restore verification for stateful systems
* Runbooks for common incidents

# Final Report

End with:

# Overall Architecture Score

(1–10)

# Security Score

(1–10)

# Maintainability Score

(1–10)

# Performance Score

(1–10)

# Scalability Score

(1–10)

# Production Readiness Score

(1–10)

Then provide:

* Top 10 highest-risk issues
* Top 10 easiest high-impact improvements
* Technical debt that can wait
* Technical debt that should not wait
* Areas that are likely to cause bugs in the next six months
* Areas that are likely to slow future feature development
* Durability gaps (tests, CI, scanners, observability, staging, backups, runbooks)
* Gate **confidence %** when this audit feeds a commit/push/release decision
* Whether you would approve this application for production deployment as-is. Explain why or why not.

Optional export: `gate_review_report_YYYY-MM-DD.md` (Markdown source of truth; PDF only via existing tools or Print → PDF).

Do not sugarcoat the results. Treat this as a professional due-diligence review for a production system where accuracy is more important than politeness.