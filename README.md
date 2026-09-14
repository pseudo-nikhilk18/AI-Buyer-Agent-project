# AI Purchasing Agent

A purchasing decision system that investigates operational evidence, decides what should happen, executes authorized purchase-order actions, and validates the real outcome.

The original project brief is in [`AI Buyer Agent project.pdf`](./AI%20Buyer%20Agent%20project.pdf).

## Current status

Purchase recommendation review is implemented end to end. The live agent investigation, blinded model proposal, deterministic loss guard, authorization, PO execution, read-back validation, buyer workspace, and separate evaluation paths are operational. Reviewer Docker packaging remains.

Latest checked-in proof: Gemini 2.5 Flash passed the blinded live case with a correct raw proposal and zero hard-safety failures; the separate system/safety regression passed 10/10 checks, including concurrent idempotency.

## Product

The supported product workflow reviews one purchase recommendation for the company's internal buyer. Customers create demand, the fulfillment node serves that demand, and an approved PO asks the external supplier to replenish the node.

```text
purchasing event
  -> agent investigation
  -> live model proposal
  -> deterministic loss-bounded guard
  -> risk-based authorization
  -> purchase-order action
  -> independent read-back validation
  -> complete, replan, or escalate
```

The live model selects evidence tools, states why each source is needed, closes missing-evidence gaps, compares safe candidates, and proposes a decision. It never receives fixture answers. Deterministic services control calculations, constraints, authorization, mutations, and validation. The raw proposal and guarded outcome remain separately inspectable.

Six variations exercise accept, modify, reject, investigate, human approval, and incorrect persisted state. Supplier shortfall, demand change, and budget records remain explicit additional probes rather than being misrepresented as complete workflows.

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
| Evaluation | Blinded live-agent graders plus deterministic system/safety regression |

Model names are configuration rather than hardcoded product decisions. Live mode uses the selected provider. Clearly labelled replay mode runs the same graph deterministically against seeded evidence without an API key and is not presented as live-model evaluation.

## Evaluation

Two evaluation paths prevent inflated claims:

- Live-agent evaluation grades the configured model's tool plan and raw proposal against hidden labels, then separately grades the guarded action and outcome.
- Replay system/safety regression proves policy, routing, authorization, concurrency-safe idempotency, mutation, validation, and recovery without claiming model intelligence.

Reports are written under [`artifacts/evaluations/`](./artifacts/evaluations).

## Local setup

Prerequisites: Python 3.13, Node.js 24 or newer, npm, and PostgreSQL 17.

Start PostgreSQL and create the database once:

```bash
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
brew services start postgresql@17
createdb buyer_agent
```

Start the API:

```bash
cd backend
cp .env.example .env
# Add your Gemini API key to .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
python main.py
```

Start the web app in a second terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The web app runs at `http://localhost:5173`, the API at `http://localhost:8000`, and API documentation at `http://localhost:8000/docs`. `GET /api/health` verifies the API and performs a real PostgreSQL query.

Run one blinded live-agent case from `backend/` (repeat `--case` or omit it for all six):

```bash
source .venv/bin/activate
python -m app.live_evaluation --case REC-MODIFY
```

Run the no-key system/safety regression:

```bash
AI_MODE=replay python -m app.evaluation
```

## Model configuration

The example environment selects live Gemini. Edit this line in `backend/.env`:

```text
GEMINI_API_KEY=replace-with-your-gemini-api-key
```

It defaults to `gemini-2.5-flash`. OpenAI and Anthropic remain supported by changing `LLM_PROVIDER`, `LLM_MODEL`, and the matching key variable. The application refuses incomplete live configuration. Use replay only for the explicit no-key regression command above.

## Project map

| File | Purpose |
| --- | --- |
| [`docs/prd.md`](./docs/prd.md) | Product capabilities, behavior, guardrails, and acceptance criteria. |
| [`docs/architecture.md`](./docs/architecture.md) | Stack, components, graph, data boundaries, and failure handling. |
| [`docs/evaluation.md`](./docs/evaluation.md) | Cases, graders, safety failures, metrics, and reporting. |
| [`docs/decisions.md`](./docs/decisions.md) | Consequential product and technical decisions with reasoning. |
| [`AGENTS.md`](./AGENTS.md) | Working standards for contributors and coding agents. |
| [`frontend/`](./frontend) | React buyer workspace for actors, demo scenarios, model investigation, raw proposals, guarded decisions, actions, and validation. |
| [`backend/`](./backend) | FastAPI API, LangGraph workflow, policy engine, simulator, live and replay evaluation runners, seed data, and migrations. |

No undocumented step should be required to run or understand the implemented project.

## Security

Never commit API keys, tokens, passwords, or other secrets. Provider credentials will be loaded from environment variables documented in `.env.example`.
