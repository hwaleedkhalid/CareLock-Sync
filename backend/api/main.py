"""
CareLock Sync - Main FastAPI Application
Fixed: CORS allows port 5173, logger defined before use, auth route added.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import os, sys, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging FIRST before any imports that call logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing modules
try:
    from common.config import settings
    from common.database import get_hospital_db, get_shared_db
    from common.auth import require_auth, AuthContext
    logger.info("Core modules loaded")
except ImportError as e:
    logger.warning(f"Could not import core modules: {e}")
    settings = None

# Import security modules
try:
    from security.production_encryption import (
        ProductionEncryptionManager, SecureTenantKeyManager, TamperResistantAuditLogger
    )
    key_manager = SecureTenantKeyManager()
    audit_logger = TamperResistantAuditLogger('carelock_audit.db')
    logger.info("Security modules loaded")
except ImportError as e:
    logger.warning(f"Security modules not available: {e}")
    key_manager = None
    audit_logger = None

app = FastAPI(
    title="CareLock Sync API",
    description="Secure Healthcare Data Synchronisation — FHIR R4 + AI Mapping",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow all dev origins ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # CRA / alternative
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://carelock.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security headers ─────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ── Core routes ───────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "CareLock Sync API", "version": "1.0.0", "status": "operational",
            "docs": "/docs", "health": "/health"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "version": "1.0.0",
            "components": {"api": "operational", "encryption": "AES-256-GCM", "audit": "enabled"}}

# ── Import and register all route modules ─────────────────────────────────────
# Each router is imported individually so a failure in one module never
# silently prevents other modules from loading.  Errors are fatal — the server
# must not start with missing routes.

def _load_router(import_path: str, label: str):
    """Import a route module; raise with a clear message on failure."""
    try:
        import importlib
        mod = importlib.import_module(import_path)
        logger.info(f"  ✓ {label}")
        return mod
    except Exception as exc:
        logger.error(f"  ✗ FAILED to load {label}: {exc}")
        raise RuntimeError(
            f"Route module '{import_path}' failed to import: {exc}\n"
            "Fix the error above and restart the server."
        ) from exc

logger.info("Loading route modules…")

# Auth — owns its own prefix /api/v1/auth
_auth   = _load_router("api.routes.auth",            "auth")
app.include_router(_auth.router)

# Core API routes — each has its own prefix defined inside the module
_fhir   = _load_router("api.routes.fhir_routes",     "fhir_routes   (prefix: /api/v1)")
_dash   = _load_router("api.routes.dashboard_routes","dashboard_routes (prefix: /api/v1)")
_sync   = _load_router("api.routes.sync",            "sync          (prefix: /api/v1/sync)")
_conn   = _load_router("api.routes.connector",       "connector     (prefix: /api/v1/connector)")
_status = _load_router("api.routes.status",          "status        (prefix: /api/v1/status)")
_rag    = _load_router("api.routes.rag",             "rag           (prefix: /api/v1/rag)")
_pat    = _load_router("api.routes.patients",        "patients      (prefix: /api/v1/patients)")

app.include_router(_fhir.router)
app.include_router(_dash.router)
app.include_router(_sync.router)
app.include_router(_conn.router)
app.include_router(_status.router)
app.include_router(_rag.router)
app.include_router(_pat.router, prefix="/api/v1/patients", tags=["Patients"])

logger.info("All route modules loaded successfully")

# ── Error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": exc.detail, "status_code": exc.status_code,
                                 "timestamp": datetime.utcnow().isoformat()})

@app.exception_handler(Exception)
async def general_error(request: Request, exc: Exception):
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500,
                        content={"error": "Internal server error", "status_code": 500,
                                 "timestamp": datetime.utcnow().isoformat()})

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("  CareLock Sync API  v1.0.0  starting...")
    logger.info("  Frontend: http://localhost:5173")
    logger.info("  API Docs: http://localhost:8003/docs")
    logger.info("=" * 60)

    # ── Startup route audit ────────────────────────────────────────────────
    # Log every registered GET/POST route so misconfiguration is immediately
    # visible in the startup output without needing a live request.
    from fastapi.routing import APIRoute
    api_routes = sorted(
        {r.path for r in app.routes if isinstance(r, APIRoute)},
    )
    logger.info(f"  Registered API routes ({len(api_routes)} total):")
    for path in api_routes:
        logger.info(f"    {path}")
    logger.info("=" * 60)

    # ── Critical-route assertions (fail loud, fail early) ─────────────────
    REQUIRED_ROUTES = {
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/stats",
        "/api/v1/tenants",
        "/api/v1/sync/status",
        "/api/v1/sync/history",
        "/health",
    }
    missing = REQUIRED_ROUTES - set(api_routes)
    if missing:
        logger.error("STARTUP FAILURE — required routes not registered:")
        for r in sorted(missing):
            logger.error(f"  MISSING: {r}")
        raise RuntimeError(f"Critical routes missing: {missing}")
    if audit_logger:
        try:
            is_valid, _ = audit_logger.verify_integrity()
            logger.info(f"Audit log integrity: {'OK' if is_valid else 'TAMPERED'}")
        except Exception:
            pass

    # CDC pipeline runs OUT-OF-PROCESS now — see backend/services/{cdc_worker,
    # ingestion, etl_worker}. The API server is READ + CONTROL only and no
    # longer installs triggers or schedules sync runs in this process.
    # Run `python -m services.cdc_worker --source <id> --setup` once per
    # source DB to install triggers, then start the long-running services.

    # ── Kick off RAG engine initialization in a background thread ─────────
    # Ollama warm-up + Chroma load can take several seconds. Eager-start here
    # so /api/v1/rag/status returns {state:'initializing'} (not 503) during the
    # warm-up window.
    try:
        from api.routes.rag import start_background_init as _rag_init
        _rag_init()
        logger.info("RAG engine warm-up kicked off (non-blocking)")
    except Exception as exc:
        logger.warning(f"RAG warm-up skipped: {exc}")

@app.on_event("shutdown")
async def shutdown():
    logger.info("API shutdown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True, log_level="info")
