import logging
import sys
from contextlib import asynccontextmanager

# Allow running "uvicorn main:app" directly from the backend/ directory by
# ensuring the project root is importable (code uses "backend.*" imports).
import os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from backend.config import settings
from backend.db import init_db, engine
from backend.security import SecurityHeadersMiddleware, limiter, redact_secrets
from backend.routes.auth_routes import router as auth_router
from backend.routes.agent_routes import router as agent_router
from backend.routes.analytics_routes import router as analytics_router
from backend.routes.github_routes import router as github_router
from sqlmodel import Session, select, text

# Configure root logger
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forge.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Forge backend database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Forge backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# SlowAPI Rate Limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Security Headers Middleware (always before other custom middlewares)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS Middleware
_candidate_origins = [
    settings.ALLOWED_ORIGIN,
    getattr(settings, "ALLOWED_ORIGINS", ""),
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://forge-phi-navy.vercel.app",
]
resolved_origins: list[str] = []
for entry in _candidate_origins:
    if entry:
        for origin in str(entry).split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in resolved_origins:
                resolved_origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=resolved_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Global Exception Handler — safety net ensuring clean JSON responses and secret redaction
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing request {request.url.path}: {exc}")
    safe_message = redact_secrets(str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. It has been logged securely.",
            "message": safe_message if settings.DEBUG else "Operation failed.",
        },
    )


# --- Probes & Health Checks ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe for Render / container orchestrator."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe checking database connectivity (Supabase Postgres or SQLite)."""
    try:
        from backend.db import get_db_type
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "database_type": get_db_type(),
            "docker_sandbox": settings.ENABLE_DOCKER_SANDBOX,
            "provider_chain": settings.LLM_PROVIDER_CHAIN,
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "error": str(e)},
        )


# Include Routers
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(analytics_router)
app.include_router(github_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
