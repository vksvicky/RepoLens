# Cross-source SCA deduplication & confidence impact (design)

**Status:** Approved for plan  
**Date:** 2026-09-06  
**Issue:** [#14](https://github.com/vksvicky/RepoLens/issues/14)  
**Parent:** [#13](https://github.com/vksvicky/RepoLens/issues/13) (Gate honesty interrupt)  
**Consumer requirement:** LogViewer dogfood & multi-pass deep reviews (prevent 2 CVE advisories exploding into 6 Critical/High penalties)  
**Preceded by:** [#21](https://github.com/vksvicky/RepoLens/issues/21) (Vacuous pass confidence floor, merged via PR #22)  
**Followed by:** [#17](https://github.com/vksvicky/RepoLens/issues/17) (Gate UX & copy MVP)

---

## 1. Problem

In RepoLens today, SCA deduplication (`dedupe_sca_issues` in `src/repolens/scanners/sca.py`) only operates across scanner tools (preferring OSV over Trivy for identical advisory IDs). It runs before the LLM passes execute.

When a deep review runs:
1. Deterministic scanners (OSV, Trivy) detect known CVEs/GHSAs in dependencies and produce findings.
2. Scanner evidence is formatted and attached to LLM prompts (`format_scanner_evidence_for_prompt`).
3. LLM passes (P1/Security or domain packs) frequently report findings citing the exact same CVE or GHSA advisories.
4. During report merge, scanner issues and LLM issues are concatenated together (`report.issues = list(report.issues) + extra_issues`).
5. `severity_finding_penalty` in `src/repolens/metrics.py` iterates over every open Critical/High issue:
   - Critical: −20 per finding (cap −60)
   - High: −10 per finding (cap −50)
6. As a result, 2 genuine dependency advisories frequently multiply into 4–6 Critical/High findings across scanner and LLM outputs, causing maximum severity penalty (−60 Critical + −50 High) and triggering unwarranted gate failure or artificial confidence collapse.

### Why not overload `cluster_near_duplicates`?
RepoLens already has `cluster_near_duplicates` in `src/repolens/cluster.py`. However:
- `cluster.py` clusters by `(file, theme, cwe/title)` and explicitly **prefers the higher severity** finding (to avoid hiding severe code smells).
- Cross-source SCA deduplication requires the **opposite severity rule**: the deterministic scanner finding is the authoritative baseline; the LLM must **not** raise an advisory's severity above the scanner's CVSS calculation.
- SCA findings often have different file targets (e.g. `package-lock.json` from OSV vs `src/index.ts` from an LLM pass discussing the import).
- Therefore, cross-source SCA deduplication requires a dedicated helper pipeline.

---

## 2. Goals

1. **FR1 — Dedicated cross-source SCA dedupe:** Deduplicate findings across scanners and LLMs sharing the same advisory and package.
2. **FR2 — Authoritative severity rule:** Prefer scanner baseline severity over LLM self-reported severity. LLM passes cannot artificially escalate a known scanner vulnerability to Critical.
3. **FR3 — Schema backward compatibility (`evidenceSources`):** Add optional `evidenceSources: list[str]` to `Issue` while keeping `source: IssueSource` singular and primary. Ensure full backward compatibility for existing SARIF and JSON consumers.
4. **FR4 — Accurate advisory extraction:** Robustly extract advisory IDs (`CVE-*`, `GHSA-*`, `RUSTSEC-*`, `PYSEC-*`, `GO-*`) and package hints from LLM findings. If an LLM finding does not cite a recognizable advisory ID, leave it unmerged (no speculative merging).
5. **FR5 — Raw vs unique accounting:** `report.summary` and gate metrics reflect **unique** findings. Raw counts across tools are stored on the report/provenance so CLI and Markdown can render `Unique Critical/High: N (M raw)`.
6. **FR6 — Gate math integrity:** Ensure `compute_audit_metrics` evaluates deduplicated issues so penalties reflect unique risks.

---

## 3. Non-goals

- Merging general SAST/code quality findings across scanners and LLMs (handled separately by `cluster_near_duplicates`).
- Guessing advisory matches without explicit identifiers (e.g. fuzzy string matching on vulnerability descriptions).
- Overloading `cluster_near_duplicates` with SCA-specific rules.
- Local UI calibrations (`attack_surface=local_ui`), which are deferred to #17b.

---

## 4. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Deduping mechanism** | Dedicated `dedupe_cross_source_sca_issues` helper | Clean separation of concerns; avoids corrupting general theme clustering in `cluster.py`. |
| **Execution point** | After scanner + LLM issue merge, **before** `compute_audit_metrics` and `recount_summary` | Gate penalties and summary metrics must both compute on deduplicated issues. |
| **Cluster key** | `(ecosystem, normalized_package, advisory_id)` | Ecosystem + package + advisory ID uniquely identifies a dependency vulnerability across lockfiles and code references. |
| **Advisory regex** | `(CVE-\d{4}-\d{4,}\|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\|RUSTSEC-\d{4}-\d{4,}\|PYSEC-\d{4}-\d{4,}\|GO-\d{4}-\d{4,})` | Covers standard open-source advisory identifiers. Case-insensitive, matched on title, explanation, and details. |
| **Unmatched LLM findings** | Leave untouched | Strict safety: never merge an LLM finding on guesswork. |
| **Primary selection** | Prefer scanner finding over LLM finding | Scanners have authoritative package locations, CVE links, and CVSS scores. If multiple scanners match, prefer OSV over Trivy (existing rule). |
| **Severity resolution** | Keep scanner severity | Prevents LLM hallucinated severity inflation from blowing up gate penalties. If only an LLM reported the advisory, use the LLM's severity. |
| **Provenance tracking** | Add `evidenceSources: list[str] = Field(default_factory=list)` | Primary `source` remains an `IssueSource` enum (`scanner`, `llm`, `heuristic`). `evidenceSources` records all contributing origins (e.g. `["osv", "llm:p1"]`). |
| **Raw count preservation** | `rawCriticalHighCount: int | None = None` and `rawTotalFindings: int | None = None` on `FindingReport` | Allows CLI and Markdown reports to display `Unique Critical/High: N (M raw)` without keeping raw numbers only in prose. |
| **Language** | British English in user-facing strings | Project convention (`penalised`, `behaviour`). |

---

## 5. Architecture & Data Flow

```text
1. Run scanners (OSV, Trivy, Semgrep, Gitleaks, Checkov)
   → scanner_issues (already OSV ↔ Trivy deduped)

2. Run LLM passes (P1, P2, P3, domain packs)
   → llm_issues

3. Merge issues:
   merged_issues = list(llm_issues) + list(scanner_issues) + list(heuristic_issues)

4. Cross-source SCA Deduplication:
   deduped_issues, raw_crit_high, raw_total = dedupe_cross_source_sca_issues(merged_issues)

5. Pipeline State:
   report.issues = deduped_issues
   report.rawCriticalHighCount = raw_crit_high
   report.rawTotalFindings = raw_total
   report.summary = report.recount_summary()

6. Metrics Calculation:
   report = _apply_coverage_metrics(report, coverage, pass_confidences, issues=report.issues)
   # severity_finding_penalty now runs on unique findings!
```

---

## 6. Schema Changes & Backward Compatibility

### `src/repolens/schema.py`

```python
class Issue(BaseModel):
    # Existing fields (unchanged): severity, priority, category, file, line,
    # title, explanation, impact, recommendedFix, source: IssueSource | None, …
    # New optional field for multi-source provenance:
    evidenceSources: list[str] = Field(
        default_factory=list,
        description="All tools/passes that contributed evidence to this finding (e.g. ['osv', 'llm:p1']).",
    )
```

```python
class FindingReport(BaseModel):
    # Existing fields
    summary: Summary = Field(default_factory=Summary)
    issues: list[Issue] = Field(default_factory=list)
    ...
    # New raw count tracking:
    rawCriticalHighCount: int | None = Field(
        default=None,
        description="Raw count of Critical/High findings across all tools prior to deduplication.",
    )
    rawTotalFindings: int | None = Field(
        default=None,
        description="Raw count of total findings across all tools prior to deduplication.",
    )
```

### Backward Compatibility
- **JSON Export:** `evidenceSources` defaults to `[]`. Existing parsers expecting standard `Issue` fields ignore extra fields or receive an empty list if unspecified.
- **SARIF Export:** SARIF uses `source` to map tool rules. `evidenceSources` can be serialized into the SARIF property bag (`properties.evidenceSources`) without breaking SARIF 2.1.0 schema compliance.

---

## 7. Worked Example (LogViewer Scenario)

1. **Scanner Findings:**
   - OSV reports `GHSA-1234-5678-90ab` in `package-lock.json` (`express`) as `HIGH`.
   - Trivy reports `GHSA-1234-5678-90ab` in `package-lock.json` (`express`) as `HIGH`.
   - *OSV↔Trivy dedupe collapses these to 1 scanner finding.*
2. **LLM Findings:**
   - P1 (Security) pass analyzes `app.js`, notes express vulnerability from scanner context, and emits `GHSA-1234-5678-90ab in express` as `CRITICAL`.
3. **Before #14:**
   - Report has 2 findings for the same advisory: 1 High (scanner) + 1 Critical (LLM).
   - `severity_finding_penalty` applies: −20 (Critical) + −10 (High) = −30 penalty.
   - If two advisories repeat: −60 (Critical cap) + −20 (High) = −80 penalty! Gate collapses to 0–20%.
4. **After #14:**
   - Cross-source dedupe matches `(npm, express, GHSA-1234-5678-90ab)`.
   - Single primary issue kept: `HIGH` (scanner severity preferred).
   - `evidenceSources` stamped as `["osv", "llm:p1"]`.
   - Summary reflects: 1 High issue.
   - `rawCriticalHighCount = 2`, `uniqueCriticalHigh = 1`.
   - `severity_finding_penalty` applies: −10 (High) only.
   - Gate confidence remains honest and resilient (e.g. 70–75% instead of 20%).

---

## 8. Testing Strategy (TDD)

1. **Advisory extraction tests:**
   - Recognise `CVE-2024-12345`, `GHSA-xxxx-yyyy-zzzz`, `RUSTSEC-2023-0001`, `PYSEC-2022-43` in titles, descriptions, and details.
   - Handle case-insensitivity.
   - Return `None` when no valid advisory pattern exists.
2. **Primary selection & severity tests:**
   - Scanner finding + LLM finding with same advisory ID → keep scanner finding with scanner severity.
   - LLM finding with higher severity than scanner → demote to scanner severity.
   - LLM finding alone with advisory ID → kept as LLM finding with LLM severity.
   - Check `evidenceSources` contains both source tags.
3. **Pipeline metrics test:**
   - Assert `severity_finding_penalty` receives deduplicated issues.
   - Assert `report.rawCriticalHighCount` is populated.
   - Assert `report.summary` matches unique counts.
4. **General clustering separation:**
   - Verify `cluster_near_duplicates` still functions independently and does not interfere with SCA dedupe.

---

## 9. Exit Criteria

1. LogViewer-style test cases with dual scanner + LLM findings for the same advisory collapse to a single unique finding.
2. `severity_finding_penalty` is computed strictly over unique findings.
3. `Issue.evidenceSources` accurately lists contributing sources.
4. `report.rawCriticalHighCount` correctly records the raw finding count.
5. All unit and integration tests pass with zero regressions in existing SARIF/JSON schemas.
