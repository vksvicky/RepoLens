# Official slim RepoLens image for air-gapped / locked-down CI.
# Does NOT replace pipx/local install as the primary zero-infra story.
#
# Build:  docker build -t ghcr.io/vksvicky/repolens:0.1.1 .
# Multi-arch (CI): docker buildx build --platform linux/amd64,linux/arm64 -t …
#
# Pinned scanner versions (match src/repolens/plugins.py):
#   gitleaks 8.24.0 · osv-scanner 1.9.2 · trivy 0.73.0 · semgrep (pip)
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
RUN set -eux; \
    arch="$TARGETARCH"; \
    case "$arch" in \
      amd64) gl_arch=x64; osv_arch=amd64; trivy_arch=Linux-64bit ;; \
      arm64) gl_arch=arm64; osv_arch=arm64; trivy_arch=Linux-ARM64 ;; \
      *) echo "unsupported TARGETARCH=$arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_V}/gitleaks_${GITLEAKS_V}_linux_${gl_arch}.tar.gz" \
      | tar -xz -C /opt/scanners gitleaks; \
    curl -fsSL -o /opt/scanners/osv-scanner \
      "https://github.com/google/osv-scanner/releases/download/v${OSV_V}/osv-scanner_linux_${osv_arch}"; \
    curl -fsSL \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_V}/trivy_${TRIVY_V}_${trivy_arch}.tar.gz" \
      | tar -xz -C /opt/scanners trivy; \
    chmod +x /opt/scanners/gitleaks /opt/scanners/osv-scanner /opt/scanners/trivy

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[scanners]"

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

ENTRYPOINT ["repolens"]
CMD ["--help"]
