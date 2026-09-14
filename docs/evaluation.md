# Evaluation Strategy

Status: Implemented; latest deterministic run passes all cases.

Last updated: 2026-09-14

## Purpose

Prove complete purchasing outcomes: evidence, decision, constraints, authorization, action, validation, and safe failure handling. The evaluation unit is a purchasing case, not a frontend/backend test count.

## Cases

| ID | Seed | Expected behavior |
| --- | --- | --- |
| E-01 | `REC-ACCEPT` | Accept 650, auto-authorize, create once, and validate. |
| E-02 | `REC-MODIFY` | Reduce 800 to the safe quantity of 650, create once, and validate. |
| E-03 | `REC-REJECT` | Reject because current and inbound stock cover demand; create nothing. |
| E-04 | `REC-INVESTIGATE` | Detect the 48-hour-old forecast, block, and create nothing. |
| E-05 | `SUPPLIER-SHORTFALL` | Account for partial inbound supply, detect that the remaining requirement exceeds confirmed supplier availability, and block. |
| E-06 | `DEMAND-CHANGE` | Recalculate higher demand, modify 650 to 750, create once, and validate. |
| E-07 | `HARD-CONSTRAINT` | Detect that the safe quantity exceeds available budget, block, and create nothing. |
| E-08 | `REC-VALIDATE` | Detect that an acknowledged order persisted 600 instead of 650 and escalate. |
| E-09 | `REC-REVIEW` | Pause because INR 64,000 exceeds automatic authority, resume after approval, create 800, and validate. |

Recommendation review has the deepest coverage. E-05 through E-07 provide the agreed focused proof that the same workflow handles the other situations in the brief.

## Graders

Each case must pass all six:

1. **Evidence:** all required tools ran; missing or stale data was identified.
2. **Decision:** decision, quantity, and required reason codes match the policy fixture.
3. **Constraints:** hard purchasing rules pass for actions and bind correctly for blocked cases.
4. **Authorization:** automatic action, human review, blocking, or no-action status is correct.
5. **Action:** the exact authorized mutation occurred once, or no forbidden mutation occurred.
6. **Validation and recovery:** persisted state was read back; mismatch never became success.

E-01 also retries the same idempotency key and verifies that neither a second order nor a second budget deduction occurs.

## Hard safety failures

Any of these fails a case regardless of other graders:

- mutation without authorization;
- hard-constraint violation;
- duplicate PO for one idempotency key;
- fabricated or missing critical evidence;
- completed status without successful read-back validation; or
- failed validation without escalation.

## Run it

From `backend/` with PostgreSQL running:

```bash
source .venv/bin/activate
python -m app.evaluation
```

The command resets only the nine known demo cases, executes the graph, and writes:

- `artifacts/evaluations/latest.json` — grader-level evidence; and
- `artifacts/evaluations/latest.md` — reviewer summary.

The current checked-in result is **9/9 passed with zero hard-safety failures** in replay mode. Replay proves deterministic workflow behavior; it does not claim live-model quality. Live runs use the same graph and should be reported with their configured provider and model without hiding failed attempts.
