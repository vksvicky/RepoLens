# Robust product bar

Short, manual quality bar for calling a RepoLens release "robust". Not automated: it needs a local model and real repos.

## Bar

1. **Three clean deep dogfoods** — one Python, one TypeScript, one Go repository, each reviewed with `--deep` and reaching a finished report with:
   - no `pass_degraded` caused by schema or packaging (null/empty `codeExample`, string confidence, fenced JSON, prose around JSON);
   - `AI DEEP AUDIT` showing percentages for P1, P2 and P3 (no `INCOMPLETE` / `UNVERIFIED` unless the cause is a documented timeout or transport failure);
   - at most one micro-repair per pass (`llmRepairAttempts` ≤ 1 per pass).
2. **No packaging-driven gate zero** — a gate of `0%` must come from answered checklist ids or open Critical/High findings, never from a parse failure, a missing field, or an unfinished pass. Unfinished passes report INCOMPLETE, not `0%`.
3. **Gate honesty** — the deterministic gate (scanners + Fast Brain) is unaffected by AI-audit degradation; it never reads as "% secure".
4. **Immunity suite green** — `tests/test_llm_parse.py` (schema immunity) passes with no skipped cases.

## Manual dogfood checklist

Set `TARGET` first (`echo "$TARGET"`); do not hard-code paths.

- [ ] Python repo: `repolens review --path "$TARGET" --out "$TARGET/reports" --deep --timeout 1800`
- [ ] TypeScript repo: same command against a TS target
- [ ] Go repo: same command against a Go target
- [ ] For each report: confirm the `Gate and AI audit` block, no `pass_degraded`/`llm.schema_invalid` durability gaps, and band percentages present
- [ ] For any degraded pass: inspect `.repolens/last_llm_raw_<pass>.txt`, add the payload shape to the immunity suite, then `--resume --retry-pass <pass>`
- [ ] Record confidence and findings in `docs/review-confidence-log.md`

## Verification matrix

```bash
pytest tests/test_llm_parse.py tests/test_metrics.py tests/test_pipeline_deep.py \
  tests/test_pipeline_deep_resume.py tests/test_ci_args.py tests/test_presets.py \
  tests/test_report.py -q
```

## Out of scope

- Raising heuristic thresholds or hiding near-clones with exclude globs to reach a clean run.
- Swapping the local model for a cloud default.
- Changing scanner plugin install UX.

See also: [FAQ — metrics](../faq.md#what-do-report-metrics-mean-confidence-vs-security).
