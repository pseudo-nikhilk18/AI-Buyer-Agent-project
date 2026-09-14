# AI Purchasing Agent

A purchasing decision system that investigates operational evidence, decides what should happen, executes authorized purchase-order actions, and validates the real outcome.

The original project brief is in [`AI Buyer Agent project.pdf`](./AI%20Buyer%20Agent%20project.pdf).

## Current status

The purchasing workflow and buyer workspace are implemented. All nine deterministic end-to-end evaluations pass with zero hard-safety failures. Reviewer Docker packaging remains.

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
| Evaluation | Deterministic Python graders |

Model names are configuration rather than hardcoded product decisions. Live mode uses the selected provider. Clearly labelled replay mode runs the same graph deterministically against seeded evidence without an API key and is not presented as live-model evaluation.

## Evaluation

The evaluation suite measures the complete purchasing outcome: evidence gathered, decision correctness, constraint compliance, authorization, action, post-action validation, and recovery.

It includes all four decisions, supplier shortfall, demand change, hard constraints, stale evidence, human approval, idempotent retry, and an action that acknowledges success but persists incorrect state. The latest report is in [`artifacts/evaluations/latest.md`](./artifacts/evaluations/latest.md).

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

Run the complete backend evaluation from `backend/`:

```bash
source .venv/bin/activate
python -m app.evaluation
```

## Model configuration

The copied backend environment is ready to run as-is. `AI_MODE=replay` exercises the complete seeded workflow without calling an LLM or requiring an API key.

To use Gemini instead, edit `backend/.env`: change `AI_MODE` to `live`, then add these three lines:

```text
AI_MODE=live
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.8-flash
GEMINI_API_KEY=replace-with-your-gemini-api-key
```

The model is a stable Gemini API model, but availability and rate limits depend on the key. OpenAI and Anthropic remain supported by using their provider name, model name, and matching key variable. The application refuses incomplete live configuration.

## Project map

| File | Purpose |
| --- | --- |
| [`docs/prd.md`](./docs/prd.md) | Product capabilities, behavior, guardrails, and acceptance criteria. |
| [`docs/architecture.md`](./docs/architecture.md) | Stack, components, graph, data boundaries, and failure handling. |
| [`docs/evaluation.md`](./docs/evaluation.md) | Cases, graders, safety failures, metrics, and reporting. |
| [`docs/decisions.md`](./docs/decisions.md) | Consequential product and technical decisions with reasoning. |
| [`AGENTS.md`](./AGENTS.md) | Working standards for contributors and coding agents. |
| [`frontend/`](./frontend) | React buyer workspace for cases, evidence, decisions, policy checks, approval, actions, and validation. |
| [`backend/`](./backend) | FastAPI API, LangGraph workflow, policy engine, simulator, evaluation runner, seed data, and migrations. |

No undocumented step should be required to run or understand the implemented project.

## Security

Never commit API keys, tokens, passwords, or other secrets. Provider credentials will be loaded from environment variables documented in `.env.example`.
