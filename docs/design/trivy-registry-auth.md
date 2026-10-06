# Trivy registry authentication (RepoLens)

Date: 2026-10-06  
Issue: [#94](https://github.com/vksvicky/RepoLens/issues/94) (formerly out of Phase 6.1)  
Status: Operator contract for the #92–#96 slice. Implementation follows [the spec](../superpowers/specs/2026-10-06-parked-92-96-design.md).

Related: [scanners.md](../scanners.md) · [phase-6.x-scanner-depth-ci-gates-and-credibility.md](./phase-6.x-scanner-depth-ci-gates-and-credibility.md)

## What this is

`trivy fs` and CycloneDX SBOM already run from RepoLens. Private **image registries** (and some lockfile lookups) need the same credentials Trivy itself reads from the environment. RepoLens forwards an **allowlist** of those variables into Trivy subprocesses and **never** writes them into reports.

This is not Trivy Enterprise, not Aqua cloud, and not a live-registry CI job.

## Secrets policy

- Set credentials in the **environment** (CI secrets, local shell).  
- Do **not** put passwords or tokens in `.repolens.toml`, CLI flags, architecture YAML, or committed fixtures.  
- `ScannerRun.detail`, durability gaps, and Markdown/JSON reports must not contain allowlisted secret **values**. If Trivy echoes them, RepoLens redacts to `***`.
- Redact only secret values with **length ≥ 3** after strip. Empty or whitespace env vars are not forwarded and must not be used as `str.replace` needles.

## Environment allowlist

| Variable | Typical use |
|----------|-------------|
| `TRIVY_USERNAME` + `TRIVY_PASSWORD` | Registry basic auth |
| `TRIVY_REGISTRY_TOKEN` | Bearer / identity token |
| `TRIVY_AUTH_URL` | Registry auth endpoint when Trivy needs it |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_PROFILE`, `AWS_REGION` | Amazon ECR (existing AWS env) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCR / Artifact Registry ADC file path (path is not a password; still do not log file contents) |
| `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_FEDERATED_TOKEN_FILE` | ACR |

Forward a key only when it is already set. Incomplete basic auth (`TRIVY_USERNAME` without password **and** without token) is a **failed** scanner run with a fixed detail string, not a hang on a 401 loop.

## Config

```toml
[scanners.trivy]
pass_registry_env = true   # default; false = do not forward the allowlist
images = []                # optional; each ref runs `trivy image --format json --quiet`
```

`trivy fs` always remains the filesystem/misconfig/secret scan. Image refs are extra: run **one image at a time**. A failed image does not drop `fs` findings or skip later images; failures append to redacted `detail`.

## Test matrix (no network)

CI must mock `subprocess.run`. Cases **A–J** are required in the spec (including empty-password redaction and partial image failure).

## Operator recipe

```bash
export TRIVY_USERNAME="ci-bot"
export TRIVY_PASSWORD="…"   # from the CI secret store
repolens review --path . --scanners trivy --scanners-only
```

ECR/GCR/ACR: use the cloud provider’s usual env or workload identity; RepoLens only forwards the allowlist.

## Out of scope

- Logging into Docker Hub from GitHub Actions in this repository’s CI  
- Storing registry passwords in RepoLens config  
- Paid Trivy/Checkov cloud features  
- Parsing `~/.docker/config.json` into the report
