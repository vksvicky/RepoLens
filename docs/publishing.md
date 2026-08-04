# Publishing RepoLens to PyPI

**Do not tag a release until you have dogfooded locally** (see [Pre-publish dogfood](#pre-publish-dogfood)) and completed Trusted Publisher setup below.

## Install paths

```bash
# From git (works before first PyPI upload)
pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"

# After first successful publish
pip install "repolens[scanners]==0.1.0a1"
```

## Release workflow (automated)

Tag a version matching `pyproject.toml` (e.g. `v0.1.0a1`) and push the tag.  
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) builds the sdist/wheel and uploads via **Trusted Publishing** (OIDC). No long-lived PyPI API token in GitHub secrets.

The publish Action is **pinned to a commit SHA** (`pypa/gh-action-pypi-publish@ed0c539…` = v1.13.0). Do not switch back to floating tags.

---

## One-time Trusted Publisher setup (UI)

Do these **once** before the first `v*` tag publish.

### A. GitHub environment `pypi`

1. Open **[Repo settings → Environments](https://github.com/vksvicky/RepoLens/settings/environments)**  
2. Click **New environment**  
3. Name it exactly: `pypi` (must match the workflow `environment: pypi`)  
4. Save. Optional: add required reviewers for production later; for alpha you can leave it open.

### B. PyPI pending publisher

1. Log in at [pypi.org](https://pypi.org/) (create an account if needed; enable 2FA).  
2. Open **[Publishing](https://pypi.org/manage/account/publishing/)** (Account settings → Publishing).  
3. Under **Add a new pending publisher** → **GitHub**, fill in:

   | Field | Value |
   |-------|--------|
   | PyPI Project Name | `repolens` |
   | Owner | `vksvicky` |
   | Repository name | `RepoLens` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

4. Submit. Status should show **Pending** until the first successful tag-triggered upload.

> Pending publishers register the project name. The first green Publish workflow creates the project and activates the trust relationship.

### C. Optional: TestPyPI first

Same form on [test.pypi.org publishing](https://test.pypi.org/manage/account/publishing/) if you want a dry-run. That needs a separate workflow or a temporary `repository-url` on the publish Action — not configured by default. Prefer local dogfood (below) + prod Trusted Publisher for the first alpha.

### D. First release (only after dogfood + pending publisher)

```bash
# On main, clean working tree, version already 0.1.0a1 in pyproject.toml
git tag v0.1.0a1
git push origin v0.1.0a1
```

1. Watch **Actions → Publish** for the tag.  
2. Confirm https://pypi.org/project/repolens/  
3. Smoke: `pip install "repolens==0.1.0a1" && repolens version`

---

## Pre-publish dogfood

Run these on **this repo** (or another of yours) before tagging. For reviewing any local project with generic paths, see **[try-on-your-repo.md](./try-on-your-repo.md)**.

From a RepoLens clone with the package installed editable (replace `[username]`):

```bash
cd /Users/[username]/Development/RepoLens
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1) Version + inventory
repolens version
repolens review --path . --out ./reports-dogfood --dry-run

# 2) Plugins (consent skipped with --yes; verifies checksums + HTTPS)
repolens plugins status
repolens plugins install all --yes
repolens plugins status

# 3) Scanners-only (no LLM key required)
repolens review --path . --out ./reports-dogfood --scanners-only --fail-on ""

# 4) CI argv assembly (what the GitHub Action uses)
python - <<'PY'
from repolens.ci_args import build_review_argv
print(build_review_argv(run="dry-run", fail_on=""))
print(build_review_argv(run="auto", has_key=False, fail_on=""))
PY

# 5) Optional: full LLM review if you have a key / Ollama configured
# repolens review --path . --out ./reports-dogfood --scanners auto
```

**Pass criteria**

| Check | Expect |
|-------|--------|
| Dry-run | Exit 0; Markdown under `reports-dogfood/` |
| Plugins install | gitleaks + osv (and semgrep via pip) available or clear install errors |
| Scanners-only | Exit 0 (or 1 only if you set `--fail-on` and findings exist); report has **Automated scanners** |
| `ci_args` | Prints sensible `repolens …` argv lists |
| pytest / ruff | `pytest -q` and `ruff check src tests` green |

Also exercise the Action on GitHub (workflow_dispatch on [repolens-example.yml](../.github/workflows/repolens-example.yml)) after pushing — `run: dry-run` should stay green without API keys.

---

## Version checklist

- [ ] Pre-publish dogfood passed (above)  
- [ ] GitHub environment `pypi` exists  
- [ ] PyPI pending publisher saved for `repolens` / `publish.yml` / `pypi`  
- [ ] Version in `pyproject.toml` + `src/repolens/__init__.py` matches the tag  
- [ ] [CHANGELOG.md](./CHANGELOG.md) updated  
- [ ] Tag `vX.Y.ZaN` and `git push origin <tag>`  
- [ ] Publish workflow green; package visible on PyPI  
- [ ] `pip install repolens==…` smoke test  
- [ ] Document Action pin: `uses: vksvicky/RepoLens@vX.Y.ZaN`

## Related

- [ci.md](./ci.md) — GitHub Action  
- [scanners.md](./scanners.md) — plugins / Semgrep config  
- [phases.md](./phases.md)  
- [reviews/gate_review_report_2026-08-04.md](./reviews/gate_review_report_2026-08-04.md) — pre-publish security gate  
