# HelpBot — Agentic RAG Assistant for Internal Helpdesk

A 3-agent LangGraph system (Router / RAG-Knowledge / Ticket) fronting a fictional company's
("Nimbus Corp") helpdesk: it classifies employee queries, answers self-serve questions from
policy docs with citations, raises tickets for genuine issues, and looks up/acts on existing
tickets — with a hard guardrail that refuses to auto-handle HR grievance/harassment queries.

- Design docs: [`docs/HLD.md`](docs/HLD.md), [`docs/LLD.md`](docs/LLD.md),
  [`docs/architecture.mmd`](docs/architecture.mmd) (Mermaid — paste into
  [mermaid.live](https://mermaid.live) or view directly on GitHub)
- Write-up: [`docs/writeup.md`](docs/writeup.md)
- Baseline eval queries: [`eval/test-queries.md`](eval/test-queries.md)

## Repo layout

```
backend/            FastAPI app + LangGraph agents (Python)
  app/agents/        router_agent.py, rag_agent.py, ticket_agent.py
  app/tools/         ticket_tools.py (SQLite CRUD), retrieval.py (KB loader)
  app/data/          docs/*.md, tickets.json (content pack, seeds the DB)
frontend/           React (Vite) chat UI
docs/               HLD, LLD, architecture diagram, write-up
eval/               baseline test queries from the content pack
docker-compose.yml  runs backend + frontend together
```

## 1. Local setup (no Docker)

### Prerequisites
- Python 3.11+
- Node.js 20+
- A free Groq API key: https://console.groq.com/keys

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

The SQLite ticket DB (`app/data/tickets.db`) is created and seeded from `tickets.json`
automatically on first startup. Verify it's up: `curl http://localhost:8000/health`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000 by default
npm run dev
```

Open the printed local URL (default `http://localhost:5173`).

## 2. Local setup with Docker Compose

```bash
cp backend/.env.example backend/.env   # add your GROQ_API_KEY
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:80`

## 3. Sanity-checking against the baseline queries

With the backend running:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "How often do I need to reset my password?"}'
```

Run through the queries in `eval/test-queries.md` this way, or just use them as the chat
suggestion chips in the frontend.

## 3b. Automated baseline check

Once the backend is running (locally or deployed) with a real `GROQ_API_KEY` set, run every
query from `eval/test-queries.md` against it in one shot:

```bash
cd backend
python scripts/run_eval.py --url http://localhost:8000
```

This isn't automated grading (there's no ground-truth checker) — it just prints each query's
`intent`, `handled_by`, final answer, and citations so you can eyeball them against the
expectations in `eval/test-queries.md` before submitting.

## 4. Deploying to AWS (Free Tier)

This targets a single **EC2 t2.micro / t3.micro** instance (Free Tier eligible), running both
containers via Docker Compose — no ALB, no auto-scaling group, no managed DB, so nothing here
should incur cost beyond the Free Tier allowance.

1. **Launch the instance**
   - AMI: Ubuntu 24.04 LTS (or Amazon Linux 2023), instance type `t3.micro` (or `t2.micro` for
     the older Free Tier terms).
   - Security group: allow inbound `22` (SSH, your IP only), `80` (HTTP, frontend), `8000`
     (backend API — or proxy it through the frontend's nginx instead, see step 5).
   - Attach/allocate an Elastic IP if you want a stable URL (still Free Tier while attached to a
     running instance).

2. **Install Docker**
   ```bash
   ssh ubuntu@<ec2-public-ip>
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && newgrp docker
   sudo apt-get install -y docker-compose-plugin
   ```

3. **Get the code onto the instance**
   ```bash
   git clone <your-github-repo-url> helpbot
   cd helpbot
   cp backend/.env.example backend/.env
   nano backend/.env   # paste your GROQ_API_KEY
   ```

4. **Point the frontend build at the public backend URL**
   ```bash
   export VITE_API_URL=http://<ec2-public-ip>:8000
   docker compose up --build -d
   ```

5. **(Optional, recommended) Serve everything on port 80** — add a reverse-proxy location for
   `/api/` in `frontend/nginx.conf` pointing at `http://backend:8000/`, rebuild with
   `VITE_API_URL=http://<ec2-public-ip>/api`, and close inbound port 8000 in the security
   group. This avoids exposing the API on a second port.

6. **Verify**
   ```bash
   curl http://<ec2-public-ip>:8000/health
   ```
   Then open `http://<ec2-public-ip>` in a browser for the chat UI.

Cost-safety notes: only Free-Tier-eligible resources are used (a single `t2/t3.micro`, no
managed RDS/OpenSearch, no NAT gateway, no load balancer); SQLite lives on the instance's own
EBS volume (within the Free Tier's 30 GB allowance).

## 5. Environment variables reference

**`backend/.env`**

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Only provider wired up; structured to add others in `app/config.py`. |
| `GROQ_API_KEY` | — | Required. Free tier: https://console.groq.com/keys |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | |
| `LLM_TEMPERATURE` | `0.1` | Low on purpose — classification/extraction, not creative writing. |
| `RAG_CONFIDENCE_THRESHOLD` | `0.55` | Below this, RAG hands back to the router → ticket created. |

**`frontend/.env`**

| Var | Default |
|---|---|
| `VITE_API_URL` | `http://localhost:8000` |

## 6. Known constraints (see `docs/writeup.md` for full detail)

- Each chat request is stateless (no multi-turn memory across separate messages yet).
- No duplicate/similar-ticket detection (explicitly out of scope per the assignment brief).
- No authentication — anyone reaching the deployed URL can raise/escalate/cancel tickets.
