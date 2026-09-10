# NeoLearn Backend — README

## Architecture

```
Frontend (React/Vite → Vercel)
        │  JWT from Supabase Auth
        ▼
FastAPI Backend (Cloud Run / localhost:8080)
        │
        ├── POST /api/v1/quiz/generate     → IRT adaptive question generation
        ├── POST /api/v1/quiz/evaluate     → Answer eval + mastery update
        ├── POST /api/v1/chat              → Streaming AI Tutor (SSE)
        └── GET  /api/v1/analytics/insights → Learning analytics
        │
        ▼
Supabase (Postgres + RLS + Auth)
```

## Learning session (LangGraph)

The tutor → judge → quiz flow is a LangGraph `StateGraph` (`app/graph/`) with a Postgres checkpointer:

```
START → init → await_student ⇄ tutor_reply
                    │ evaluate (≥3 student turns)
                    ▼
                  judge → quiz_generate → await_answer → grade_answer ─(index<5)─┐
                              ▲                                                  │
                              └──────────────────────────────────────────────────┘
                                                             (index==5) → finish → END
```

- `await_student` / `await_answer` call `interrupt()`: the graph checkpoints and the API returns what the client needs. The client resumes with the student's message or answer. With `SUPABASE_DB_URL` set, a session survives refreshes, redeploys and cold starts.
- Generated questions live in graph state **with** their answer key; the API serialises them through `public_question()` which strips `correct_answer`. The key is revealed only inside the graded result. The quiz is no longer gameable from the browser.
- Tutor tokens stream out of the graph with `stream_mode="messages"`; the SSE endpoint forwards them.
- Thread id is `<user_id>:<session_id>`, built from the authenticated user, so sessions are user-scoped by construction.
- If a node fails (model outage), the checkpoint stays before that node; the API reports `pending_step` and `/continue` (or retrying the same call) resumes from there.

## Key Technical Features

- **IRT (Item Response Theory)** — Rasch (1PL) item model for adaptive difficulty selection, with a Bayesian EAP ability update after each answer. The response function accepts a discrimination parameter so per-item 2PL calibration can be added later.
- **Structured LLM outputs** — every non-streaming LLM call is bound to a Pydantic schema via LangChain `with_structured_output` (Groq tool calling); invalid output is retried once with a repair hint, then surfaced as HTTP 503 rather than a fabricated score
- **Streaming LLM responses** — Server-Sent Events via Groq streaming API
- **Background tasks** — DB writes run async via FastAPI `BackgroundTasks`
- **JWT middleware** — validates Supabase tokens on every protected route
- **Rate limiting** — per-IP via SlowAPI
- **Structured logging** — structlog with ISO timestamps
- **Multi-stage Docker build** — lean runtime image, non-root user

## Local Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in GROQ_API_KEY, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET

uvicorn app.main:app --reload --port 8080
```

Visit: http://localhost:8080/docs

## Environment Variables

| Variable | Where to find |
|---|---|
| `GROQ_API_KEY` | console.groq.com |
| `SUPABASE_URL` | Supabase project → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase project → Settings → API → service_role key |
| `SUPABASE_JWT_SECRET` | Supabase project → Settings → API → JWT Secret |
| `SUPABASE_DB_URL` | Postgres connection string for the LangGraph checkpointer (Settings → Database → Connection string, URI). Use the direct connection or the **session** pooler on port 5432, not the transaction pooler (6543). Optional: without it sessions are checkpointed in memory and lost on restart. |

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check |
| POST | `/api/v1/session/start` | JWT | Start a learning session (tutor → judge → quiz) on the server |
| GET | `/api/v1/session/{id}` | JWT | Current session view (resume after refresh) |
| POST | `/api/v1/session/{id}/message` | JWT | One Socratic turn, streamed as SSE |
| POST | `/api/v1/session/{id}/evaluate` | JWT | LLM-as-Judge over the transcript; returns verdict + first question |
| POST | `/api/v1/session/{id}/answer` | JWT | Grade against the server-held key; returns result + next question |
| POST | `/api/v1/session/{id}/continue` | JWT | Finish a step that failed mid-way (model outage) |
| POST | `/api/v1/quiz/generate` | JWT | *Legacy*, client-driven quiz; removed next release |
| POST | `/api/v1/quiz/evaluate` | JWT | *Legacy* |
| POST | `/api/v1/chat` | JWT | *Legacy* streaming tutor |
| POST | `/api/v1/chat/evaluate` | JWT | *Legacy* judge |
| GET | `/api/v1/analytics/insights` | JWT | Learning analytics |

## Tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
```

The suite needs no credentials: `tests/conftest.py` sets fake environment
variables and every external dependency (Groq, Supabase, Redis) is replaced
with an in-process fake. Coverage today:

| Area | What is verified |
|---|---|
| `mastery_service` | Item response function, band selection, mastery⇄θ mapping, EAP update direction/bounds/surprise-scaling, and a test proving the legacy Newton step was always clipped to ±0.5 |
| `ai_schemas` / `ai_service` | Schema validation rules, one repair retry with the validation error appended, `AIServiceError` after repeated failure, exact-match short circuit |
| `security` | HS256 with raw and base64 secrets, ES256 via (faked) JWKS, expiry, wrong key, missing `sub` |
| routes | `/quiz/generate`, `/quiz/evaluate`, `/chat/evaluate` happy paths, 503 on model failure, background persistence calls, auth required |
| session graph | Interrupt payloads, turn accounting, evaluate guard, judge → quiz transition, answer key never in an interrupt payload, five-answer completion with θ movement, failure leaves the graph parked before the failed node, resume across a new graph instance on the same checkpointer, thread isolation |
| session routes | Start/get/ownership (404 for another user), SSE token stream + done event, 400 too early, 409 wrong phase, 503 then retry, full quiz over HTTP, `pending_step` + `/continue` recovery, auth required |

CI runs the same two commands on every push/PR touching `backend/` (`.github/workflows/backend-ci.yml`).

## Known limitations (next up)

- Two concurrent resumes of the same session are not serialised; the second will act on stale state. Fix: a per-thread lock (Redis) or optimistic check on checkpoint id.
- Legacy `/chat` and `/quiz/*` routes duplicate the session flow and should be removed once the frontend release is out.

- Rate limiting is per-process and per-IP; the `REDIS_URL` storage is configured on the app limiter but the routers use their own in-memory limiters. Fix: one shared limiter keyed by JWT `sub`.
- Retrieval is a deterministic `ILIKE` on topic title. Fix: pgvector similarity search over mentor primary sources on top of the curriculum row.
- The Supabase client is synchronous and blocks the event loop under load.
