"use strict";

function createCycleTree(vscode, deps) {
  const { runCli, workspaceRoot } = deps;

  function moduleToCandidates(mod) {
    const parts = String(mod || "").replace(/\./g, "/");
    return [`${parts}.py`, `${parts}/__init__.py`, `src/${parts}.py`, `src/${parts}/__init__.py`];
  }

  class CycleTreeProvider {
    constructor() {
      this._onDidChange = new vscode.EventEmitter();
      this.onDidChangeTreeData = this._onDidChange.event;
      this._cycles = [];
      this._cyclicity = 0;
    }

    refresh() {
      this._onDidChange.fire();
    }

    async load() {
      const folder = workspaceRoot();
      if (!folder) {
        this._cycles = [];
        this._cyclicity = 0;
        this.refresh();
        return;
      }
      const root = folder.uri.fsPath;
      // CLI only — no Slow Brain / model on this path.
      const { stdout, code } = await runCli(root, [
        "graph",
        "cycles",
        "--path",
        root,
        "--format",
        "json",
      ]);
      if (code !== 0) {
        this._cycles = [];
        this._cyclicity = 0;
        this.refresh();
        return;
      }
      try {
        const payload = JSON.parse(stdout || "{}");
        this._cyclicity = payload.cyclicity || 0;
        this._cycles = payload.cycles || [];
      } catch (_err) {
        this._cycles = [];
        this._cyclicity = 0;
      }
      this.refresh();
    }

    getTreeItem(element) {
      return element;
    }

    getChildren(element) {
      if (!element) {
        if (!this._cycles.length) {
          const empty = new vscode.TreeItem(
            this._cyclicity === 0 ? "No import cycles" : "Cycles unavailable",
            vscode.TreeItemCollapsibleState.None
          );
          empty.tooltip = `cyclicity=${this._cyclicity}`;
          return [empty];
        }
        return this._cycles.map((cycle, idx) => {
          const label = `Cycle ${idx + 1} (${(cycle.modules || []).length} modules)`;
          const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.Collapsed);
          item.contextValue = "cycle";
          item.tooltip = (cycle.modules || []).join(" → ");
          item.cycle = cycle;
          return item;
        });
      }
      const cycle = element.cycle;
      if (!cycle || !cycle.edges) {
        return (cycle.modules || []).map((mod) => {
          const item = new vscode.TreeItem(mod, vscode.TreeItemCollapsibleState.None);
          item.tooltip = mod;
          return item;
        });
      }
      return cycle.edges.map((edge) => {
        const label = `${edge.importer} → ${edge.imported}`;
        const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
        item.command = {
          command: "repolens.openCycleEdge",
          title: "Open",
          arguments: [edge],
        };
        item.tooltip = edge.line ? `line ${edge.line}` : "import edge";
        return item;
      });
    }
  }

  async function openCycleEdge(edge) {
    const folder = workspaceRoot();
    if (!folder || !edge || !edge.importer) {
      return;
    }
    const candidates = moduleToCandidates(edge.importer);
    let uri = null;
    for (const rel of candidates) {
      const trial = vscode.Uri.joinPath(folder.uri, rel);
      try {
        await vscode.workspace.fs.stat(trial);
        uri = trial;
        break;
      } catch (_err) {
        // try next
      }
    }
    if (!uri) {
      vscode.window.showWarningMessage(`RepoLens: could not map ${edge.importer} to a file`);
      return;
    }
    const doc = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(doc);
    const line = Math.max(0, (edge.line || 1) - 1);
    const pos = new vscode.Position(line, 0);
    editor.selection = new vscode.Selection(pos, pos);
    editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
  }

  return { CycleTreeProvider, openCycleEdge };
}

module.exports = { createCycleTree };
