# RepoLens in Zed

First version: run the same CLI Zed already understands as a task. There is no in-process analyser and **no model call on save**.

## Tasks

Copy into the project `.zed/tasks.json` (or run from the terminal):

```json
[
  {
    "label": "RepoLens: Check",
    "command": "repolens",
    "args": ["check", "--path", "$ZED_WORKTREE_ROOT", "--format", "sarif"]
  },
  {
    "label": "RepoLens: Cyclicity ratchet",
    "command": "repolens",
    "args": ["check", "--path", "$ZED_WORKTREE_ROOT", "--diff"]
  },
  {
    "label": "RepoLens: Breakup",
    "command": "repolens",
    "args": ["graph", "breakup", "--path", "$ZED_WORKTREE_ROOT", "--format", "json"]
  }
]
```

Open the SARIF output with Zed’s diagnostics if you have a SARIF extension; otherwise keep the JSON in a buffer.

Full `repolens review --deep` stays a command **you** start in the terminal.
