# Publishing RepoLens to PyPI

Alpha installs can use git until the first upload succeeds:

```bash
pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
# after publish:
pip install "repolens[scanners]==0.1.0a1"
```

## Release workflow

Tag a version matching `pyproject.toml` (e.g. `v0.1.0a1`) and push the tag.  
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) builds the sdist/wheel and uploads via **Trusted Publishing** (OIDC). No long-lived PyPI token in GitHub secrets.

## One-time Trusted Publisher setup (manual)

1. Create the project on [PyPI](https://pypi.org/) (or first upload will create it if allowed).  
2. Project → **Publishing** → **Add a new pending publisher**:  
   - Owner: `vksvicky`  
   - Repository: `RepoLens`  
   - Workflow: `publish.yml`  
   - Environment: `pypi`  
3. In GitHub → **Settings → Environments → pypi** (create if missing). Optionally require reviewers.  
4. Push tag `v0.1.0a1` and confirm the Publish workflow is green.

## Version checklist

- [ ] Bump `version` in `pyproject.toml` / `src/repolens/__init__.py` if needed  
- [ ] Update [CHANGELOG.md](./CHANGELOG.md)  
- [ ] Tag `vX.Y.Z` (or `vX.Y.ZaN`) and `git push origin vX.Y.Z`  
- [ ] Verify package page on PyPI  
- [ ] Point Action consumers at the tag: `uses: vksvicky/RepoLens@vX.Y.Z`

## Related

- [ci.md](./ci.md) — Action `install-from: pypi`  
- [phases.md](./phases.md)  
