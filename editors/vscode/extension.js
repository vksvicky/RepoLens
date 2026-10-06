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
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
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
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!folder) {
    return;
  }
  const root = folder.uri.fsPath;
  const { stdout, stderr } = await runCli(root, ["check", "--path", root, "--diff"]);
  const text = (stdout || stderr || "").trim().split("\n")[0] || "check --diff finished";
  vscode.window.setStatusBarMessage(`RepoLens: ${text}`, 8000);
}

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection(COLLECTION);
  context.subscriptions.push(collection);

  context.subscriptions.push(
    vscode.commands.registerCommand("repolens.check", () => runCheck(collection))
  );
  context.subscriptions.push(vscode.commands.registerCommand("repolens.diff", runDiff));

  let timer = null;
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(() => {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        runCheck(collection);
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

module.exports = { activate, deactivate };
