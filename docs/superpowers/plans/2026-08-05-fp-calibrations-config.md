# FP calibrations (`[deep].fp_calibrations`) Implementation Plan

> **For agentic workers:** Spec: [2026-08-05-fp-calibrations-config-design.md](../specs/2026-08-05-fp-calibrations-config-design.md).

**Goal:** Config-toggleable post-LLM demotion of list-form subprocess “injection” FPs; playbook anti-FP note; no dual storage.

## Tasks

### Task 1: Module + tests (TDD)

- [x] `tests/test_fp_calibrations.py` — default demotes High; disabled = no-op
- [x] `src/repolens/fp_calibrations.py` — defaults, resolve, apply

### Task 2: Config + example

- [x] `DeepConfig.fp_calibrations: dict[str, bool]`
- [x] `.repolens.example.toml` comment
- [x] Config load test

### Task 3: Pipeline + playbook

- [x] Apply after LLM merge / single-shot analyse (recount summary)
- [x] Security playbook + rules default anti-FP note
- [x] FAQ one-liner

### Task 4: Verify

- [x] `pytest tests/test_fp_calibrations.py tests/test_config.py -q`
