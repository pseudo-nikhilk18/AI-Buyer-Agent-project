# AI Purchasing Agent

A full-stack purchasing agent for a retail or quick-commerce buyer. It investigates current business evidence, challenges a purchase recommendation, takes an authorized action, and verifies the result instead of trusting an acknowledgement.

The source brief is [`AI Buyer Agent project.pdf`](./AI%20Buyer%20Agent%20project.pdf).

## What is implemented

Purchase recommendation review runs end to end:

```text
purchasing situation
  -> AI plans the investigation
  -> typed tools retrieve current evidence
  -> deterministic code calculates safe candidates
  -> AI proposes accept / modify / reject / investigate
  -> an independent guard checks the proposal
  -> the action auto-runs or pauses for the buyer
  -> the system reads the PO back and validates it
```

The opening screen is an evaluation runner with six understandable tests. Each result follows the brief directly: situation, information investigated, agent decision, action taken, and result validation. Technical evidence and the LangGraph trace remain available without dominating the buyer view.

The versioned dataset contains 12 cases. The six UI cases cover accept, modify, reject, stale evidence, buyer approval, and a wrong persisted quantity. The full evaluation also probes supplier shortage, changed demand, insufficient budget, missing evidence, prompt injection, and a different SKU/supplier/node.

## Approach

The AI has two bounded responsibilities: choose the approved evidence sources needed for the purchasing situation, then propose a decision from the retrieved evidence and policy-checked candidates. Its structured tool requests, tool results, proposal, explanation, and reason codes remain visible and auditable.

Deterministic Python owns quantities, hard constraints, authorization, mutations, and result validation. LangGraph coordinates the investigation, one bounded replan, buyer-review pause and resume, action-time evidence check, and escalation path. PostgreSQL stores both business state and the complete workflow record.

The operational feedback loop closes on persisted business state: after an authorized action, the system reads the purchase order from PostgreSQL and compares it with the approved quantity. An exact match completes the run; changed evidence returns to investigation; an incorrect persisted result is escalated and never reported as success. Separately, failed evaluation traces are classified, added to the versioned dataset when they expose a genuine gap, fixed in the responsible layer, and rerun first as a focused live-model case and then through the broader evaluation and safety checks.

## Technology

| Area | Choice |
| --- | --- |
| Web | React JavaScript, Vite, Tailwind CSS |
| API | Python, FastAPI, Pydantic |
| Agent workflow | LangGraph with PostgreSQL checkpoints |
| Models | Configurable Gemini, OpenAI, or Anthropic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| AI evaluation | Dataset-backed configured-model experiments |
| Engineering checks | Separate deterministic safety regression |
| Reviewer setup | Docker Compose |

The LLM chooses evidence and proposes a decision. Ordinary Python controls calculations, constraints, authorization, writes, and read-back validation. Raw model output and the final guarded outcome are stored separately.

## Local setup

Prerequisites: Python 3.13, Node.js 24+, npm, and PostgreSQL 17.

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
# In .env, use the Gemini, OpenAI, or Anthropic block matching your key.
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
python main.py
```

Start the frontend in a second terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. The API is at `http://localhost:8000`; `GET /api/health` checks both API and database connectivity.

## Evaluation

Run one live case first when using a free key:

```bash
cd backend
source .venv/bin/activate
python -m app.live_evaluation --case REC-MODIFY
```

Run the six core cases or all 12 cases:

```bash
python -m app.live_evaluation --suite quick --delay-seconds 15
python -m app.live_evaluation --suite full --delay-seconds 15
```

Measure nondeterministic stability by repeating selected cases:

```bash
python -m app.live_evaluation --case REC-MODIFY --repetitions 3 --delay-seconds 15
```

`--judge` adds an optional explanation-quality rubric using one extra model call per trial. Core correctness never depends on this subjective score. Free-tier quotas may require a larger delay or a smaller selection.

Run the no-key system and safety regression:

```bash
AI_MODE=replay python -m app.system_regression
```

The configured-model evaluation is the AI quality result. One scored Gemini `REC-MODIFY` trial passed trajectory, raw decision, explanation grounding, final outcome, and every hard-safety check; the complete live suite has not yet run. Provider failures are reported separately as target errors rather than incorrect model decisions. Reports are under [`artifacts/evaluations/live/`](./artifacts/evaluations/live). Separately, the deterministic engineering regression passes 13/13 system checks and is stored under [`artifacts/system-regression/`](./artifacts/system-regression). It is never counted as model quality. See [`docs/evaluation.md`](./docs/evaluation.md) for the scoring contract.

An action is successful only when the created purchase order is read from PostgreSQL and matches the authorized quantity. A mismatch is escalated instead of reported as success. Live evaluations independently grade the AI's tool trajectory and raw proposal; the replay regression verifies deterministic policy, concurrency, action, and validation behavior.

## Docker reviewer setup

Docker is optional for local development. For a clean reviewer environment:

```bash
cp backend/.env.example backend/.env
# Add a provider key to backend/.env, then:
docker compose up --build
```

Open `http://localhost:5173`. Compose starts PostgreSQL, applies migrations, seeds the dataset, starts FastAPI, and serves the built React app. To inspect the deterministic workflow without a key, set `AI_MODE=replay` in `backend/.env`; replay is never presented as live AI quality.

## Repository guide

This is the end-to-end index for the product source, setup, architecture, supporting data and services, evaluation evidence, and decision validation.

| Path | Purpose |
| --- | --- |
| [`AI Buyer Agent project.pdf`](./AI%20Buyer%20Agent%20project.pdf) | Original project brief |
| [`docs/prd.md`](./docs/prd.md) | Product behavior and acceptance criteria |
| [`README.md`](./README.md#approach) | Approach, setup, commands, and validation summary |
| [`docs/architecture.md`](./docs/architecture.md) | Components, graph, boundaries, and consistency |
| [`docs/evaluation.md`](./docs/evaluation.md) | Dataset, graders, metrics, and feedback loop |
| [`docs/decisions.md`](./docs/decisions.md) | Consequential decisions and reasoning |
| [`AGENTS.md`](./AGENTS.md) | Contributor working agreement |
| [`backend/evals/purchasing_agent_dataset.json`](./backend/evals/purchasing_agent_dataset.json) | Versioned inputs, evaluator-only references, and test metadata |
| [`backend/app/agent/`](./backend/app/agent) | LangGraph, prompts, provider adapters, routing, and nodes |
| [`backend/app/evals/`](./backend/app/evals) | Dataset validation, modular graders, judge, and reporting |
| [`backend/app/seed.py`](./backend/app/seed.py) and [`backend/app/services/simulator.py`](./backend/app/services/simulator.py) | Supporting purchasing data and simulated action service |
| [`artifacts/evaluations/live/`](./artifacts/evaluations/live) | Configured-model experiment report |
| [`artifacts/system-regression/`](./artifacts/system-regression) | Deterministic workflow and safety report |
| [`compose.yaml`](./compose.yaml) | PostgreSQL, API, and web reviewer environment |
| [`backend/.env.example`](./backend/.env.example) and [`frontend/.env.example`](./frontend/.env.example) | Safe backend provider and frontend API configuration examples |
| [`frontend/src/`](./frontend/src) | Evaluation-first React interface |

No secret belongs in the repository. `.env.example` files contain only safe placeholders.
