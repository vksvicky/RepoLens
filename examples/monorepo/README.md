# Monorepo example config

Point RepoLens at a package subdirectory, or run from the repo root with ignores.

```bash
# Review one package
repolens review --path ./packages/api --dry-run

# From root with project config (see .repolens.toml)
repolens review --path . --scanners-only
```

Copy [`repolens.example.toml`](./repolens.example.toml) to `.repolens.toml` at your monorepo root and adjust scanners / report dir.

For CI, set the Action `path` input to the package you want reviewed (e.g. `packages/api`).
