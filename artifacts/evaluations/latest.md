# Latest Purchasing Evaluation

- Generated: 2026-09-14T16:34:26.208276+00:00
- Mode: `replay`
- Result: **9/9 passed**
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

The JSON artifact contains grader-level results, quantities, reason codes,
workflow steps, idempotency evidence, and hard-safety findings.
