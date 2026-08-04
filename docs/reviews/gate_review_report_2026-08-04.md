# Gate review report — 2026-08-04

**Repo / branch:** RepoLens / `main`  
**Commit / WIP:** `6c9cc10` (Phases 3–4 vs `87b4cae`)  
**Scope:** Retroactive dual-review of Phase 3 scanners + Phase 4 CI/Action/local learning (gate was skipped at commit/push time)  
**Confidence:** 78%  
**Commit go/no-go:** n/a (already committed)  
**Push go/no-go:** already pushed with override; **no further push** until Medium items below addressed or accepted  

## Executive summary

- P1: Critical 0 · High 0 · Medium 3 · Low 2  
- P2: Medium 1 · Low 1  
- P3: Medium 1 · Low 1  
- Top risks: plugin downloads without checksums; floating PyPI publish Action tag; Action `git-repository` input not restricted to HTTPS  

Evidence: `pytest` 80 passed · `ruff` clean  

## P1 — Security findings

### [MEDIUM] Plugin downloads lack checksum verification
- **Priority:** P1  
- **File:** `src/repolens/plugins.py`  
- **Line:** 187–198  
- **Explanation:** `plugins install` pins release URLs and enforces HTTPS (+ redirect check) and safe archive extract, but does not verify SHA-256 of the downloaded artifact before chmod + exec / pip install.  
- **Impact:** Compromised GitHub release asset or MITM after TLS termination at a broken mirror could yield a malicious scanner binary, especially with Action `install-plugins: true` + `--yes`.  
- **Recommended fix:** Add per-asset digests in `catalog()` and verify after download; fail closed on mismatch.  
- **Code example:**

```python
import hashlib

def _download(url: str, dest: Path, *, sha256: str | None = None) -> None:
    if not url.startswith("https://"):
        raise RuntimeError("refusing non-HTTPS plugin download URL")
    # ... stream to dest ...
    if sha256:
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if digest != sha256:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {url}: got {digest}")
```

- **Fix timing:** before launch (before recommending `--yes` / PyPI consumers)

### [MEDIUM] Publish workflow pins floating Action tag
- **Priority:** P1  
- **File:** `.github/workflows/publish.yml`  
- **Line:** 36  
- **Explanation:** `pypa/gh-action-pypi-publish@release/v1` follows a moving tag. A compromised tag could publish a trojaned package under Trusted Publishing.  
- **Impact:** Supply-chain compromise of the first (and later) PyPI releases.  
- **Recommended fix:** Pin to a full commit SHA and comment the version; bump deliberately.  
- **Code example:**

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@76f17fb7db86387fc23009674fa183ee8c9e85f2  # v1.12.4
```

- **Fix timing:** **immediately** (before first Trusted Publisher tag)

### [MEDIUM] Action `git-repository` input allows non-HTTPS / arbitrary remotes
- **Priority:** P1  
- **File:** `action.yml`  
- **Line:** 78–81  
- **Explanation:** `install-from: git` interpolates `inputs.git-repository` into `pip install … git+${REPO}@${REF}` with no scheme allowlist. A malicious or mistaken workflow can pull arbitrary code.  
- **Impact:** Arbitrary code execution in the CI job as the runner user.  
- **Recommended fix:** Require `https://` prefix (and optionally allowlist `github.com/vksvicky/RepoLens`).  
- **Code example:**

```bash
REPO="${{ inputs.git-repository }}"
case "$REPO" in
  https://github.com/*|https://gitlab.com/*) ;;
  *) echo "git-repository must be https://…" >&2; exit 2 ;;
esac
python -m pip install "repolens[scanners] @ git+${REPO}@${REF}"
```

- **Fix timing:** before launch

### [LOW] Semgrep `--config auto` may fetch rules over the network
- **Priority:** P1  
- **File:** `src/repolens/scanners/semgrep.py`  
- **Line:** 26  
- **Explanation:** Upstream Semgrep behaviour; air-gapped or privacy-sensitive CI may unexpected egress.  
- **Impact:** Network dependency / rule supply chain outside RepoLens control.  
- **Recommended fix:** Document offline configs; optional Action input for `--config`.  
- **Fix timing:** if time permits  

### [LOW] Process gap — dual-review gate skipped on Phase 4 ship
- **Priority:** P1 (process)  
- **File:** n/a (process)  
- **Line:** n/a  
- **Explanation:** Phase 4 implementation was committed and pushed without a durable gate report in-repo/chat.  
- **Impact:** Missed Medium findings until retroactive review; weaker audit trail.  
- **Recommended fix:** Always emit chat report + optional `docs/reviews/gate_review_report_YYYY-MM-DD.md` before commit/push; never skip for “docs-only” or large features.  
- **Fix timing:** immediately (process)

## P2 — Bugs, reliability, performance

### [MEDIUM] Action plugin install failures are swallowed
- **Priority:** P2  
- **File:** `action.yml`  
- **Line:** 93–95  
- **Explanation:** `plugins install … || { echo …; }` continues even when all installs fail; with `run=auto` the job may “succeed” with only skipped scanners unless `require-scanners` is set.  
- **Impact:** False sense of security in CI (green job, no scanners).  
- **Recommended fix:** Surface a warning annotation; document `require-scanners: true` for strict pipelines; optional fail on total plugin failure.  
- **Fix timing:** before launch  

### [LOW] Local learning FTS rebuild deletes DB then rebuilds without backup
- **Priority:** P2  
- **File:** `src/repolens/learning/index.py`  
- **Line:** 35–36  
- **Explanation:** `build()` unlinks `index.sqlite` before recreate; crash mid-build leaves no index.  
- **Impact:** Transient empty learning context until rebuild.  
- **Recommended fix:** Build to temp path then atomic replace.  
- **Fix timing:** after launch  

## P3 — Architecture & quality (scoped)

### [MEDIUM] `[local-ml]` extra does not change retrieval yet
- **Priority:** P3  
- **File:** `src/repolens/learning/embeddings.py`  
- **Line:** 14–20  
- **Explanation:** Extra installs `sentence-transformers` but `enhance_query` is a pass-through; FAQ/README imply optional embeddings path.  
- **Impact:** User expectation mismatch; install weight without benefit.  
- **Recommended fix:** Either wire minimal embedding retrieval or document clearly as “reserved / no-op in alpha”.  
- **Fix timing:** before launch (docs honesty) or after launch (implementation)

### [LOW] Large CLI surface growth
- **Priority:** P3  
- **File:** `src/repolens/cli.py`  
- **Explanation:** plugins + learn + review flags increase maintenance; `ci_args` correctly extracted for Action.  
- **Fix timing:** if time permits (further splits)

## Architecture scores (milestone — Phases 3–4)

| Dimension | Score (1–10) |
|-----------|--------------|
| Architecture | 8 |
| Security | 7 |
| Maintainability | 8 |
| Performance | 7 |
| Scalability | 7 |
| Production readiness | 6 |

## Plan to fix

1. **Now (before first PyPI tag):** pin `gh-action-pypi-publish` to SHA; restrict Action git URL to HTTPS  
2. **Before launch / wide Action use:** plugin SHA-256 pins; clarify `[local-ml]` no-op or implement; Action plugin-fail signalling  
3. **Later:** atomic index rebuild; Semgrep offline config input; Dependabot + CodeQL on this repo  
4. **Verification:** `pytest -q` · `ruff check src tests` · dry-run Action workflow · TestPyPI publish once publisher is configured  

## Durability checklist

- [x] Tests covering ci_args, scanners (mocked), plugins (mocked), learning  
- [x] CI (pytest + ruff + docs sanity)  
- [ ] Dependabot / Renovate  
- [ ] CodeQL / Semgrep / gitleaks on **this** repo  
- [ ] Plugin checksum pins  
- [x] Logging: Rich console; no secrets in reports (prior hardenings)  
- [ ] Staging: TestPyPI before prod PyPI  
- [ ] Runbook: `docs/publishing.md` (Trusted Publisher)  

## Confidence log entry

| Date | Ref | Confidence | Counts | Note |
|------|-----|------------|--------|------|
| 2026-08-04 | 6c9cc10 | 78% | C:0 H:0 M:5 L:4 | Retroactive Phase 3–4 gate; process miss noted |

## Remediation status (same day)

| Finding | Status |
|---------|--------|
| Plugin SHA-256 pins | Fixed in follow-up commit |
| Publish Action floating tag | Fixed — pinned to `ed0c539…` (v1.13.0) |
| Action git-repository HTTPS | Fixed — allowlist https GitHub/GitLab/Bitbucket |
| Semgrep offline config | Fixed — `REPOLENS_SEMGREP_CONFIG` + docs |
| Dual-review process gap | Fixed — CONTRIBUTING + `docs/reviews/` + confidence log |

## Next action

1. Commit remediation  
2. Proceed with PyPI Trusted Publisher setup (manual UI + GitHub `pypi` environment)  
3. Tag `v0.1.0a1` only after Trusted Publisher pending publisher is registered  

