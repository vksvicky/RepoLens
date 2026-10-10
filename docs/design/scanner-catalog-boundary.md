# Scanner catalog boundary

RepoLens runs five scanners and normalizes their output into `Issue` records on `FindingReport`:

| Tool | What it contributes |
| --- | --- |
| gitleaks | Secrets in source and git history |
| semgrep | SAST patterns |
| osv | Known vulnerabilities in dependencies |
| trivy | Filesystem and image vulnerabilities, plus SBOM input |
| checkov | Infrastructure-as-code misconfiguration |

`parse_scanners_flag` rejects any other name. A port scanner, injector, crawler, or extra linter is not a sixth wrapper.

Other tools arrive as SARIF through `--import-sarif`. Those results are normalized into the same `Issue` model and show up in the same Markdown, JSON, and gate. They are not teed to the terminal as raw tool logs.

Terminal lines from `ReviewProgress` are operator status (phase, heartbeat). They are not a dump of scanner stdout. Scanner processes are captured and parsed. Ratchet scoring stays the import-graph cycle-debt check; it is not a score applied to every scanner row.
