# Product Requirements: AI Purchasing Agent

Status: Finalized product blueprint; implementation has not started.

Source: original project brief in `AI Buyer Agent project.pdf`

Last updated: 2026-09-14

## 1. Product goal

Automate purchasing investigation and action while protecting the buyer from unnecessary stock, shortages, constraint violations, and incorrect execution.

This is an operational decision system, not a general chatbot. It must investigate evidence, decide, act when authorized, and verify the actual result.

## 2. Primary user

A retail or quick-commerce buyer responsible for replenishment across products, suppliers, and fulfillment nodes. They need decisions that are fast, explainable, auditable, and safe.

## 3. Supported purchasing situations

One shared workflow handles four event types:

1. **Recommendation review:** accept, modify, reject, or investigate a proposed purchase.
2. **Supplier shortfall:** replan when a supplier cannot fulfill the complete order.
3. **Demand change:** respond when actual demand makes the current purchasing plan insufficient or excessive.
4. **Constraint resolution:** find a safe course when budget, storage, supplier, quantity, or timing constraints block the obvious action.

These situations reuse the same evidence, policies, authorization, action, and validation capabilities.

## 4. Operating workflow

1. Receive a purchasing event and create a traceable case.
2. Let the agent select and call the tools needed to investigate it.
3. Check evidence completeness, freshness, and consistency.
4. Calculate the replenishment requirement and feasible options using deterministic policy code.
5. Produce a structured decision and explain the important factors.
6. Apply the risk-based authorization policy.
7. Execute an authorized purchase-order action idempotently.
8. Read the resulting state back from the purchasing system.
9. Validate the result and either complete, replan, or escalate the case.

## 5. Intelligence and authority

The LLM may:

- choose investigation tools;
- identify missing or conflicting evidence;
- compare policy-compliant options;
- propose a purchasing plan;
- explain its decision; and
- replan after changed data or a failed action.

The LLM may not bypass data validation, purchasing rules, authorization, or post-action validation. Deterministic Python services are authoritative for calculations, constraints, and executable actions.

## 6. Decision contract

Every run returns a structured record containing:

- `decision`: `accept`, `modify`, `reject`, or `investigate`;
- recommended and proposed quantities;
- product, supplier, and fulfillment node;
- evidence used with source timestamps;
- missing, stale, or conflicting evidence;
- binding constraints and reason codes;
- proposed action and expected resulting state;
- `authorization`: `auto_authorized`, `human_review`, or `blocked`;
- action status; and
- `validation`: `not_required`, `pending`, `validated`, `failed`, `replanning`, or `escalated`.

The product must not present an uncalibrated LLM confidence score as evidence. It should expose concrete uncertainty and data-quality signals instead.

## 7. Required evidence and tools

- Sellable, reserved, and damaged inventory by product and node.
- Expected demand, horizon, recent sales behavior, and forecast timestamp.
- Open purchase orders, quantities, statuses, and expected arrival dates.
- Supplier lead time, minimum order quantity, case pack, price, availability, reliability, and active status.
- Remaining purchasing budget and committed spend.
- Available storage capacity and per-unit storage requirement.
- Safety-stock policy, authority policy, and permitted data-age thresholds.
- Alternate suppliers when the current supplier cannot meet the need.

Seeded data must be explicit, inspectable, deterministic, and realistic enough to produce genuine trade-offs.

## 8. Purchasing rules

- Inventory position includes usable stock and eligible inbound supply, less reservations.
- Target stock covers forecast demand across lead time and review period plus safety stock.
- A proposed quantity must respect supplier availability, MOQ, case pack, budget, storage, and timing.
- Missing, stale, or conflicting critical evidence prevents automatic action.
- The agent cannot silently change product, supplier, or node.
- No zero or negative purchase order can be created.
- The action service rechecks mutable evidence immediately before writing.
- Authorization is bound to the exact action payload; changed actions require new authorization.
- Every mutation uses an idempotency key.
- Success requires read-back validation from persisted state, not an API acknowledgement.

## 9. Authorization policy

Automatic execution is allowed only when evidence is complete and current, deterministic checks pass, the proposed supplier/product/node are permitted, exposure is within configured authority, and the action can be validated.

Human review is required for policy-defined high exposure, a new supplier or node, cancellation or material amendment of an existing commitment, unresolved evidence conflict, or recovery from an unsafe outcome.

Blocked cases cannot execute. They must identify the blocking evidence or constraint and the next information or decision required.

## 10. Functional requirements

### FR-1 — Investigate

The agent calls named, typed tools and records the evidence obtained, its source, and its timestamp.

### FR-2 — Decide

The system produces one valid decision supported by the gathered evidence and deterministic purchasing policy.

### FR-3 — Authorize

The system records why an action was automatically authorized, blocked, or routed to a human. Human input, when required, applies to the exact proposed action.

### FR-4 — Act

The system creates, amends, or cancels a simulated purchase order only after authorization and records every attempt under the case trace.

### FR-5 — Validate and recover

The system reads back the purchase order and affected constraints, compares actual with intended state, and routes mismatch to bounded retry, replanning, safe compensation, or escalation. It must never report invalid state as success.

### FR-6 — Audit

The system preserves the event, tool calls, evidence, policy results, decision, authorization, action attempts, validation, and state transitions under one trace ID.

### FR-7 — Buyer workspace

The interface shows cases, evidence, calculations, constraints, decision, authorization, action, and validation as an operational workflow rather than a chat transcript.

### FR-8 — Provider configuration

The agent supports Gemini, OpenAI, and Anthropic through a provider-neutral adapter. A configured provider/model is explicit; the purchasing graph and evaluation cases do not change between providers.

## 11. Quality requirements

- Reliable: explicit states, idempotent writes, bounded retries, and no fake success.
- Explainable: every decision links to concrete evidence and policy results.
- Safe: secrets remain outside source control and no action bypasses authorization.
- Evaluatable: deterministic graders can verify evidence, decisions, constraints, actions, validation, and recovery.
- Maintainable: UI, agent orchestration, domain policy, persistence, and integrations remain separate.
- Accessible: the complete buyer workflow is usable with keyboard and assistive technology.
- Repeatable: Docker provides a documented local environment and seeded reset path.
- Honest: replayed agent runs are clearly labelled and never counted as live evaluation.

## 12. Acceptance criteria

The completed product must let a reviewer:

- start the system through the documented Docker workflow;
- run seeded cases covering all four purchasing situations;
- inspect which evidence and tools drove each decision;
- observe all four decision outcomes across the evaluation set;
- observe both automatic authorization and human review;
- see an authorized purchase-order action change persisted state;
- see the validator catch a deliberately incorrect outcome; and
- run an evaluation command that produces a scored, inspectable report.

All hard safety graders in `docs/evaluation.md` must pass.

## 13. Policy values to set with seed data

The architecture is fixed, but these business values remain explicit configuration rather than silent assumptions:

- forecast and operational-data freshness windows;
- lead-time review horizon and safety-stock policy;
- automatic spend and quantity authority limits;
- what constitutes a material purchase-order amendment; and
- retry limits and compensatable action types.
