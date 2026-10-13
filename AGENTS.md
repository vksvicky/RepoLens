# AGENTS.md

## Repository Overview
RepoLens is an in-repo static audit and review engine built in Python.
The scanner catalog is closed strictly to: **Gitleaks**, **Semgrep**, **OSV**, **Trivy**, and **Checkov**.
All other external tools or signals enter as imported SARIF (`--import-sarif`), normalized into RepoLens's standard issue model.

## Setup & Supported Python Versions
- **Supported Python**: `>=3.11` (`pyproject.toml`). GitHub Actions CI (`.github/workflows/ci.yml`) matrix runs **Python 3.11, 3.12, and 3.13**.
- **Local Environment Setup**:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -e ".[dev]"
  ```

## Critical Build & Test Commands
- **Full CI Verification ("Done" Gate)**:
  ```bash
  ./scripts/ci-check.sh
  ```
  Runs `ruff check src tests` followed by `pytest -q`. Matches the GitHub Actions Python job.
- **Coverage (Informational)**:
  ```bash
  ./scripts/coverage.sh
  ```
  Writes `coverage/html/index.html` and `coverage/coverage.xml`. Does not fail the run; CI does not run it.
- **Targeted Fast Checks (while editing specific modules)**:
  - CLI & which: `./.venv/bin/pytest tests/test_which.py tests/test_resolved_argv.py -q`
  - Right-BICEP & Heuristics: `./.venv/bin/pytest tests/test_right_bicep_scenarios.py tests/test_heuristics.py -q`
- **Local student notes** (gitignored; not in CI): `./.venv/bin/python3 scripts/generate_learn_file_notes.py --check` fails when `docs/learn` has drifted. Regenerate with `./.venv/bin/python3 scripts/generate_learn_file_notes.py`.

## Style Rules & Code Conventions
- **Linter & Formatter**: Ruff configured in `pyproject.toml` (target Python 3.11, line length 100, rules `E, F, I, UP, B` with `B008` ignored for Typer CLI options).
- **Line Length Exception**: `scripts/generate_learn_file_notes.py` is permitted to exceed the 100-character line limit (`per-file-ignores = ["E501"]`).
- **Tests**: Place all tests in `tests/` following existing pytest conventions. New production logic must always have a failing test first.

## Files Agents Must Not Hand-Edit
- **Local-only docs** (gitignored, never commit): `docs/learn/`, `docs/plans/`, `docs/superpowers/` (this is where agent plans and specs live; `docs/plans/` is the older plan folder), `docs/recipes/`, `docs/reviews/`, and `.superpowers/`.
- **Generated Learn Notes**: Never edit files in `docs/learn/src/` or `docs/learn/tests/` manually. They are generated deterministically by `scripts/generate_learn_file_notes.py`.
- **Handwritten Course Notes**: `docs/learn/00-start-here.md` through `docs/learn/06-order-complexity-and-your-own-model.md` are written by hand and are outside `--check`.
- **Changelog**: Add user-visible features and fixes as bullets under `## [Unreleased]` in `docs/CHANGELOG.md`.
- **Package Version**: The version in `pyproject.toml` remains `0.1.3` until an explicit release is requested.

## Architecture & Review Contracts
- **Review Target Path**: When testing review runs against dogfood repositories, use `$TARGET` (`--path "$TARGET"` and `--out "$TARGET/reports"`).
- **Expanded Argv Contract**: Provenance records exact reproducible flag tokens via `build_expanded_argv()`. Preset deltas only fill flags at their CLI default (explicit flags always win). Strip credentials, query parameters, and fragments from HTTP/S URLs.
- **Exit Code Semantics**:
  - `0`: Run succeeded without gate failures.
  - `1`: Gate failure (`--fail-on` triggered or ratchet budget breached).
  - `2`: Bad input or CLI argument failure (unknown preset, invalid scenario name).
- **Fast Brain Heuristics**: Modules in `src/repolens/heuristics/` must be pure stdlib (regex/stat/line checks, no heavy external dependencies), executed concurrently via `ThreadPoolExecutor` (8 threads).
