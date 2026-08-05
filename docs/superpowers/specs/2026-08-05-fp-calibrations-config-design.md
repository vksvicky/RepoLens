# FP calibrations via `[deep]` config

**Status:** Approved in chat 2026-08-05 (approach B — config-native; no rules-pack dual path)  
**Language:** British English in user-facing docs/prose.

## Goal

Reduce known LLM false positives (starting with list-form `subprocess` “command injection”) for **all** RepoLens users, with enable/disable stored in the same place as other deep settings — not a parallel rules pack that would need migration later.

## Non-goals

- Rules-registry / `calibrations.json` pack (approach A) or dual storage  
- Migration, roll-forward, or left-behind compatibility layers  
- CLI flags for individual calibrations  
- Per-finding dismiss memory (later phase)  
- Claiming zero false positives from LLM-only analysis  
- Retry libraries / rewriting safe user code to silence the model

## Design

### Config surface

Extend `DeepConfig` with an optional map of calibration id → bool:

```toml
[deep]
# fp_calibrations = { subprocess_list_not_injection = true }
```

| Behaviour | Result |
|-----------|--------|
| Key omitted | Packaged default for that id (see table) |
| `true` | Calibration runs |
| `false` | Calibration skipped |
| Unknown id | Ignored (forward-compatible; no error) |

User config and project `.repolens.toml` merge like other `[deep]` keys (existing merge rules). No new trust restriction — these are not credential fields.

### Packaged defaults (code constant)

| Id | Default | When enabled |
|----|---------|--------------|
| `subprocess_list_not_injection` | `true` | For issues with category suggesting injection (`sec.injection` or title/category containing “command injection” / `subprocess`) **and** severity Critical/High/Medium: if the issue’s `codeExample` / `explanation` / file context shows list-form `subprocess.run`/`Popen` (or equivalent argv list) **and** no `shell=True`, **demote to Low** and prefix explanation with `[calibrated: subprocess_list_not_injection]`. |

Resolution helper: `effective_fp_calibrations(cfg.deep) -> dict[str, bool]` merges defaults with config overrides.

### Prompt steering (not separately toggleable in v1)

Add a short anti-FP note to packaged security playbook / rules body:

> List-form `subprocess.run(argv, …)` / `shell=False` (Python default) is **not** command injection. Only flag when `shell=True` or a single shell string is executed. Prefer Semgrep/OSV evidence for real injection.

Same text in `playbooks/security.md` and `src/repolens/playbooks/security.md` / rules default if they diverge today — keep them aligned.

### Pipeline hook

After deep (or single-shot) LLM issues are merged and band-coerced, before coverage/metrics:

```text
issues → apply_fp_calibrations(issues, cfg.deep) → continue
```

Heuristics and scanner findings are **not** passed through these calibrations (LLM FP class only). If a future calibration needs scanner scope, add an explicit flag then — not now.

### Module layout

- `src/repolens/fp_calibrations.py` — defaults, resolve, `apply_fp_calibrations`
- `DeepConfig.fp_calibrations: dict[str, bool] = {}` (empty = use all defaults)
- Example comment in `.repolens.example.toml`
- FAQ one-liner under metrics / dogfood noise

### Tests (minimal)

1. Default: calibration on → matching High injection demoted to Low  
2. `fp_calibrations = { subprocess_list_not_injection = false }` → no-op  
3. Config load accepts the map from TOML  

No golden full-pipeline dogfood required for merge.

## Success criteria

1. Enabled by default: list-form subprocess injection Highs from local LLMs demoted for every user.  
2. Users can disable via `[deep].fp_calibrations` without code changes.  
3. No second storage system; no migration story.  
4. Security playbook steers the model before emit.

## Sequencing

1. Spec (this doc)  
2. Implement config + module + playbook note + minimal tests  
3. Optional later: more calibration ids, CLI UX, dismiss memory  
