# Official RepoLens container image

This is a ready-made copy of RepoLens for a computer that is not allowed to download extra tools at review time. It already includes the checkers, on known versions, including the Semgrep pattern check for Python 3.12. Nothing in the image is a password or a cloud key.

Most people should still install RepoLens with `pipx install "repolens-audit[scanners]"` on their own computer. Use this image when company policy says the review has to run inside a locked-down container. Plain-language overview: [for-everyone.md](./for-everyone.md).

Image: `ghcr.io/vksvicky/repolens` (multi-arch `linux/amd64`, `linux/arm64` when published).

## Pinned scanners (build-time)

| Tool | Version (see `Dockerfile` / `plugins.py`) |
|------|------------------------------------------|
| gitleaks | 8.24.0 |
| osv-scanner | 1.9.2 |
| trivy | 0.73.0 |
| semgrep | 1.181.0, Python 3.12, fixed list of every piece it needs |

No API keys or cloud credentials are baked into the image. The runtime stage defines a `HEALTHCHECK` that runs `repolens version`.

## Build locally

```bash
docker build -t ghcr.io/vksvicky/repolens:0.1.5 .
# optional SBOM for the image (Syft / BuildKit):
# docker buildx build --sbom=true --provenance=true -t ghcr.io/vksvicky/repolens:0.1.5 .

CI publishes the same tags on `v*` pushes via [`.github/workflows/publish-ghcr.yml`](../.github/workflows/publish-ghcr.yml) (`0.1.5`, `0.1`, `latest` for non-prerelease tags).
```

## Entrypoint recipes

### GitHub Actions

```yaml
jobs:
  repolens:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/vksvicky/repolens:0.1.5
    steps:
      - uses: actions/checkout@v7
      - run: repolens review --path . --out reports --preset pr --fail-on HIGH --ci
```

### GitLab CI

```yaml
repolens:
  image: ghcr.io/vksvicky/repolens:0.1.5
  script:
    - repolens review --path . --out reports --preset pr --fail-on HIGH --ci
  artifacts:
    paths: [reports/]
```

### AWS CodeBuild

```yaml
phases:
  build:
    commands:
      - docker pull ghcr.io/vksvicky/repolens:0.1.5
      - docker run --rm -v "$CODEBUILD_SRC_DIR:/work" -w /work
          ghcr.io/vksvicky/repolens:0.1.5
          review --path . --out reports --preset pr --fail-on HIGH --ci
```

## Honesty

- Image includes scanners for Fast Brain / CI gates — not a hosted SaaS.
- Deep Slow Brain still needs BYOK env vars or a sidecar Ollama — never baked keys.
- Prefer local `pipx` for interactive laptops; use the image when policy forbids runtime downloads.
