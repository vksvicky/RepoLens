# Fintech compliance overlay (opt-in)

**Not a certification.** This overlay adds checklist prompts and light heuristics for
payment / ledger style codebases. It does **not** replace a QSA, PCI assessor, or
your bank’s control framework. Keep Semgrep/CodeQL/secret scanners in CI.

## Namespaced checklist themes

| ID | Theme | Ask |
|----|-------|-----|
| `fintech.pci_pan` | Card data | Is PAN / track data ever logged, stored, or sent in clear text? |
| `fintech.ledger_integrity` | Ledger | Are money movements append-only with immutable audit ids? |
| `fintech.webhook_auth` | Integrations | Are payment webhooks verified with constant-time HMAC / SDK verify? |
| `fintech.secrets_hsm` | Keys | Are signing keys via HSM/KMS — never hard-coded or in git? |
| `fintech.recon` | Ops | Is there a reconciliation path for failed / duplicate settlements? |

## Honesty

Findings are **due-diligence hints**. Passing this overlay ≠ PCI DSS / SOC 2 certified.
