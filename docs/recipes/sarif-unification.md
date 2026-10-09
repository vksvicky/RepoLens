# Recipe: Unify CodeQL / Sonar / ESLint SARIF into one executive audit

**Positioning:** RepoLens **imports and complements** SAST engines — it does **not** displace CodeQL, SonarQube, ESLint, or Semgrep. Keep those in CI; fold their SARIF into one P1→P3 gate report with cyclicity, remediation narrative, and `--fail-on`.

**Related:** [ci.md — import third-party SARIF](../ci.md#import-third-party-sarif) · [scanners.md](../scanners.md#import-third-party-sarif-codeql-sonar-eslint-) · [sample report](../../reports/samples/sample_audit_report.md)

---

## What you get

| Input | RepoLens adds |
|-------|----------------|
| CodeQL / Sonar / ESLint / … SARIF dumps | Merge + dedupe into one finding list |
| Your tree | Fast Brain heuristics + Python import **cyclicity** |
| Optional BYOK / Ollama | Executive narrative, Critical/High code examples |
| Optional `--fail-on HIGH` | Single CI gate over unified evidence |

---

## 1) Produce SARIF from tools you already run

Examples (keep whatever your org already uses):

```bash
# CodeQL (illustrative)
codeql database analyze db codeql/python-queries --format=sarif-latest -o codeql.sarif

# Sonar / SonarScanner — export or download the task SARIF
# ESLint
npx eslint . -f @microsoft/eslint-formatter-sarif -o eslint.sarif
```

For a **local dry demonstration** without those CLIs, use the tiny fixtures in this repo:

- `tests/fixtures/sarif/minimal_codeql.sarif.json`
- `tests/fixtures/sarif/minimal_sonar.sarif.json`
- `tests/fixtures/sarif/minimal_eslint.sarif.json`

---

## 2) Import into a scanners-only (or full) review

```bash
# From a RepoLens clone — demo against fixtures + a tiny path
TARGET="${TARGET:-.}"

repolens review \
  --path "$TARGET" \
  --out "$TARGET/reports" \
  --scanners-only \
  --import-sarif tests/fixtures/sarif/minimal_codeql.sarif.json \
  --import-sarif tests/fixtures/sarif/minimal_sonar.sarif.json \
  --import-sarif tests/fixtures/sarif/minimal_eslint.sarif.json \
  --require-sarif-import \
  --format both \
  --sarif
```

**Expected narrative outcomes** (fixture demo):

1. **Imported findings appear** under P1/P2/P3 with `source` reflecting the third-party tool (CodeQL / Sonar / ESLint).
2. **Dedupe** collapses near-identical locations when fingerprints collide across runs/tools (exact rules vary by path/rule id).
3. **Cyclicity / architecture** still come from RepoLens Fast Brain + import graph — SARIF engines rarely ship that signal.
4. Gate report Markdown under `--out` is the **executive** artifact; optional SARIF out is for GitHub code scanning upload.

CI-hardened variant (fail if a path is missing):

```bash
repolens review --path "$TARGET" --out "$TARGET/reports" --scanners-only \
  --import-sarif "$TARGET/codeql.sarif" \
  --import-sarif "$TARGET/sonar.sarif" \
  --require-sarif-import \
  --fail-on HIGH --ci --format both --sarif
```

More vendor one-liners: [ci.md](../ci.md#import-third-party-sarif).

---

## 3) Optional: add Slow Brain narrative (BYOK)

After scanners + imports look right:

```bash
repolens review --path "$TARGET" --out "$TARGET/reports" \
  --import-sarif tests/fixtures/sarif/minimal_codeql.sarif.json \
  --import-sarif tests/fixtures/sarif/minimal_sonar.sarif.json \
  --preset changed   # or: repolens audit for release defaults
```

Prefer **cloud BYOK** for minutes-scale narrative; local 32B Ollama is the air-gap path (often hours). See [setup — recommended daily path](../setup-ai-and-scanners.md#recommended-daily-path).

---

## 4) README walkthrough (short)

1. Keep CodeQL/Sonar/ESLint in CI as today.  
2. Archive their `.sarif` next to the job.  
3. Run `repolens review --import-sarif … --scanners-only` (PR) or `repolens audit` (release).  
4. Ship the Markdown/PDF gate report to auditors; upload RepoLens SARIF only if you want a second code-scanning channel.  
5. Do **not** turn off CodeQL/Sonar — RepoLens is the unification layer, not a replacement.

---

## Honesty checklist

- [ ] Org still runs at least one first-party SAST on every PR  
- [ ] `--require-sarif-import` used when the import is load-bearing for the gate  
- [ ] Gate confidence read as **package adequacy**, not “% secure”  
- [ ] Cyclicity ratchet (`repolens check --diff`) separate from SARIF import  
