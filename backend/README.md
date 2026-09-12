# NeoLearn Backend — README

## Architecture

```
Frontend (React/Vite → Vercel)
        │  JWT from Supabase Auth
        ▼
FastAPI Backend (Cloud Run / localhost:8080)
        │
        ├── POST /api/v1/session/start     → Start a checkpointed learning session
        ├── POST /api/v1/session/{id}/message → Streaming Socratic tutor turn (SSE)
        ├── POST /api/v1/session/{id}/evaluate → LLM-as-Judge + first adaptive question
        ├── POST /api/v1/session/{id}/answer   → Grade against server-held key, IRT update
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
- The mentor's greeting is the first message of the server-side transcript, so the judge grades what the student saw. Completion (progress row, `First Steps` / `Expert` / `Master` badges) is recorded by the `finish` node, idempotently; the client only displays it.
- If a node fails (model outage), the checkpoint stays before that node; the API reports `pending_step` and `/continue` (or retrying the same call) resumes from there.

## Mentor RAG (pgvector)

Two retrieval steps feed every tutor turn:

1. **Curriculum row** (`topics`, deterministic): *what* to teach. Unchanged.
2. **Mentor passages** (`mentor_passages`, semantic): *how this mentor would say it*. Public-domain writings of the mentors are chunked (~300 words, 50 overlap), embedded with Gemini (768 dims) and stored with a `vector(768)` column plus a generated `tsvector`. Per turn, the student's message is embedded and the top-k passages are retrieved with `match_mentor_passages_hybrid`, which fuses cosine rank and full-text rank with Reciprocal Rank Fusion in SQL, then placed in the system prompt with a "quote at most one short phrase, name the source" rule.

Setup:

```bash
# 1. run supabase/migrations/20260910_mentor_passages.sql in the Supabase SQL editor
# 2. set GEMINI_API_KEY, then ingest (dry-run first to see titles + chunk counts)
python scripts/ingest_sources.py --all --dry-run
python scripts/ingest_sources.py --all --yes
# 3. measure
python scripts/eval_retrieval.py --compare          # recall@k and MRR, vector vs hybrid
```

Only mentors with clearly public-domain primary texts are ingested (Darwin, Twain, Nightingale, Einstein's 1916 *Relativity*, Plato's *Apology* for Socrates). Feynman, Turing, Curie, Gandhi and Ramanujan fall back to prompt-only personas. Retrieval fails open: no key, no rows or any error leaves the prompt exactly as before.

The SQL functions were verified against a local Postgres 16 + pgvector 0.6: cosine ordering, per-mentor isolation, RRF promoting a row both signals agree on, and keyword-only hits surfacing outside the vector candidate window.

## Key Technical Features

- **IRT (Item Response Theory)** — Rasch (1PL) item model for adaptive difficulty selection, with a Bayesian EAP ability update after each answer. The response function accepts a discrimination parameter so per-item 2PL calibration can be added later.
- **Structured LLM outputs** — every non-streaming LLM call is bound to a Pydantic schema via LangChain `with_structured_output` (Groq tool calling); invalid output is retried once with a repair hint, then surfaced as HTTP 503 rather than a fabricated score
- **Streaming LLM responses** — Server-Sent Events via Groq streaming API
- **Background tasks** — DB writes run async via FastAPI `BackgroundTasks`
- **JWT middleware** — validates Supabase tokens on every protected route
- **Rate limiting** — per-IP via SlowAPI
- **Structured logging** — structlog with ISO timestamps
- **Multi-stage Docker build** — lean runtime image, non-root user

## Fresh database setup (new Supabase project)

Run these in the Supabase SQL editor, in order; each is safe to re-run:

1. `supabase/schema.sql` — tables (`topics`, `profiles`, `user_progress`, `user_badges`, `user_mastery`, `user_streaks`, `quiz_sessions`), RLS, and the `update_mastery_level` / `update_user_streak` functions.
2. `supabase/migrations/20260725_mentor_topics.sql` — `mentor_id`, `explanation`, `key_takeaway` columns and the seeded topics.
3. `supabase/migrations/20260912_user_memories.sql` — the session-memory table.
4. `supabase/migrations/20260910_mentor_passages.sql` — the retrieval table and search functions (pgvector).

Then create a **public** Storage bucket named `avatars` (profile pictures) and enable the Google provider under Authentication. The LangGraph `checkpoints*` tables are created by the backend itself on first start.

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
| `GROQ_MODEL` | Groq model id, default `llama-3.3-70b-versatile`. Groq retires models; if the tutor logs `model_not_found`, pick a current id from console.groq.com/docs/models |
| `GEMINI_API_KEY` | Google AI Studio key, used only for embeddings (`gemini-embedding-001`). Optional: without it mentor-passage retrieval is skipped. |
| `MENTOR_RAG_MODE` | `hybrid` (default: vector + keyword, RRF-fused), `vector`, or `off` |
| `MENTOR_RAG_TOP_K` | Passages injected per tutor turn (default 3) |
| `LLM_PRICE_INPUT_PER_M` / `LLM_PRICE_OUTPUT_PER_M` | JSON map of model → USD per 1M tokens for cost estimates. Defaults are Groq's list prices for `llama-3.1-8b-instant` at the time of writing; verify against groq.com/pricing. |
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

## Numbers

Every LLM call and HTTP request is measured (`app/services/telemetry.py`):

- **Per session**: `GET /api/v1/session/{id}` includes `usage` — LLM calls, prompt/completion tokens and estimated cost accumulated in graph state, so it survives restarts.
- **Per process**: `GET /api/v1/metrics` (JWT) — by purpose (`tutor`, `llm_judge`, `question_generation`, `answer_evaluation`, `tutor_stream`): count, p50/p95/max latency, tokens, `usage_reported_ratio`, cost; by route: count, p50/p95, 5xx count. In-memory, resets on restart, and says so.
- **Logs**: one `llm_call` line per call (purpose, model, tokens, latency, cost) and `latency_ms` on every `response` line.

How to produce the numbers for this section:

```bash
# 1. complete 5 real sessions in the app, then
curl -H "Authorization: Bearer $JWT" https://<backend>/api/v1/metrics | jq '.llm, .http'
curl -H "Authorization: Bearer $JWT" https://<backend>/api/v1/session/<id> | jq .usage

# 2. throughput / latency of the checkpointed path, no model cost
python scripts/load_test.py --base https://<backend> --token $JWT --users 10 --requests 20

# 3. retrieval quality (after ingesting sources)
python scripts/eval_retrieval.py --compare
```

<!-- Paste results here, e.g.:
| Metric | Value |
|---|---|
| Tokens per completed session (tutor + judge + 5 questions + 5 gradings) | … prompt / … completion |
| Estimated cost per session | $… |
| tutor p95 latency | … ms |
| POST /session/start p95 (10 concurrent users) | … ms |
| mentor RAG recall@3 / MRR (hybrid vs vector) | … |
-->

## Tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
```

The suite needs no credentials: `tests/conftest.py` sets fake environment
variables and every external dependency (Groq, Gemini, Supabase, Postgres) is replaced
with an in-process fake. Coverage today:

| Area | What is verified |
|---|---|
| `mastery_service` | Item response function, band selection, mastery⇄θ mapping, EAP update direction/bounds/surprise-scaling, and a test against a reference copy of the pre-EAP Newton step proving it was always clipped to ±0.5 |
| `ai_schemas` / `ai_service` | Schema validation rules, one repair retry with the validation error appended, `AIServiceError` after repeated failure, exact-match short circuit |
| `security` | HS256 with raw and base64 secrets, ES256 via (faked) JWKS, expiry, wrong key, missing `sub` |
| routes | `/quiz/generate`, `/quiz/evaluate`, `/chat/evaluate` happy paths, 503 on model failure, background persistence calls, auth required |
| session graph | Interrupt payloads, turn accounting, evaluate guard, judge → quiz transition, answer key never in an interrupt payload, five-answer completion with θ movement, failure leaves the graph parked before the failed node, resume across a new graph instance on the same checkpointer, thread isolation |
| `mentor_rag` | Gutenberg boilerplate stripping, chunk size/overlap/coverage, hybrid vs vector RPC selection, fail-open on off/k=0/no mentor/blank query/no key/embedding error/RPC error, prompt block present only with passages and placed before the Socratic rules, tutor messages carry retrieved passages, golden-set recall@k and MRR, migration ⇄ code contract |
| `telemetry` | Nearest-rank percentiles, per-model cost table, usage normalisation, per-purpose and per-route aggregates, per-context capture + drain, state reducer, include_raw unpacking keeps token usage, parsing errors counted as errored attempts |
| session routes | Start/get/ownership (404 for another user), SSE token stream + done event, 400 too early, 409 wrong phase, 503 then retry, full quiz over HTTP, `pending_step` + `/continue` recovery, auth required |

CI runs the same two commands on every push/PR (`.github/workflows/backend-ci.yml`); `frontend-ci.yml` type-checks, lints and builds the frontend. Both are required checks on `main`. Python is pinned to 3.12 via `backend/.python-version` (Render honours it; the Dockerfile pins its own base image).

## Known limitations (next up)

- Mentor RAG retrieves on every tutor turn (one embedding call + one RPC, ~200–400 ms). Fix: cache by (mentor, normalised query) or retrieve every other turn.
- Recall numbers in the README are a TODO until the corpus is ingested: run `scripts/eval_retrieval.py --compare` and paste the output.

- Two concurrent resumes of the same session are not serialised; the second will act on stale state. Fix: a per-thread lock (Redis) or optimistic check on checkpoint id.

- Rate limiting is per-process and per-IP. Fix when running more than one instance: one shared limiter (Redis) keyed by JWT `sub`.
- The `topics` table still has the static-quiz columns `quiz_question`, `quiz_options`, `quiz_correct_answer` and `video_description` from before question generation; nothing reads them. `supabase/migrations/20260911_drop_static_quiz_columns.sql` drops them; it is destructive, so run it deliberately.
- The Supabase client is synchronous and blocks the event loop under load.
