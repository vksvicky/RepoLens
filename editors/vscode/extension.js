"use strict";

const { spawn } = require("child_process");
const vscode = require("vscode");

const COLLECTION = "repolens";

function runCli(root, args) {
  return new Promise((resolve, reject) => {
    const child = spawn("repolens", args, {
      cwd: root,
      env: process.env,
      shell: false,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

function workspaceRoot() {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  return folder || null;
}

function moduleFromRel(rel) {
  let p = String(rel || "").replace(/\\/g, "/");
  if (p.startsWith("src/")) {
    p = p.slice(4);
  }
  if (!p.endsWith(".py")) {
    return null;
  }
  p = p.slice(0, -3);
  if (p.endsWith("/__init__")) {
    p = p.slice(0, -"/__init__".length);
  }
  return p.replace(/\//g, ".");
}

function activeModule() {
  const ed = vscode.window.activeTextEditor;
  if (!ed) {
    return null;
  }
  const rel = vscode.workspace.asRelativePath(ed.document.uri);
  return moduleFromRel(rel);
}

function activeRel() {
  const ed = vscode.window.activeTextEditor;
  if (!ed) {
    return "";
  }
  return vscode.workspace.asRelativePath(ed.document.uri);
}

function showJson(title, text) {
  const doc = vscode.window.createOutputChannel(title, { log: false });
  doc.clear();
  doc.append(text);
  doc.show(true);
}

function applySarif(collection, folder, sarif) {
  collection.clear();
  const run = sarif && sarif.runs && sarif.runs[0];
  const results = (run && run.results) || [];
  const grouped = new Map();
  for (const result of results) {
    const loc = result.locations && result.locations[0];
    const phys = loc && loc.physicalLocation;
    const uriRel = phys && phys.artifactLocation && phys.artifactLocation.uri;
    const line = (phys && phys.region && phys.region.startLine) || 1;
    if (!uriRel) {
      continue;
    }
    const fileUri = vscode.Uri.joinPath(folder.uri, uriRel);
    const level =
      result.level === "error"
        ? vscode.DiagnosticSeverity.Error
        : vscode.DiagnosticSeverity.Warning;
    const range = new vscode.Range(
      Math.max(0, line - 1),
      0,
      Math.max(0, line - 1),
      200
    );
    const msg = (result.message && result.message.text) || result.ruleId || "RepoLens";
    const diag = new vscode.Diagnostic(range, msg, level);
    diag.source = COLLECTION;
    diag.code = result.ruleId;
    const key = fileUri.toString();
    if (!grouped.has(key)) {
      grouped.set(key, { uri: fileUri, diags: [] });
    }
    grouped.get(key).diags.push(diag);
  }
  for (const { uri, diags } of grouped.values()) {
    collection.set(uri, diags);
  }
}

async function runCheck(collection) {
  const folder = workspaceRoot();
  if (!folder) {
    vscode.window.showWarningMessage("RepoLens: open a folder first.");
    return;
  }
  const root = folder.uri.fsPath;
  const { code, stdout, stderr } = await runCli(root, [
    "check",
    "--path",
    root,
    "--format",
    "sarif",
  ]);
  let sarif;
  try {
    sarif = JSON.parse(stdout);
  } catch (err) {
    vscode.window.showErrorMessage("RepoLens: check did not return SARIF.");
    return;
  }
  applySarif(collection, folder, sarif);
  if (code !== 0 && stderr) {
    vscode.window.setStatusBarMessage(`RepoLens check exit ${code}`, 4000);
  }
}

async function runDiff() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout, stderr } = await runCli(root, ["check", "--path", root, "--diff"]);
  const text = (stdout || stderr || "").trim().split("\n")[0] || "check --diff finished";
  vscode.window.setStatusBarMessage(`RepoLens: ${text}`, 8000);
}

async function runDeps() {
  const folder = workspaceRoot();
  const mod = activeModule();
  if (!folder || !mod) {
    vscode.window.showWarningMessage("RepoLens: open a Python file.");
    return;
  }
  const root = folder.uri.fsPath;
  const deps = await runCli(root, ["graph", "deps", mod, "--path", root, "--json"]);
  const importers = await runCli(root, [
    "graph",
    "dependents",
    mod,
    "--path",
    root,
    "--json",
  ]);
  showJson(
    "RepoLens dependencies",
    JSON.stringify({ module: mod, deps: deps.stdout, importers: importers.stdout }, null, 2)
  );
}

async function runWouldCycle() {
  const folder = workspaceRoot();
  const fromMod = activeModule();
  if (!folder || !fromMod) {
    vscode.window.showWarningMessage("RepoLens: open a Python file.");
    return;
  }
  const toMod = await vscode.window.showInputBox({
    prompt: "Would this import cycle? Target module",
    placeHolder: "packcycle.b",
  });
  if (!toMod) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout, stderr, code } = await runCli(root, [
    "graph",
    "would-cycle",
    "--from",
    fromMod,
    "--to",
    toMod.trim(),
    "--path",
    root,
  ]);
  vscode.window.showInformationMessage(
    `would-cycle exit ${code}: ${(stdout || stderr || "").trim().slice(0, 200)}`
  );
}

async function runBreakup() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout } = await runCli(root, [
    "graph",
    "breakup",
    "--path",
    root,
    "--format",
    "json",
  ]);
  showJson("RepoLens breakup", stdout);
}

async function runPreviewCut() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const token = await vscode.window.showInputBox({
    prompt: "Preview cut (importer:imported)",
    placeHolder: "packcycle.a:packcycle.b",
  });
  if (!token) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout, stderr } = await runCli(root, [
    "graph",
    "breakup",
    "--path",
    root,
    "--omit-edge",
    token.trim(),
    "--format",
    "json",
  ]);
  showJson("RepoLens preview cut", stdout || stderr);
}

async function runDuplicates() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const rel = activeRel();
  const root = folder.uri.fsPath;
  const args = ["duplicates", "--path", root, "--format", "json"];
  if (rel) {
    args.push("--file", rel);
  }
  const { stdout } = await runCli(root, args);
  showJson("RepoLens duplicates", stdout);
}

async function runIgnore() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const ruleId = await vscode.window.showInputBox({
    prompt: "Ignore --id (stableId)",
  });
  if (!ruleId) {
    return;
  }
  const root = folder.uri.fsPath;
  const args = ["ignore", "add", "--path", root, "--id", ruleId.trim()];
  const rel = activeRel();
  if (rel) {
    args.push("--file", rel);
  }
  const { stdout, stderr, code } = await runCli(root, args);
  vscode.window.showInformationMessage(
    code === 0 ? stdout.trim() || "Ignored" : (stderr || stdout).trim()
  );
}

async function runExplain() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const fingerprint = await vscode.window.showInputBox({
    prompt: "Explain fingerprint / stableId",
  });
  if (!fingerprint) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout, stderr } = await runCli(root, [
    "explain",
    fingerprint.trim(),
    "--path",
    root,
  ]);
  showJson("RepoLens explain", stdout || stderr);
}

async function copyFullReview() {
  const folder = workspaceRoot();
  if (!folder) {
    return;
  }
  const root = folder.uri.fsPath;
  const cmd = `repolens review --path "${root}" --out "${root}/reports" --full-audit --deep --timeout 7200`;
  await vscode.env.clipboard.writeText(cmd);
  vscode.window.showInformationMessage(
    "Copied full review command. Paste it in a terminal. Save does not start a review."
  );
}

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
  const root = folder.uri.fsPath;
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
  void root;
}

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection(COLLECTION);
  context.subscriptions.push(collection);

  const cycleProvider = new CycleTreeProvider();
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("repolens.cycles", cycleProvider)
  );
  cycleProvider.load();

  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.check", () => runCheck(collection))
  );
  context.subscriptions.push(vscode.commands.registerCommand("repolens.diff", runDiff));
  context.subscriptions.push(vscode.commands.registerCommand("repolens.deps", runDeps));
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.wouldCycle", runWouldCycle)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.breakup", runBreakup)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.previewCut", runPreviewCut)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.duplicates", runDuplicates)
  );
  context.subscriptions.push(vscode.commands.registerCommand("repolens.ignore", runIgnore));
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.explain", runExplain)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.copyFullReview", copyFullReview)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.refreshCycles", () => cycleProvider.load())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.openCycleEdge", openCycleEdge)
  );

  let timer = null;
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(() => {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        // Save path: check SARIF + refresh cycles via CLI only (no model).
        runCheck(collection);
        cycleProvider.load();
      }, 500);
    })
  );

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  status.text = "RepoLens";
  status.command = "repolens.diff";
  status.tooltip = "Run cyclicity ratchet (check --diff)";
  status.show();
  context.subscriptions.push(status);
}

function deactivate() {}

module.exports = { activate, deactivate, moduleFromRel };
