# Domain pack: Azure Sentinel / Logic Apps SOAR

**Opt-in only.** Apply when reviewing Microsoft Sentinel analytics rules, Logic Apps,
Playbooks, or related ARM/Bicep/JSON automation. Do **not** invent Azure control-plane
facts; cite the workflow or rule file.

## Checklist themes

1. **Hardcoded tenant / subscription IDs** — Prefer Key Vault references, parameters, or
   managed identity; flag literals that lock automation to one tenant/subscription.
2. **Connector / credential pollution** — Client secrets, shared keys, or PATs embedded in
   Logic App connections or Sentinel playbook definitions.
3. **MSI / RBAC over-privilege** — Workflows that assume broad Owner/Contributor where a
   scoped role would do; missing least-privilege notes for managed identity.
4. **SOAR / playbook loops** — Recursive or unbounded automation (self-invoking Logic Apps,
   alert → playbook → alert) without concurrency / timeout guards.
5. **External data / unsafe enrichment** — Analytics rules or playbooks that pull untrusted
   external content into automation without validation.

## Output rules

- Severity: Critical/High for secrets and hard-coded credentials; Medium for tenant/subscription
  literals and loose RBAC; Low for documentation gaps.
- Critical/High require non-empty `impact` and `codeExample`.
- Category hint: `pack.azure_sentinel` when the finding is pack-specific.
- Prefer evidence from the cited JSON/Bicep/YAML; do not claim Checkov/ARM-TTK coverage.
