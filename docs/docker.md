# Official RepoLens container image

**Primary zero-infra story remains** `pipx install "repolens-audit[scanners]"` (or editable clone).  
This image is for **locked-down CI / air-gap runners** that cannot download scanner binaries at job time.

Image: `ghcr.io/vksvicky/repolens` (multi-arch `linux/amd64`, `linux/arm64` when published).

## Pinned scanners (build-time)

| Tool | Version (see `Dockerfile` / `plugins.py`) |
|------|------------------------------------------|
| gitleaks | 8.24.0 |
| osv-scanner | 1.9.2 |
| trivy | 0.73.0 |
| semgrep | via `pip install ".[scanners]"` + semgrep |

No API keys or cloud credentials are baked into the image.

## Build locally

```bash
docker build -t ghcr.io/vksvicky/repolens:0.1.1 .
# optional SBOM for the image (Syft / BuildKit):
# docker buildx build --sbom=true --provenance=true -t ghcr.io/vksvicky/repolens:0.1.1 .
```

## Entrypoint recipes

### GitHub Actions

```yaml
jobs:
  repolens:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/vksvicky/repolens:0.1.1
    steps:
      - uses: actions/checkout@v4
      - run: repolens review --path . --out reports --preset pr --fail-on HIGH --ci
```

### GitLab CI

```yaml
repolens:
  image: ghcr.io/vksvicky/repolens:0.1.1
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
      - docker pull ghcr.io/vksvicky/repolens:0.1.1
      - docker run --rm -v "$CODEBUILD_SRC_DIR:/work" -w /work
          ghcr.io/vksvicky/repolens:0.1.1
          review --path . --out reports --preset pr --fail-on HIGH --ci
```

## Honesty

- Image includes scanners for Fast Brain / CI gates — not a hosted SaaS.
- Deep Slow Brain still needs BYOK env vars or a sidecar Ollama — never baked keys.
- Prefer local `pipx` for interactive laptops; use the image when policy forbids runtime downloads.
