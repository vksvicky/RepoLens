# RepoLens vs Sonargraph-Architect

**Status:** C1/C2/C3/C5/C6 CLI landed (2026-10-06). C4 extra baseline fields, C7 churn, and editor plugins remain later. No Metis desktop.  
**Source:** [Sonargraph-Architect](https://www.hello2morrow.com/products/sonargraph/architect)  
**Related:** [which-command.md](../which-command.md) (what you can run today) · [zugel-comparison-and-roadmap.md](./zugel-comparison-and-roadmap.md) (G0–G4, CLI-first guardrail) · [architecture-dsl-format-comparison.md](./architecture-dsl-format-comparison.md)

Sonargraph-Architect is a static-analysis workbench: architecture rules, dependency pictures, a cycle break-up computer, metrics, baselines, duplicates, and scripting, checked in an IDE and in the build. It supports C#, C/C++, Java/Kotlin, TypeScript, Go, and Python 3.

RepoLens stays a review CLI. The editor story is a thin plugin for Visual Studio Code, Cursor, Zed, and IntelliJ that runs that CLI. This note does not propose an Eclipse-style workbench, a graph canvas product, or a second analysis engine inside the editor.

G1–G4 from the Zügel roadmap are already in the tree: a Python import graph, a cyclicity baseline, `repolens check`, architecture YAML verification, and feedback-arc-set candidates. The gap is that those results are split across commands and Markdown, so an editor cannot use them the way Sonargraph uses its model.

---

## What each product is for

| | Sonargraph-Architect | RepoLens |
| --- | --- | --- |
| Job | Keep the structure you designed, and show how to untangle what you have | Review a repo for security, reliability, and architecture, and fail CI when the gate says so |
| When it runs | IDE and every build | CLI, CI, pre-commit. A full model review is explicit |
| How structure is decided | Deterministic model and an architecture DSL | Deterministic Python graph plus playbooks. The model explains; it does not discover cycles |
| Languages in the core model | C#, C/C++, Java/Kotlin, TypeScript, Go, Python 3 | Python import graph. Other languages through scanners, SARIF import, and a precomputed edge file |
| What the other product does not lead with | Security scanners and a local or BYOK model review | A polyglot structure workbench |

---

## Feature comparison

| Sonargraph capability | RepoLens today | Gap |
| --- | --- | --- |
| Architecture rules as code, checked in the IDE and in CI | `repolens.yaml` / `architecture.json`, verified by `repolens check architecture`. Violations print `file:line` and exit 1. `--json` dumps the remediation context | The check is a separate subcommand. A save in the editor does not run it. JSON Schema autocomplete for the YAML is a docs recommendation, not shipped editor support |
| Dependency views from modules down to methods, each arc tied to a line | Import edges carry file and line. `graph/query.py` can list dependencies, dependents, and whether a proposed edge would enlarge a cycle. Reports can include Mermaid | Those queries are not CLI commands. There is no exploration view, graph view, or cycle view. Method-level call arcs are not in the graph |
| Break-up computer: smallest set of dependencies to cut, then simulate delete / move / rename | `candidate_feedback_arc_sets` prints candidate cuts and weights. The report says they are candidates, and architecture direction wins over the lightest cut | Cuts are text in the architecture check. There is no “omit these edges and recompute cyclicity” query, and no virtual move or rename |
| Hundreds of metrics, including LCOM4 and Maintainability Level; quality gates against a baseline | Cyclicity (sum of *n*² over cycle groups) with `repolens baseline set` / `show` and `repolens check --diff`. Python cyclomatic and cognitive complexity. Mega-file size. The review gate fails on severity | The baseline is cyclicity only. Complexity and size are findings inside `repolens review`, not ratchet metrics. There is no Maintainability Level and no large metric catalog |
| Duplicate code, inspected side by side | Near-clone windows (hash of normalised lines) become findings for several languages | Pairs are buried in the review report. There is no command that returns the two spans for an editor diff |
| Groovy scripting over the model | Playbooks, `.repolens.toml`, architecture YAML, and `--import-sarif` | Custom checks are data and external SARIF, not a script API over the graph. That is enough for this product |
| Git history: change frequency and churn, drawn as tree maps | `--git-diff` limits the Slow Brain pack and tags findings as touched or pre-existing | No churn or hotspot command. Tree maps are out of scope; a table of hot files is enough |
| Issues view: filter, ignore, turn into tasks | `.repolens-ignore`, inline suppressions, and `repolens feedback down <stableId>`, which appends a fingerprint ignore. `repolens explain` narrates one finding | The plugin still needs a command keyed by rule and path, not only by a report fingerprint. There is no “open a task” hook |
| Modernizing a legacy tree | The model receives cycle context and candidate cuts and writes a fix plan in the report | The plan is a document after a long review. It is not a short, repeatable query on one cycle |

---

## Out of scope

These Sonargraph features stay out, including in the plugin:

- An Eclipse workbench or any new IDE shell.
- A visual architecture designer. The architecture file stays YAML or JSON, with schema help in the editor the user already has.
- A Groovy or Python scripting engine with full access to an in-memory model.
- A catalog of hundreds of metrics, LCOM4, or a single Maintainability Level score.
- 2D or 3D tree maps.
- Method-level dependency arcs for every language.
- A polyglot resolver inside RepoLens. Python stays on grimp. Other languages arrive as a precomputed edge file (the adapter in `graph/adapters.py`) or as SARIF.
- Running `repolens review` (the model) on every save. The plugin runs the fast check. A full review stays a task the user starts.

---

## What `repolens review` includes today

This is the dogfood command. It is a full audit. It is not the fast check the plugin runs on save.

```bash
repolens review \
  --path . \
  --out reports/selfdog-deep \
  --full \
  --full-audit \
  --deep \
  --scanners gitleaks,semgrep,osv,trivy,checkov \
  --model qwen2.5-coder:32b \
  --timeout 7200 \
  --verbose
```

| Proposed command | In this review? |
| --- | --- |
| C1 `repolens check --format sarif` | No SARIF file. `--sarif` is off unless you pass it. Scanners run (gitleaks, semgrep, osv, trivy, checkov). Fast Brain runs. Slow Brain runs P1, P2, P3, and coverage closure because of `--full --full-audit --deep`. The report is Markdown under `reports/selfdog-deep` |
| C2 `repolens graph` | The Python import graph runs inside the review. The log and the report include cycle groups, findings, and cyclicity. The query commands (`deps`, `dependents`, `edges`, `would-cycle`) are not separate CLI calls |
| C3 `repolens graph breakup --omit-edge` | Yes: candidate cuts in JSON; `--omit-edge` recomputes cyclicity without editing files | Editor sidecar still later |
| C4 extra baseline fields | No. This command does not pass `--ratchet`, and the repo has no `.repolens.toml` turning the ratchet on. `repolens baseline` is a different command. The baseline file is still cyclicity only |
| C5 `repolens duplicates` | Near-clone and sibling-duplication findings are inside the report. There is no command that prints the two line spans |
| C6 `repolens ignore add` | The review reads `.repolens-ignore` if the file is already there and drops matching rows. It does not add an ignore. Adding one is `repolens feedback down <stableId>` after a report exists |
| C7 `repolens hotspots` (git churn) | No git churn table. The review does print complexity hotspots: functions over the cyclomatic or cognitive threshold, and the top of that list is packed into the Slow Brain prompt |

`--timeout 7200` is time to the first token. After the first token, the pass ends on silence, not on that wall clock.

## 1. CLI first

The plugin is a client. Every view below is a command that already returns machine-readable output. Ship the commands in this order. Each one is useful in CI before any editor exists.

### C1 — One diagnostic stream

Today `repolens check --diff` is the cyclicity ratchet. `repolens check architecture` is a second command. Complexity, mega-files, and near-clones appear only inside `repolens review`.

Add one fast command that runs no model:

```bash
repolens check --path . --format sarif
repolens check --path . --format jsonl
```

It includes, when each is available:

- cyclicity ratchet breaches, anchored to the new import line when `--diff` can see one (already implemented),
- architecture boundary violations (already implemented),
- Fast Brain rows that already exist: complexity, mega-file, near-clone.

Each diagnostic has `path`, `line`, `ruleId`, `severity`, `message`, and optional related locations (the other file in a clone pair, or the other side of an import). Exit codes stay the ones CI already uses: 0 clean, 1 findings, 2 usage, 3 graph failed or skipped.

`repolens check --diff` without `--format` keeps today’s human output so current CI scripts do not change.

This is the command VS Code, Zed, and IntelliJ all call. SARIF is the interchange format; JSONL is the line-oriented fallback for a problem matcher.

### C2 — Graph queries on the CLI

`graph/query.py` already answers these. Expose them:

```bash
repolens graph deps <module> --path .
repolens graph dependents <module> --path .
repolens graph cycles --path . --format json
repolens graph would-cycle --from <module> --to <module> --path .
repolens graph edges --path . --format json
```

`edges` is the list the picture is drawn from: importer, imported, file, line, kind (`runtime` or `type_only`). `cycles` is the cycle groups plus cyclicity. `would-cycle` is the pre-flight a human or an agent runs before adding an import.

JSON on stdout. No model call.

### C3 — Break-up as a query

`repolens check architecture --json` already includes feedback-arc-set candidates. Add a focused query that does not require an architecture file, because a cycle exists whether or not boundaries are declared:

```bash
repolens graph breakup --path . --format json
repolens graph breakup --path . --omit-edge importer:imported --omit-edge importer:imported
```

The first print is the candidate cuts: edges, weight, and the cycle group each cut addresses. The second recomputes cyclicity with those edges removed and prints the new score and the groups that remain. That is the break-up computer as data. Nothing in the tree is edited.

Virtual move and rename can wait. When they exist, they are the same idea: a what-if edge list, printed, not applied.

### C4 — A small baseline, not a metric catalog

`.repolens/baseline.json` today stores cyclicity and cycle fingerprints. Extend that file with four more numbers, each optional and each able to fail the build on its own:

| Field | Already measured by |
| --- | --- |
| `cyclicity` | import graph |
| `boundaryViolations` | architecture verify |
| `complexityHotspots` | functions over the cyclomatic or cognitive threshold |
| `nearClonePairs` | near-clone heuristic |

```bash
repolens baseline set --path .
repolens check --path . --diff
```

`check --diff` fails when a ratcheted field is higher than the baseline. The report line names the field and the delta. Teams check the baseline file into git, as they can today for cyclicity.

Maintainability Level, LCOM4, and the rest of Sonargraph’s catalog are not added.

### C5 — Duplicates as spans

```bash
repolens duplicates --path . --format json
repolens duplicates --path . --file src/app.py --format json
```

Each pair is two inclusive line spans. The editor opens them in its own diff view. The detector stays the current near-clone heuristic.

### C6 — Ignore from a command

```bash
repolens ignore add --id arch.boundary_violation --path src/api/orders.py --reason "temporary adapter import"
repolens ignore list --path .
```

This writes `.repolens-ignore` in the format the review already honours. The plugin does not hand-edit that file. Turning a finding into a task is a URL in the diagnostic (`code` / `helpUri` in SARIF), pointing at the repo’s issue tracker. RepoLens does not grow a task database.

`repolens explain <id>` stays the long-form narrative. The plugin can offer it as a command. It is not part of `repolens check`.

### C7 — Churn as a table, later

After C1–C6:

```bash
repolens hotspots --path . --since 6.months
```

Columns: path, commits, lines added, lines deleted, from `git log`. The top rows can be packed into a later review. No tree map.

### CLI build order

1. C1 diagnostic SARIF and JSONL, wrapping the checks that already exist.
2. C2 graph queries.
3. C3 breakup and `--omit-edge`.
4. C5 duplicate spans.
5. C6 `ignore add`.
6. C4 extra baseline fields.
7. C7 hotspots.

C1 alone is enough for CI annotations and a problems list. C2 and C3 are what make the plugin feel like Sonargraph’s exploration and cycle views.

---

## 2. UI and UX

One small program speaks to the editor. It runs `repolens` and maps stdout onto the editor’s diagnostics. It does not parse Python, does not call the model on save, and does not embed grimp.

Preferred shape: a language-server sidecar that shells the CLI, so VS Code, Cursor, and Zed share it. IntelliJ consumes the same SARIF through a thin plugin or an LSP client. Three menus, one protocol.

The check runs on save and on demand. It is debounced. A full `repolens review` is a task in the command palette, with the same flags as the dogfood command above, and its output stays a report file. Save never starts that review.

### Calls

The sidecar runs one command per action. Arguments are the workspace root and, where a row needs it, the file the user has open.

| When | Command |
| --- | --- |
| Save, and “RepoLens: Check” | `repolens check --path <root> --format sarif` |
| Status bar click | `repolens check --path <root> --diff` |
| “Show dependencies” | `repolens graph deps <module> --path <root>` and `repolens graph dependents <module> --path <root>` |
| “Would this import cycle?” | `repolens graph would-cycle --from <module> --to <module> --path <root>` |
| Optional neighborhood picture | `repolens graph edges --path <root> --format json`, filtered to the current module and one hop, rendered as Mermaid by the editor |
| “Show why this cycle” | `repolens graph breakup --path <root> --format json` |
| “Preview this cut” | the same command with one `--omit-edge importer:imported` per selected edge |
| “Compare duplicate” | `repolens duplicates --path <root> --file <file> --format json`, then the editor’s diff on the two spans |
| “Ignore” | `repolens ignore add --id <rule> --path <file> --reason <text>` |
| “Explain” | `repolens explain <stableId> --path <root>` |
| “Run full review” | the `repolens review` command in the section above. The user starts it. It is not on the save path |

Build C1 before the save row exists. Build C2 before the dependency rows. Build C3 before the cycle rows. Build C5 and C6 before duplicate diff and Ignore. `explain` and `review` already exist.

### What the user sees

**Problems list.** C1 diagnostics become squiggles and a problems row. The jump target is the import or the complex function. Related locations jump to the other side of an edge or the other clone span.

Code actions, each one CLI:

- Ignore — `repolens ignore add` (C6).
- Explain — `repolens explain` for a finding id, opened as a Markdown preview.
- Show why this cycle — `repolens graph breakup` (C3) in a side panel.

**Dependencies.** Command palette: “Show dependencies of this file.” A list, not a canvas: modules this file imports, modules that import it, each row opening `file:line` from C2. A second command, “Would this import cycle?”, asks for a target module and runs `would-cycle`.

An optional Mermaid preview renders the neighborhood from `repolens graph edges` for the current module plus one hop. The editor’s existing Markdown preview is enough. A custom graph widget is a later choice, and only if the list proves too hard to read.

**Cycle cuts.** When the diagnostic is a cycle group, the side panel lists candidate cuts the way Sonargraph’s break-up computer does: which edges, the weight, and the cyclicity that remains if they are omitted. “Preview” re-runs C3 with `--omit-edge`. “Open edge” jumps to the import. Nothing is renamed or moved in the IDE.

**Duplicates.** “Compare duplicate” opens the editor’s diff with the two spans from C5. VS Code `diff`, Zed split, IntelliJ diff. RepoLens does not draw a duplicate viewer.

**Status.** The status bar shows cyclicity against the baseline from the last `repolens check --diff`: the number, and whether the ratchet is clean. Clicking it runs the check again.

**Architecture file.** Editing `repolens.yaml` gets schema validation from the editor. The plugin does not add a diagram editor for boundaries.

### Per editor

| Editor | Shell | First version |
| --- | --- | --- |
| VS Code and Cursor | Extension plus the sidecar | Diagnostics on save, status bar, dependencies list, cycle panel, duplicate diff |
| Zed | Extension that runs the same CLI, or the same sidecar if the extension host allows it | Diagnostics and a buffer or panel for the cycle list. The richer panel can follow |
| IntelliJ | Plugin that runs the CLI, maps SARIF to the problems view | Diagnostics on save and on the commit check. The dependencies list uses the tool window |

VS Code is the first shell because Cursor already uses it. Zed and IntelliJ wait until C1–C3 are stable, so the plugin work is not repeated when the JSON changes.

### What the plugin refuses to do

- Analyse in-process.
- Start a model call because a file was saved.
- Store a private copy of the graph that can drift from `repolens check`.
- Offer refactorings that edit the user’s code. Cuts stay a preview until the user edits the import themselves.

### Plugin build order

1. Sidecar plus VS Code diagnostics from C1. A problem matcher on JSONL is an acceptable first week if the sidecar slips.
2. Status bar from `check --diff`.
3. Dependencies list from C2.
4. Cycle panel from C3.
5. Duplicate diff from C5 and Ignore from C6.
6. Zed, then IntelliJ, against the same commands.

---

## How this sits on the current product

The Zügel note already fixed the order: graph, then ratchet, then CLI check, then architecture rules, with the model used for remediation. This note starts after that. It turns those results into one diagnostic stream and a client that Visual Studio Code, Zed, and IntelliJ can host.

RepoLens still reviews. Sonargraph-Architect still owns a multi-language structure workbench. The overlap worth building is the part a developer feels on save: a boundary or a new cycle is a diagnostic, the other end of the import is one click away, and the cheapest cuts are listed before anyone spends a Slow Brain pass on them.
