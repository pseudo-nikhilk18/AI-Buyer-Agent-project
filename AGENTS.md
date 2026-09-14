# Working Agreement

This file applies to the whole repository. It records the working standards for contributors and coding agents.

## How we work

- Work like friendly, candid teammates. Be direct, explain trade-offs, and raise concerns early.
- Build one feature at a time as a complete end-to-end capability: agree on the outcome, define acceptance criteria, implement, verify, then document.
- Prefer a small reliable solution over broad unfinished scope.
- Hold every implemented capability to a production-quality bar within the agreed product boundary: correct, secure, observable, accessible, evaluated, and easy to explain.
- Keep code and docs simple and clean. Production quality does not mean speculative infrastructure or unnecessary abstractions.
- Never silently decide a material product, UX, architecture, data, technology, or scope question. Bring it to the project owner with a recommendation, reasoning, and trade-offs before acting.
- Mechanical, reversible implementation choices are allowed only inside an agreed direction; surface any choice that could reasonably affect later work.
- Treat examples and exploratory comments as context, not approved requirements. Confirm before promoting them into product scope, architecture, or evaluation criteria.
- Treat accepted scope and recorded decisions as binding. Do not reopen or expand them during implementation; surface a genuine conflict before changing direction.
- Derive recommendations from the problem and evidence. Do not mirror a technology or idea merely because the project owner mentioned prior experience with it.
- Lead updates with outcomes. Avoid bloated status reports or documentation.
- Match communication to an experienced technical collaborator. Do not repeat established context, re-explain basics, or pad responses; recap only when materially useful or requested.
- Delegate clearly independent work in parallel when it materially shortens delivery; keep integration, decisions, and final verification with the primary agent.
- Do not select a service that requires paid credentials without explicit approval.
- Never expose secrets or commit credentials.

## Source of truth

- `AI Buyer Agent project.pdf`: original project brief; never edit it.
- `docs/prd.md`: product scope, requirements, and acceptance criteria.
- `docs/decisions.md`: meaningful product or technical decisions and their reasoning.
- `docs/architecture.md`: current system structure, boundaries, and data flow.
- `docs/evaluation.md`: product evaluation cases, graders, safety gates, and reporting.
- `README.md`: the front door and end-to-end project map.

If documents conflict, the original project brief wins, followed by the PRD and then the implementation. Fix the stale document in the same change.

## Feature workflow

1. State the user outcome and acceptance criteria.
2. Identify data, tools, constraints, failure paths, and the validation loop.
3. Implement the agreed capability completely across every required layer.
4. Run relevant automated checks and exercise the demo path.
5. Update only the living docs affected by the change.

A feature is done when its evaluation proves the intended decision, evidence gathering, constraint handling, action, validation, and important failure behavior; relevant engineering checks pass; and setup or behavior changes are documented.

## Documentation habits

- Update `docs/prd.md` when requirements, scope, or acceptance criteria change.
- Add to `docs/decisions.md` when we make a consequential choice that future work should not rediscover. Do not log trivial edits.
- Update `docs/architecture.md` only for substantial changes to components, boundaries, interfaces, persistence, or data flow.
- Keep `README.md` accurate whenever setup, commands, configuration, features, or repository structure changes.
- When the project owner gives a durable instruction about future behavior or collaboration, add the concise rule here in the same change.

## Engineering guardrails

- Treat LLM output as untrusted input. Use typed schemas and deterministic business-rule checks.
- Keep evaluation answers out of model inputs. Record the raw live-model proposal separately from the guarded business outcome, and never present replay results as AI quality.
- Use the configured live model for product demonstrations and AI evaluations. Replay mode is only for deterministic debugging or engineering regression and must not be run as the default verification path.
- Define evaluation examples with separate inputs, evaluator-only references, and public metadata. Seed only inputs; apply references after the target run; record dataset and prompt versions.
- Evaluate agents by tool trajectory, raw decision, grounded explanation, final outcome, hard safety, and repeated-run stability. Optional LLM judges stay separate and never conceal exact failures.
- Target zero preventable loss introduced by AI. Automatic action must be at least as safe as the validated baseline under conservative evidence; uncertainty reduces authority rather than increasing risk.
- Do not assume blanket human approval or blanket autonomy. Execute purchasing mutations only under the agreed authorization policy, and route uncertain or high-risk actions to human review.
- After an action, read back the resulting state and validate it independently. Never report success from an API acknowledgement alone.
- Keep domain logic separate from UI, LLM prompts, and data access so it is independently verifiable.
- Frontend anti-slop: establish a product-specific visual direction before coding; use realistic purchasing content, intentional hierarchy, responsive behavior, accessible interactions, and screenshot-based critique. Avoid generic dashboard templates and decorative effects without purpose.
- Open the product UI with simple plain-language agent tests. Present each result as purchasing situation, information investigated, agent decision, action taken, and result validation; keep technical codes and graph internals optional.
- Backend anti-slop: define contracts and failure modes first; validate at runtime; use typed errors, idempotent writes, structured traces, and evaluation-driven engineering checks. No placeholder logic, fake success states, swallowed errors, or happy-path-only implementations.
- Run the web app and API directly on macOS against local PostgreSQL during development. Maintain Docker Compose as the reviewer setup and validate it outside the routine local workflow.
- Use a standard Python `.venv` and `requirements.txt` for backend dependencies. Discuss alternate package managers or additional lint and test tools before adding them.
- Start Vite and FastAPI separately and configure the browser-facing API URL through `VITE_API_BASE_URL`. Add a development proxy only if an agreed requirement needs one.
- Do not add an infrastructure layer such as Nginx when the existing runtime can serve the agreed reviewer demo adequately. Every extra service needs a concrete requirement.
- When available, use `frontend-design` for visual direction, `vercel-react-best-practices` while building React, `web-design-guidelines` for UI audits, and `security-best-practices` for secure-by-default implementation.
- Preserve Git history and existing user changes. Keep commits focused and independently understandable.
- Commit and push each cohesive milestone after its implementation, verification, and affected documentation are complete. Do not commit known-broken intermediate states.
- Use Conventional Commits: `<type>[optional scope]: <imperative description>`. Choose the type by intent: `feat` for capability, `fix` for a real defect, `docs` for documentation only, `test` for evaluations or tests, `refactor` for behavior-preserving structure, and `chore` for maintenance. Use a short, stable scope only when it adds clarity.

## Capability sequence

1. Establish the shared purchasing case, evidence, policy, authorization, action, and validation model.
2. Connect recommendation review, supplier shortfall, demand change, and constraint-resolution triggers to the shared workflow.
3. Build the evaluation suite alongside the capabilities it measures, including failed-action recovery.
