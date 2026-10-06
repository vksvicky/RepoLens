# RepoLens in IntelliJ

First version: External Tool + Problems via SARIF. The plugin does not embed grimp or start a model on save.

## External Tools

**Settings → Tools → External Tools → +**

| Field | Value |
| --- | --- |
| Name | RepoLens Check |
| Program | `repolens` |
| Arguments | `check --path $ProjectFileDir$ --format sarif` |
| Working directory | `$ProjectFileDir$` |

Add a second tool **RepoLens ratchet**: `check --path $ProjectFileDir$ --diff`.

Map stdout SARIF with the IDE’s SARIF viewer (GitHub / Qodana SARIF plugin), or save to `$ProjectFileDir$/reports/repolens.sarif` and open it.

Commit check: run **RepoLens Check** in Before Commit if you want Problems on the change list. Do **not** add `repolens review --deep` to save or commit.

Richer dependency / cycle panels stay the VS Code client (`editors/vscode/`) until a dedicated IntelliJ plugin exists.
