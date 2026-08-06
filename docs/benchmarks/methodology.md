# RepoLens public benchmark methodology (pre-registered)

**Status:** Pre-registered for Phase 6.6 (2026-08-06).  
**Design:** [phase-6.x §6.6](../design/phase-6.x-scanner-depth-ci-gates-and-credibility.md)  
**Results:** [results/mvp-2026-08-06.md](./results/mvp-2026-08-06.md)

This document locks definitions **before** claiming win/loss numbers. We do **not** lead with synthetic-suite F1 alone. Headline story: developers **fix** true positives faster because of explanation + code examples.

---

## 1. Goal

Compare RepoLens (with optional companion scanners) to free baselines on:

1. **Remediation** (primary)
2. **Detection** (supporting)
3. **CI cost / latency** (supporting, especially triage)

Honest losses (e.g. lower raw recall than CodeQL on a CWE subset) are published alongside wins.

---

## 2. Headline metrics (primary)

| Metric | Definition | Notes |
|--------|------------|--------|
| **Remediation rate** | Among findings labelled **true positive** by the study adjudicator, the % for which a blinded developer produces a **correct fix** (or accepts a correct suggested fix) within a fixed time window | Window default: **30 minutes** per finding batch cap (see protocol) |
| **MTTR** | Mean wall-clock from first exposure to the finding (tool UI / report open) until a correct fix is committed **or** the participant states a correct remediation plan scored by the adjudicator | Failures / timeouts count as uncapped at window length for rate; excluded from MTTR mean or reported separately as “timed out” |
| **Suggested-fix apply %** | Where the tool offered a concrete code example / patch: % of TPs where the participant **applies or lightly adapts** that example (≤ trivial edits) rather than rewriting from scratch | RepoLens Critical/High require `codeExample` by schema; Semgrep/CodeQL often have rule help only |

### What is not a headline

- Precision / Recall / F1 on synthetic corpora  
- Actionability Likert scores  
- `repolens score-report` readiness %  

Those are **supporting** (§4).

---

## 3. Remediation study protocol (human)

### 3.1 Participants

- ≥ 3 developers familiar with the language of the corpus task (intern / mid / senior mix OK).  
- Blinded to tool brand where practical (generic labels: Tool A / B / C).  
- Same machine class and internet policy for all arms.

### 3.2 Arms (configs)

| Arm | Config |
|-----|--------|
| Semgrep CE | Default or documented ruleset; no LLM |
| CodeQL | Default security suite for the language; no LLM |
| RepoLens scanners-only | `--scanners-only` with declared plugin set |
| RepoLens LLM-only | No scanners (or scanners disabled) |
| RepoLens combined | Scanners + LLM (deep default) |
| RepoLens triage CI | `--ci` (+ declared `--fail-on` / severity floor) |

Each published table row must name the **exact CLI / workflow** and tool versions.

### 3.3 Task flow (per finding or small batch)

1. Adjudicator marks TP / FP / unknown **before** timing starts (or on a frozen finding set).  
2. Participant opens only that arm’s artifact (SARIF / Markdown / IDE).  
3. Timer starts.  
4. Participant attempts fix in a clean checkout.  
5. Stop on correct fix, correct plan (adjudicator score ≥ 4/5), or window expiry.  
6. Record: outcome, seconds, whether suggested fix was applied, free-text notes.

Worksheet: [templates/remediation-study-row.json](./templates/remediation-study-row.json).

### 3.4 Hit definition (detection support)

A **hit** for P/R is a finding that maps to a ground-truth defect via:

- Same file + line within ±3 **or** same CWE/rule id on the ground-truth region, **and**  
- Severity ≥ agreed floor for that corpus (default: Medium for synthetic; High for CVE set).

Duplicates collapsed by (tool, file, rule/CWE, nearest line).

---

## 4. Supporting metrics

| Metric | Definition |
|--------|------------|
| Precision / Recall / F1 | Per corpus; macro and micro; variance across ≥ 3 LLM runs when LLM involved |
| Actionability (1–5) | Human rating of explanation + fix clarity |
| Suggested-fix readiness | % of report issues with non-empty `codeExample` — `repolens score-report` |
| Location verified rate | % LLM/heuristic issues with `locationVerified=true` (SARIF path) |
| CI wall time | Scanners phase + optional LLM; triage bypass rate |

---

## 5. Corpora (MVP)

| Corpus | Role | Status |
|--------|------|--------|
| OWASP Benchmark and/or Juliet **subset** | Detection P/R support | Planned; pin commit SHA when first run |
| Small **real-CVE** set (3–10 CVEs with known patches) | Remediation realism | Planned |
| Juice Shop / WebGoat (qualitative) | Narrative / timed walkthrough | Optional |
| **RepoLens dogfood** (this repo) | Latency + readiness proxies | Used in MVP results |

Pre-registration rule: corpus pin + exclude list published **before** scoring a “v1” detection table. Until then, detection cells stay **TBD**.

---

## 6. Comparators & fairness

- Prefer free tiers: **Semgrep CE**, **CodeQL** (GHAS free for public repos / local CLI).  
- Do not tune RepoLens playbooks on the evaluation corpus after freezing.  
- LLM temperature / model id recorded; Ollama vs cloud called out.  
- No cherry-picking only easy CWEs for the headline remediation table.

---

## 7. Publish path & honesty

- Methodology: this file.  
- Results: `docs/benchmarks/results/*.md`.  
- Losses included (e.g. “CodeQL higher recall on X”).  
- Partial dogfood allowed for MVP exit; must be labelled **proxy / partial**, never as completed human remediation study.

---

## 8. Tooling helpers

```bash
# Supporting readiness metrics from a FindingReport JSON
repolens score-report path/to/report.json
repolens score-report path/to/report.json --json
```

Library: `repolens.benchmark.score_actionability`.
