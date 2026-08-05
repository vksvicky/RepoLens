# Self-review hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear dogfood noise, close Highs, harden guided script, split mega-files (PR 1→4).

**Architecture:** Inventory/heuristic ignore rules first; then guided-script helpers; then behaviour-preserving module splits; docs last. Spec: [2026-08-05-self-review-hardening-design.md](../specs/2026-08-05-self-review-hardening-design.md).

**Tech Stack:** Python 3.11+, pytest, existing RepoLens inventory/heuristics/config.

## Global Constraints

- British English in report/heuristic prose  
- Preserve public entry points (`repolens.cli:app`, etc.) on splits  
- TDD for new ignore/heuristic behaviour  
- Do not commit secrets; SECURITY.md prefers GitHub PVR  

---

## PR 1 — Noise & truth

### Task 1: Inventory ignore `.superpowers`

- [x] Add failing test in `tests/test_inventory.py` that a file under `.superpowers/` is not listed  
- [x] Add `.superpowers` to `IGNORE_DIR_NAMES` in `src/repolens/inventory.py`  
- [x] Run `pytest tests/test_inventory.py -q`

### Task 2: Mega-file default exclude for `.superpowers`

- [x] Extend `DEFAULT_MEGA_FILE_EXCLUDES` with `**/.superpowers/**`  
- [x] Update `.repolens.example.toml` comment list  
- [x] Test exclude match in `tests/test_heuristics.py`

### Task 3: Skip fixtures for sibling + scripts_hygiene

- [x] Helper `is_test_fixture(relative) -> bool` for `tests/fixtures/`  
- [x] Apply in `siblings.py` and `scripts_hygiene.py`  
- [x] Failing then passing tests

### Task 4: Narrow scripts_hygiene to scripts (not pedagogical markdown)

- [x] Remove `.md`/`.txt`/`.rst` from suffixes (keep shell/ps1 + notarize name)  
- [x] Tests: playbook `.md` with “password” → no issue; `.sh` without keychain → issue  

### Task 5: SECURITY.md + playbook scanner note

- [x] `docs/SECURITY.md`: drop placeholder email; state PVR as primary  
- [x] `playbooks/security.md` + `src/repolens/playbooks/security.md` + rules default: mature scanners bullet  
- [x] FAQ one-liner pointing at self-review hardening spec  

### Task 6: Verify PR 1

- [x] `pytest tests/test_inventory.py tests/test_heuristics.py -q`  
- [ ] Commit PR 1 slice (user-requested commit only)

---

## PR 2 — Guided script (after PR 1)

- [ ] `_run_capture` helper + High subprocess fixes  
- [ ] URL validation; `_prompt_text` empty edge  
- [ ] Tests in `tests/test_guided_script.py`

## PR 3 — Mega-file splits (after PR 2)

- [ ] Split `cli.py` / `llm.py` / `pipeline.py` / guided script per design table  
- [ ] Re-exports; full pytest green per family  

## PR 4 — Docs polish

- [ ] `docs/try-on-your-repo.md` Low nits  
