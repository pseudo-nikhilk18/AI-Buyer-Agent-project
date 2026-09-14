# Decision Log

Only choices with meaningful future impact belong here. `Proposed` decisions are not locked until implementation confirms them; `Withdrawn` records an assumption that was explicitly rejected.

| ID | Date | Status | Decision | Why |
| --- | --- | --- | --- | --- |
| D-001 | 2026-09-14 | Accepted | Build purchase recommendation review as a complete, production-quality workflow. | It exercises the full investigate, decide, authorize, act, and validate loop. |
| D-002 | 2026-09-14 | Accepted | Use deterministic policy checks as the authority for quantities and constraints; use the LLM for tool orchestration and explanation. | This keeps the agent useful while making safety and evaluation reproducible. |
| D-003 | 2026-09-14 | Withdrawn | Require human approval before every purchasing write. | This was an unapproved assumption. The system needs an explicit risk-based authorization policy that can support both autonomous action and human review. |
| D-004 | 2026-09-14 | Accepted | Treat an action as successful only after read-back and independent validation. | Reliable purchasing requires detecting and handling outcomes that differ from the intended action. |
| D-005 | 2026-09-14 | Accepted | Keep project guidance in a small living doc set: README, PRD, decisions, architecture, and AGENTS. | It provides continuity without duplicating large specifications. |
| D-006 | 2026-09-14 | Superseded | Provide a Docker-based local setup. | Replaced by D-015 after the development and reviewer workflows were clarified. |
| D-007 | 2026-09-14 | Accepted | Support recommendation review, supplier shortfall, demand change, and purchasing constraints through one shared workflow. | The situations use the same evidence, policies, actions, and feedback loop; separate systems would duplicate logic. |
| D-008 | 2026-09-14 | Accepted | Use risk-based action authorization rather than mandatory human approval or unrestricted autonomy. | Safe actions should be automated while uncertain, high-impact, or policy-breaking actions require review. |
| D-009 | 2026-09-14 | Accepted | Use React JavaScript with Vite and Tailwind CSS for the web application, and Python with FastAPI for the API. | This keeps the UI focused and gives the agent and domain layers access to the mature Python ecosystem. |
| D-010 | 2026-09-14 | Accepted | Use LangGraph for stateful orchestration while keeping purchasing rules in ordinary Python services. | The workflow needs conditional routing, checkpoints, replanning, and recoverable execution without coupling business rules to the framework. |
| D-011 | 2026-09-14 | Accepted | Use PostgreSQL through SQLAlchemy and Alembic as the only application database and as the LangGraph checkpoint store. | Purchasing records need relational integrity and transactions, while JSONB can hold flexible evidence and traces. |
| D-012 | 2026-09-14 | Accepted | Make the LLM provider and model configurable, initially supporting Gemini, OpenAI, and Anthropic. | Reviewers can use credentials they already have, and provider choice remains outside purchasing logic. |
| D-013 | 2026-09-14 | Accepted | Treat assessment-aligned product evaluation as the primary proof of quality. | The brief evaluates decisions, evidence, constraints, actions, validation, and recovery rather than test counts by technical layer. |
| D-014 | 2026-09-14 | Accepted | Provide clearly labelled live and replay AI modes. | Live mode proves agent behavior; replay mode lets reviewers inspect the product without credentials and must never be presented as a live evaluation. |
| D-015 | 2026-09-14 | Accepted | Run the web app and API natively against local PostgreSQL during development; keep Docker Compose as the reviewer setup. | Native processes give a faster local feedback loop while Docker keeps reviewer startup reproducible. |
| D-016 | 2026-09-14 | Accepted | Start Vite and FastAPI independently and configure the frontend with the API's local URL instead of a Vite proxy. | The explicit service boundary matches local development and keeps runtime behavior easy to understand. |
