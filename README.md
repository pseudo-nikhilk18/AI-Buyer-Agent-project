# AI Purchasing Agent

A purchasing decision system that investigates operational evidence, decides what should happen, executes authorized purchase-order actions, and validates the real outcome.

The original project brief is in [`AI Buyer Agent project.pdf`](./AI%20Buyer%20Agent%20project.pdf).

## Current status

The product, architecture, and evaluation blueprints are finalized. Application implementation has not started.

## Product

One shared workflow handles purchase recommendation review, supplier shortfall, demand change, and purchasing constraints.

```text
purchasing event
  -> agent investigation
  -> deterministic purchasing policy
  -> decision and action plan
  -> risk-based authorization
  -> purchase-order action
  -> independent read-back validation
  -> complete, replan, or escalate
```

The LLM selects tools, investigates uncertainty, proposes a plan, explains it, and may replan. Deterministic services control calculations, constraints, authorization, mutations, and validation.

## Technology

| Area | Choice |
| --- | --- |
| Web | React JavaScript, Vite, Tailwind CSS |
| API | Python, FastAPI, Pydantic |
| Agent orchestration | LangGraph |
| LLMs | Configurable Gemini, OpenAI, or Anthropic provider and model |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Development runtime | Native Vite and FastAPI processes with local PostgreSQL |
| Reviewer runtime | Docker Compose |
| Evaluation | Deterministic Python graders with focused Playwright verification |

Model names are configuration rather than hardcoded product decisions. Live mode uses the selected provider; clearly labelled replay mode lets a reviewer inspect captured runs without an API key.

## Evaluation

The evaluation suite measures the complete purchasing outcome: evidence gathered, decision correctness, constraint compliance, authorization, action, post-action validation, and recovery.

It includes successful decisions, supplier shortfall, demand change, hard constraints, missing evidence, and an action that acknowledges success but persists incorrect state.

## Project map

| File | Purpose |
| --- | --- |
| [`docs/prd.md`](./docs/prd.md) | Product capabilities, behavior, guardrails, and acceptance criteria. |
| [`docs/architecture.md`](./docs/architecture.md) | Stack, components, graph, data boundaries, and failure handling. |
| [`docs/evaluation.md`](./docs/evaluation.md) | Cases, graders, safety failures, metrics, and reporting. |
| [`docs/decisions.md`](./docs/decisions.md) | Consequential product and technical decisions with reasoning. |
| [`AGENTS.md`](./AGENTS.md) | Working standards for contributors and coding agents. |

Exact setup, configuration, commands, seeded data, evaluation usage, and demo instructions will be added as those capabilities are implemented. No undocumented step should be required to run or understand the completed project.

## Security

Never commit API keys, tokens, passwords, or other secrets. Provider credentials will be loaded from environment variables documented in `.env.example`.
