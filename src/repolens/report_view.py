"""Zero-dependency interactive HTML viewer for FindingReport JSON."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.schema import FindingReport

_VIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>RepoLens report view</title>
<style>
body { font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 56rem; }
.meta { display:flex; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }
.chip { background:#f0f0f0; padding:0.35rem 0.6rem; border-radius:4px; }
#filter { width:100%; padding:0.5rem; margin:0.5rem 0 1rem; }
.finding { border:1px solid #ddd; margin:0.5rem 0; padding:0.75rem; }
.finding.hidden { display:none; }
.sev-CRITICAL { border-left:6px solid #c62828; }
.sev-HIGH { border-left:6px solid #ef6c00; }
.sev-MEDIUM { border-left:6px solid #f9a825; }
.sev-LOW { border-left:6px solid #90a4ae; }
details { margin-top:0.5rem; }
pre { background:#f7f7f7; padding:0.75rem; overflow:auto; }
.graph { margin:1rem 0; }
</style></head><body>
<h1>RepoLens report</h1>
<div class="meta" id="meta"></div>
<div class="graph">__SVG__</div>
<label for="filter">Filter findings</label>
<input id="filter" type="search" placeholder="severity, title, file, fingerprint…"/>
<div id="findings"></div>
<script type="application/json" id="report-data">__DATA__</script>
<script>
const report = JSON.parse(document.getElementById('report-data').textContent);
const meta = document.getElementById('meta');
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}
function pct(v) { return v == null ? 'n/a' : v + '%'; }
const s = report.summary;
meta.innerHTML = [
  ['Gate', report.confidence + '%'],
  ['Security', pct(report.securityAuditConfidence)],
  ['Reliability', pct(report.reliabilityAuditConfidence)],
  ['Architecture', pct(report.architectureAuditConfidence)],
  ['C/H/M/L', [s.critical, s.high, s.medium, s.low].join('/')],
].map(([k,v]) =>
  '<span class="chip"><strong>'+esc(k)+'</strong> '+esc(v)+'</span>'
).join('');

const box = document.getElementById('findings');
(report.issues || []).forEach((issue) => {
  const el = document.createElement('article');
  el.className = 'finding sev-' + issue.severity;
  el.dataset.severity = issue.severity;
  el.dataset.search = [
    issue.severity, issue.title, issue.file, issue.category,
    issue.stableId || '', issue.explanation || '', issue.impact || ''
  ].join(' ').toLowerCase();
  el.innerHTML =
    '<header><strong>'+esc(issue.severity)+'</strong> · '+esc(issue.title)+
    '<div><code>'+esc(issue.file)+':'+esc(issue.line)+'</code>'+
    (issue.stableId ? ' · <code>'+esc(issue.stableId)+'</code>' : '')+
    '</div></header>'+
    '<p>'+esc(issue.explanation || '')+'</p>'+
    '<details><summary>Remediation</summary>'+
    '<p><em>Impact:</em> '+esc(issue.impact || 'n/a')+'</p>'+
    '<p>'+esc(issue.recommendedFix || '')+'</p>'+
    '<pre>'+esc(issue.codeExample || '(no codeExample)')+'</pre></details>';
  box.appendChild(el);
});

document.getElementById('filter').addEventListener('input', (ev) => {
  const q = ev.target.value.trim().toLowerCase();
  document.querySelectorAll('.finding').forEach((el) => {
    el.classList.toggle('hidden', q && !el.dataset.search.includes(q));
  });
});
</script>
</body></html>
"""


def _cycle_svg(report: FindingReport) -> str:
    """Tiny static SVG: cyclicity dial + module count (no SaaS)."""
    graph = report.graph
    cyc = graph.cyclicity if graph else 0
    mods = graph.moduleCount if graph else 0
    cycles = graph.cycleCount if graph else 0
    fill = min(100, int(cyc * 2))
    color = "#2e7d32" if cyc == 0 else "#f9a825" if cyc < 10 else "#c62828"
    width = f"{fill * 1.96:.1f}"
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="220" height="120" role="img"
     aria-label="Import graph cyclicity {cyc}">
  <rect width="220" height="120" fill="#fafafa" stroke="#ddd"/>
  <text x="12" y="24" font-family="system-ui" font-size="14">Import graph</text>
  <text x="12" y="48" font-family="system-ui" font-size="12">
    modules {mods} · cycle groups {cycles}
  </text>
  <text x="12" y="72" font-family="system-ui" font-size="12">cyclicity</text>
  <rect x="12" y="80" width="196" height="14" fill="#eee"/>
  <rect x="12" y="80" width="{width}" height="14" fill="{color}"/>
  <text x="12" y="112" font-family="system-ui" font-size="12">{cyc}</text>
</svg>
"""


def build_view_html(report: FindingReport) -> str:
    """Single-file HTML+JS: filterable findings, expandable remediation, cycle SVG."""
    data = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    # Prevent </script> breakout in JSON text node.
    data = data.replace("<", "\\u003c")
    return _VIEW_TEMPLATE.replace("__SVG__", _cycle_svg(report)).replace(
        "__DATA__", data
    )


def write_view_html(report: FindingReport, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build_view_html(report), encoding="utf-8")
    return dest
