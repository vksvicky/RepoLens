# Architecture Decision Records (ADRs)

RepoLens ADRs capture **why** the system is shaped the way it is, with **Mermaid diagrams** that render in GitHub and most Markdown previews.

| ADR | Title | Status |
|-----|-------|--------|
| [01](01_analysis_runtime_architecture.md) | Analysis runtime architecture | Accepted |
| [_diagram_legend.md](_diagram_legend.md) | Shared colour / prefix legend | — |

## Conventions

- Numbered files: `NN_short_snake_title.md`
- Link the [diagram legend](_diagram_legend.md) from any ADR that embeds Mermaid
- Prefer `flowchart` / `sequenceDiagram` (see legend — no `architecture-beta` in live fences)
- Keep CLI command UX details in [../design/cli-and-report-schema.md](../design/cli-and-report-schema.md); ADRs own runtime topology and decisions

Use the shared [diagram legend](_diagram_legend.md) for colours and prefixes across ADRs.
