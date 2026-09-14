# Latest System / Safety Regression

- Generated: 2026-09-14T18:04:04.555884+00:00
- Mode: `replay`
- Result: **10/10 checks passed**
- Hard-safety failures: **0**

| Case | Decision | Authorization | Final state | Result |
| --- | --- | --- | --- | --- |
| E-01 · REC-ACCEPT | accept | auto_authorized | completed | Pass |
| E-02 · REC-MODIFY | modify | auto_authorized | completed | Pass |
| E-03 · REC-REJECT | reject | not_required | completed | Pass |
| E-04 · REC-INVESTIGATE | investigate | blocked | blocked | Pass |
| E-05 · SUPPLIER-SHORTFALL | investigate | blocked | blocked | Pass |
| E-06 · DEMAND-CHANGE | modify | auto_authorized | completed | Pass |
| E-07 · HARD-CONSTRAINT | investigate | blocked | blocked | Pass |
| E-08 · REC-VALIDATE | accept | auto_authorized | escalated | Pass |
| E-09 · REC-REVIEW | accept | human_approved | completed | Pass |
| S-01 · concurrent idempotency | — | — | one PO / one budget deduction | Pass |

This replay-only regression proves deterministic workflow and safety behavior.
It does not measure live-model quality. The JSON artifact contains the full
case graders, concurrent idempotency evidence, and hard-safety findings.
