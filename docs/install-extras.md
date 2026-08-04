# RepoLens install extras (`[dev]`, `[scanners]`, …)

## What this is (and is not)

`[dev]`, `[scanners]`, and `[local-ml]` are **optional pip extras for the RepoLens package itself**.

| | |
|--|--|
| **They live in** | This repository’s [`pyproject.toml`](../pyproject.toml) → `[project.optional-dependencies]` |
| **They apply when** | You **install RepoLens** (`pip install …`) |
| **They do not live in** | The projects you *review* (`acme-api`, etc.) — those apps do not need a `[dev]` extra for RepoLens to work |

So this is **not** “project-to-project” for every repo on your machine. Only people who install or develop **RepoLens** choose these extras. When you run `repolens review --path /path/to/acme-api`, you are using the already-installed CLI; `acme-api` does not define `[dev]` / `[scanners]`.

<!-- BEGIN optional-dependencies -->
## What each extra installs

**Source of truth:** [`pyproject.toml`](../pyproject.toml). If this table disagrees, trust that file and update this page. CI (`tests/test_docs_extras.py`) fails when a package from `pyproject.toml` is missing below.

| Extra | Install (from a RepoLens clone) | Packages pulled in | Purpose |
|-------|----------------------------------|--------------------|---------|
| **dev** | `pip install -e ".[dev]"` | `pytest`, `pytest-cov`, `ruff`, `mypy` | Tests + lint for RepoLens contributors / dogfood |
| **scanners** | `pip install -e ".[scanners]"` | `semgrep` only | Semgrep via pip — **not** gitleaks/osv |
| **local-ml** | `pip install -e ".[local-ml]"` | `sentence-transformers` | Optional local learning embeddings |

Combine: `pip install -e ".[dev,scanners]"`.  
Runtime only: `pip install -e .`

### After PyPI (same extra names)

```bash
pip install "repolens[scanners]==0.1.0a1"
pip install "repolens[dev]"          # if published with that extra
```

From git without a local clone:

```bash
pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
```
<!-- END optional-dependencies -->

## Scanners: pip extra vs `plugins install`

| Tool | How you get it |
|------|----------------|
| Semgrep | `pip install "repolens[scanners]"` **or** `repolens plugins install semgrep` |
| gitleaks, osv-scanner | `repolens plugins install …` (native binaries) — **not** in the `[scanners]` pip extra |

Details: [scanners.md](./scanners.md).  
Cross-OS walkthrough: [try-on-your-repo.md](./try-on-your-repo.md).
