# RepoLens Reliability Playbook (P2)

Identify high-confidence bugs, reliability, and performance issues in the provided files.

## Focus areas

* Edge cases and null handling
* Race conditions and concurrency issues
* Missing retries and poor error recovery
* Timeout handling and resilience failures
* Performance hotspots that cause user-visible latency or resource exhaustion

## Theme checklist (Phase 5.2)

* Theme: Edge cases & null handling (`rel.edge_cases`)
* Theme: Concurrency & races (`rel.concurrency`)
* Theme: Error recovery & resilience (`rel.error_recovery`)
* Theme: Performance hotspots (`rel.performance`)

## Output requirements

* Require **impact** and **codeExample** for Critical/High findings.
* Return the RepoLens FindingReport JSON schema only.
* Prefer evidence from actual code paths; avoid speculative findings.
* Prefer theme ids above in `category` when a finding maps cleanly.
