# RepoLens editor (VS Code / Cursor)

Thin client. It shells the `repolens` CLI. It does **not** parse Python, call a model, or start a review on save.

## Install (unpacked)

1. `pip install -e ".[dev]"` so `repolens` is on PATH.
2. **Developer: Install Extension from Location…** on this folder, or copy it into Cursor/VS Code `extensions/`.
3. Save and **RepoLens: Check** → `repolens check --format sarif`.
4. Status bar → `repolens check --diff`.
5. Palette also: Show dependencies, Would this import cycle, Why this cycle, Preview cut, Compare duplicate, Ignore, Explain, Copy full review command.

Architecture YAML/JSON: the extension ships `schemas/architecture.schema.json` (same file as the Python package). For `repolens.yaml`, point the Red Hat YAML extension at that schema, or copy `"yaml.schemas"` in user settings to `./schemas/architecture.schema.json` for `repolens.yaml` / `repolens.yml` / `.repolens/architecture.yaml`.

Zed: `editors/zed/README.md`. IntelliJ: `editors/intellij/README.md`.
