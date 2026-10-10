# Healthtech compliance overlay (opt-in)

**Not a certification.** This overlay adds checklist prompts and light heuristics for
clinical / PHI-adjacent codebases. It does **not** replace a HIPAA assessor, BAA
review, or clinical safety board. Keep scanners and your GRC tooling in CI.

## Namespaced checklist themes

| ID | Theme | Ask |
|----|-------|-----|
| `healthtech.phi_logging` | PHI | Is patient / member PHI logged, traced, or dumped in errors? |
| `healthtech.access_audit` | Access | Are clinical record reads attributable (who/when/why)? |
| `healthtech.min_necessary` | Scope | Do APIs enforce minimum-necessary field projection? |
| `healthtech.baa_boundary` | Vendors | Are third-party processors behind documented BAA boundaries? |
| `healthtech.retention` | Retention | Is PHI retention / deletion policy enforced in code paths? |

## Honesty

Findings are **due-diligence hints**. Passing this overlay ≠ HIPAA / HITRUST certified.
