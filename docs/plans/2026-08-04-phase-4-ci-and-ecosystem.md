# Phase 4 — CI & ecosystem Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD. Steps use checkbox syntax.

**Goal:** Ship GitHub Action + PyPI publish path + opt-in local learning + polish docs per [phase-4-ci-and-ecosystem.md](../design/phase-4-ci-and-ecosystem.md).

**Architecture:** Composite root `action.yml` installs RepoLens and runs CLI flags assembled by a pure Python helper (`repolens.ci_args`). Local learning stores keyword/TF-IDF in `.repolens/index.sqlite` (optional embeddings via `[local-ml]`). Release tags publish to PyPI via Trusted Publishing.

**Tech Stack:** Python 3.11+, Typer, GitHub Actions composite, PyPI Trusted Publishing, sqlite3 stdlib.

## Global Constraints

- Slim wheel stays free of native scanners and heavy ML; extras: `[scanners]`, `[local-ml]`
- Local learning default **off**; require consent flag/interactive yes
- Action `run=auto`: scanners always; LLM only if API key env present
- No LLM calls required in this repo’s default CI
- Vendor-neutral public docs

## File map

| Path | Responsibility |
|------|----------------|
| `src/repolens/ci_args.py` | Pure helpers: key detection + argv assembly for Action/scripts |
| `action.yml` | Composite GitHub Action |
| `.github/workflows/repolens-example.yml` | Example consumer workflow |
| `.github/workflows/publish.yml` | Tag → PyPI Trusted Publishing |
| `docs/ci.md` | Action + Bitbucket script |
| `docs/publishing.md` | Release / Trusted Publisher setup |
| `docs/local-learning.md` | Consent, storage, CLI |
| `src/repolens/learning/` | Index, memory, consent, retrieval |
| `examples/monorepo/` | Sample configs |
| `docs/review-confidence-log.md` | Confidence log template |

---

### Task 1: CI argv helper (TDD)

**Files:**
- Create: `src/repolens/ci_args.py`
- Test: `tests/test_ci_args.py`

**Produces:**
- `has_llm_api_key(environ: Mapping[str, str] | None = None) -> bool`
- `build_review_argv(*, mode: str, path: str, run: str, fail_on: str, scanners: str, require_scanners: bool, has_key: bool | None = None) -> list[str]`
- Raises `ValueError` when `run == "llm"` and no key

- [ ] Write tests for auto/dry-run/scanners-only/llm/fail-on/require-scanners
- [ ] Implement `ci_args.py`
- [ ] `pytest tests/test_ci_args.py -q` PASS
- [ ] Commit: `Add CI argv helper for GitHub Action flag assembly`

### Task 2: Composite Action + example workflow + docs/ci.md

**Files:**
- Create: `action.yml`, `.github/workflows/repolens-example.yml`, `docs/ci.md`
- Modify: `docs/README.md`, `.github/workflows/ci.yml` (require `docs/ci.md`, design phase-4)

**Behaviour:**
- Inputs per design; `install-from`: `git` (default until PyPI stable) | `pypi`
- Steps: setup-python 3.12 → pip install → optional plugins install --yes → `python -m repolens.ci_args` or bash calling `repolens` with argv from helper
- Prefer: `repolens` entry after install; assemble flags via `python -c 'from repolens.ci_args import build_review_argv; ...'`

- [ ] Add action.yml + example workflow + docs/ci.md (include Bitbucket script section)
- [ ] Update docs index + CI required files
- [ ] Commit: `Add GitHub Action and CI usage docs`

### Task 3: PyPI publish workflow + publishing docs

**Files:**
- Create: `.github/workflows/publish.yml`, `docs/publishing.md`
- Modify: `README.md` (pip install from PyPI note)

- [ ] Tag-triggered build + `pypa/gh-action-pypi-publish` with `id-token: write`
- [ ] Document Trusted Publisher one-time setup
- [ ] Commit: `Add PyPI Trusted Publishing workflow and docs`

### Task 4: Local learning core (TDD)

**Files:**
- Create: `src/repolens/learning/__init__.py`, `consent.py`, `index.py`, `memory.py`, `retrieve.py`
- Test: `tests/test_learning.py`
- Modify: `pyproject.toml` (`local-ml` extra), `pipeline.py`, `cli.py`, `config.py`

**Produces:**
- Consent gate + notice text
- SQLite keyword/TF-IDF index build/query
- `memory.toml` load/save
- `repolens learn build|status|clear`
- Pipeline enriches prompt when enabled + consented
- Optional embeddings stub/path when `[local-ml]` present

- [ ] Tests for consent, build, retrieve, clear
- [ ] Implement modules + CLI + pipeline hook
- [ ] `docs/local-learning.md`
- [ ] Commit: `Add opt-in local learning index and memory`

### Task 5: Polish

**Files:**
- Create: `examples/monorepo/README.md`, `examples/monorepo/.repolens.toml`, `docs/review-confidence-log.md`
- Modify: `docs/faq.md`, `docs/phases.md`, `docs/CHANGELOG.md`, `README.md`, design status

- [ ] Monorepo example + confidence log template
- [ ] Mark Phase 4 items done in phases.md
- [ ] Commit: `Polish Phase 4 docs, examples, and phase tracker`

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| Action + example workflow | 2 |
| docs/ci.md + Bitbucket script | 2 |
| PyPI Trusted Publishing | 3 |
| Local learning real + consent | 4 |
| Keyword + optional embeddings | 4 |
| Monorepo / confidence log / FAQ | 5 |
