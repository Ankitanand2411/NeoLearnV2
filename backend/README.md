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

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check |
| POST | `/api/v1/quiz/generate` | JWT | Adaptive question (IRT) |
| POST | `/api/v1/quiz/evaluate` | JWT | Evaluate + update mastery |
| POST | `/api/v1/chat` | JWT | Streaming AI tutor (SSE) |
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

CI runs the same two commands on every push/PR touching `backend/` (`.github/workflows/backend-ci.yml`).

## Known limitations (next up)

- Quiz state (correct answer, θ, transcript) still lives in the client, so the quiz is gameable. Fix: server-side session state (`quiz_sessions`) — planned as the LangGraph migration.
- Rate limiting is per-process and per-IP; the `REDIS_URL` storage is configured on the app limiter but the routers use their own in-memory limiters. Fix: one shared limiter keyed by JWT `sub`.
- Retrieval is a deterministic `ILIKE` on topic title. Fix: pgvector similarity search over mentor primary sources on top of the curriculum row.
- The Supabase client is synchronous and blocks the event loop under load.
