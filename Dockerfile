# Official slim RepoLens image for air-gapped / locked-down CI.
# Does NOT replace pipx/local install as the primary zero-infra story.
#
# Build:  docker build -t ghcr.io/vksvicky/repolens:0.1.3 .
# Multi-arch (CI): docker buildx build --platform linux/amd64,linux/arm64 -t …
#
# Pinned scanner versions (match src/repolens/plugins.py):
#   gitleaks 8.24.0 · osv-scanner 1.9.2 · trivy 0.73.0
#   semgrep 1.180.0 via the CPython 3.12 hash lock (deps included)
#
# No secrets are baked into this image.

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm AS build

ARG TARGETARCH=amd64
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl tar gzip \
    && rm -rf /var/lib/apt/lists/*

# Pinned scanner binaries (linux) — keep in sync with src/repolens/plugins.py
ARG GITLEAKS_V=8.24.0
ARG OSV_V=1.9.2
ARG TRIVY_V=0.73.0
WORKDIR /opt/scanners
# Hashes match the linux assets in the plugin catalog. The build does not load that module.
RUN set -eux; \
    arch="$TARGETARCH"; \
    case "$arch" in \
      amd64) \
        gl_file=gitleaks_${GITLEAKS_V}_linux_x64.tar.gz; \
        gl_sha=cb49b7de5ee986510fe8666ca0273a6cc15eb82571f2f14832c9e8920751f3a4; \
        osv_file=osv-scanner_linux_amd64; \
        osv_sha=d6af4b67fa5de658598bd2d445efb99e90d1734b3146962418719c4350ecb74b; \
        trivy_file=trivy_${TRIVY_V}_Linux-64bit.tar.gz; \
        trivy_sha=2edd39da482bb4e9831962487b68f68e3928ec3137794757f54d00383d79547b; \
        ;; \
      arm64) \
        gl_file=gitleaks_${GITLEAKS_V}_linux_arm64.tar.gz; \
        gl_sha=3755cc9b81f2466ad308f722a064ca04df27f59d551396183efe07978fef8fcb; \
        osv_file=osv-scanner_linux_arm64; \
        osv_sha=9c6160afb26c79449a1f1b667323b989a57dda8fc19f22936c9ff920fd97ddfa; \
        trivy_file=trivy_${TRIVY_V}_Linux-ARM64.tar.gz; \
        trivy_sha=13833d97e8a1a5367471c372a173180157f593bece570e20d5d925fef552f5dd; \
        ;; \
      *) echo "unsupported TARGETARCH=$arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/gitleaks.tgz \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_V}/${gl_file}"; \
    echo "${gl_sha}  /tmp/gitleaks.tgz" | sha256sum -c -; \
    tar -xz -C /opt/scanners -f /tmp/gitleaks.tgz gitleaks; \
    curl -fsSL -o /opt/scanners/osv-scanner \
      "https://github.com/google/osv-scanner/releases/download/v${OSV_V}/${osv_file}"; \
    echo "${osv_sha}  /opt/scanners/osv-scanner" | sha256sum -c -; \
    curl -fsSL -o /tmp/trivy.tgz \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_V}/${trivy_file}"; \
    echo "${trivy_sha}  /tmp/trivy.tgz" | sha256sum -c -; \
    tar -xz -C /opt/scanners -f /tmp/trivy.tgz trivy; \
    rm -f /tmp/gitleaks.tgz /tmp/trivy.tgz; \
    chmod +x /opt/scanners/gitleaks /opt/scanners/osv-scanner /opt/scanners/trivy

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# Semgrep comes from the hashed lock for this architecture, not the unhashed extra.
RUN set -eux; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir .; \
    case "$TARGETARCH" in \
      amd64) lock=src/repolens/plugin_locks/semgrep-linux-amd64-cp312.txt ;; \
      arm64) lock=src/repolens/plugin_locks/semgrep-linux-arm64-cp312.txt ;; \
      *) echo "unsupported TARGETARCH=$TARGETARCH" >&2; exit 1 ;; \
    esac; \
    pip install --no-cache-dir --require-hashes -r "$lock"

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/vksvicky/RepoLens"
LABEL org.opencontainers.image.title="repolens"
LABEL org.opencontainers.image.description="RepoLens CLI + pinned scanners for CI / air-gap"
LABEL org.opencontainers.image.licenses="MIT"

ARG PYTHON_VERSION=3.12
ENV PATH="/opt/scanners:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=build /opt/scanners /opt/scanners
COPY --from=build /usr/local/lib/python${PYTHON_VERSION}/site-packages \
                  /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=build /usr/local/bin/repolens /usr/local/bin/repolens
COPY --from=build /usr/local/bin/semgrep /usr/local/bin/semgrep

# Non-root for CI mounts
RUN useradd --create-home --uid 10001 repolens
USER repolens
WORKDIR /work

# DS-0026 / CKV_DOCKER_2: the image is a CLI, so health is "version runs".
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD repolens version || exit 1

ENTRYPOINT ["repolens"]
CMD ["--help"]
