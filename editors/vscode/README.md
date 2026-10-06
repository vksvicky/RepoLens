# RepoLens editor (VS Code / Cursor)

Thin client. It shells the `repolens` CLI. It does **not** parse Python, call a model, or start `repolens review` on save.

## Install (unpacked)

1. `pip install -e ".[dev]"` so `repolens` is on PATH.
2. Cursor / VS Code: **Extensions: Install from VSIX…** is not required. Use **Developer: Install Extension from Location…** if available, or copy this folder into `~/.vscode/extensions/` / Cursor’s equivalent and reload.
3. Command palette: **RepoLens: Check** (`repolens check --path <workspace> --format sarif`).
4. Saving a file re-runs that same check (debounced 500ms).
5. Status bar **RepoLens** runs `repolens check --diff`.

Zed and IntelliJ wait until this command surface is stable.
