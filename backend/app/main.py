from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import analytics, chat, personas, quiz, session
from app.core.config import settings
from app.graph.graph import build_graph

# ─── Structured Logging ───────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL if settings.REDIS_URL else "memory://"
)

# ─── App ──────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Build the LangGraph session graph once per process.

    With SUPABASE_DB_URL set, checkpoints live in Postgres (tables are created
    on first start by saver.setup()) and sessions survive restarts. Without it
    we fall back to an in-memory saver, which is fine for local development
    and tests but loses every session on restart.
    """
    if settings.SUPABASE_DB_URL:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(settings.SUPABASE_DB_URL) as saver:
            await saver.setup()
            app.state.session_graph = build_graph(saver)
            log.info("session_graph_ready", checkpointer="postgres")
            yield
    else:
        from langgraph.checkpoint.memory import InMemorySaver

        app.state.session_graph = build_graph(InMemorySaver())
        log.warning("session_graph_ready", checkpointer="memory", note="SUPABASE_DB_URL unset; sessions are lost on restart")
        yield


app = FastAPI(
    title="NeoLearn API",
    lifespan=lifespan,
    description=(
        "Adaptive learning backend powering NeoLearn. "
        "Features: Socratic AI tutoring with historical mentor personas (RAG-grounded via LangChain), "
        "LLM-as-Judge mastery evaluation, IRT-based adaptive quiz generation, "
        "and personalized learning analytics."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow origins from settings + allow any localhost port for seamless dev
origins = set(settings.origins + [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Logging Middleware ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Pass OPTIONS preflight requests directly to avoid interfering with CORS
    if request.method == "OPTIONS":
        return await call_next(request)
    log.info("request", method=request.method, path=request.url.path)
    response = await call_next(request)
    log.info("response", status=response.status_code, path=request.url.path)
    return response


# ─── Routers ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(quiz.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(personas.router, prefix=API_PREFIX)
app.include_router(session.router, prefix=API_PREFIX)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint for Cloud Run / load balancers."""
    return {"status": "ok", "service": "neolearn-api", "version": "2.0.0"}


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "NeoLearn API",
        "docs": "/docs",
        "health": "/health",
        "version": "2.0.0",
    }
