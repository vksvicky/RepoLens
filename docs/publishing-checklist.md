# Publishing this repo to GitHub

When you create the remote (e.g. `gh repo create`):

1. Owner links use `vksvicky/RepoLens` in issue templates (update if the repo is transferred).
2. Add a real security contact in `docs/SECURITY.md` if not using private vulnerability reporting alone.
3. Enable:
   - Issues & Discussions (optional but recommended)
   - Private vulnerability reporting
   - Branch protection on `main` (require PR + CI) when you have collaborators
4. Push `main` and confirm the Actions “Docs sanity” workflow is green.
5. Add topics on GitHub, e.g. `cli`, `security`, `code-review`, `architecture`, `audit`, `opensource`.
6. Update README badges with the real `owner/RepoLens` path when you add them.

## After CLI / CI are green

7. Confirm Actions **Docs sanity** + **Python** jobs are green on `main`.  
8. From a clean clone: `pip install -e ".[dev]" && pytest -q && repolens version`.  
9. For a PyPI release: tag the version in `pyproject.toml` — current release is `v0.1.6.post1`. See [publishing.md](./publishing.md). Do not move `v0.1.6`.  
10. Point Action consumers at that tag: `uses: vksvicky/RepoLens@v0.1.6.post1` (or `@main` while iterating).

