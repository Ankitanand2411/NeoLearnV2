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
        ├── POST /api/v1/content/generate  → Educational content generation
        └── GET  /api/v1/analytics/insights → Learning analytics
        │
        ▼
Supabase (Postgres + RLS + Auth)
```

## Key Technical Features

- **IRT (Item Response Theory)** — 2PL model for adaptive difficulty selection (same model used in GRE/CAT)
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
| POST | `/api/v1/content/generate` | JWT | Educational content |
| GET | `/api/v1/analytics/insights` | JWT | Learning analytics |
