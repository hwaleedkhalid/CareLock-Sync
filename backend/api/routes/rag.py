"""
RAG API Routes - Sprint 4 v2
Dual-model: llama3.2:3b for mapping, phi3 for chatbot.
Full verification workflow: suggest -> review -> confirm-batch.

Readiness model
---------------
RAG init (Ollama warm-up + Chroma load) can take several seconds. Initializing
lazily inside request handlers makes the first page-open return 503 because the
frontend fans out /status + /knowledge/stats before the engine exists.

Instead:
  * `start_background_init()` is called from the FastAPI startup event and
    constructs the MappingSuggester in a daemon thread so startup stays fast.
  * A `threading.Lock` makes state transitions and the build call atomic — two
    concurrent requests can never both construct a MappingSuggester.
  * `/status` always returns 200 with a structured `state` field
    (uninitialized | initializing | ready | error) so the frontend can
    distinguish "still warming up" from "truly broken".
  * Other endpoints return 503 only when the engine is in `error` state or
    still `initializing` after a short grace window.
"""
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.auth import AuthContext, require_admin, require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rag", tags=["RAG Mapping"])

# ─────────────────────────────────────────────────────────────────────────────
# Readiness state — all access goes through `_state_lock`
# ─────────────────────────────────────────────────────────────────────────────
_STATE_UNINITIALIZED = "uninitialized"
_STATE_INITIALIZING  = "initializing"
_STATE_READY         = "ready"
_STATE_ERROR         = "error"

_state_lock = threading.Lock()
_suggester: Optional[Any] = None            # MappingSuggester instance when ready
_state: str = _STATE_UNINITIALIZED
_error: Optional[str] = None
_started_at: float = 0.0
_completed_at: float = 0.0
_ERROR_RETRY_COOLDOWN_S = 30                # after error, wait before auto-retry


def _build_suggester():
    """Construct the MappingSuggester. Called from inside the init thread only."""
    from rag.mapping_suggester import MappingSuggester
    return MappingSuggester(
        mapping_model=os.getenv("MAPPING_MODEL", "llama3.2:3b"),
        chat_model=os.getenv("CHAT_MODEL", "phi3"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        vector_store_path=os.getenv("CHROMA_PATH", "./databases/chroma"),
    )


def _run_init() -> None:
    """Body of the background init thread. Guarded by _state transitions."""
    global _suggester, _state, _error, _completed_at
    logger.info("RAG init: starting background initialization")
    try:
        s = _build_suggester()
        with _state_lock:
            _suggester = s
            _state = _STATE_READY
            _error = None
            _completed_at = time.time()
        logger.info(f"RAG init: ready (elapsed={_completed_at - _started_at:.1f}s)")
    except Exception as exc:
        with _state_lock:
            _state = _STATE_ERROR
            _error = str(exc)
            _completed_at = time.time()
        logger.exception("RAG init: failed")


def start_background_init() -> None:
    """
    Kick off RAG initialization in a daemon thread. Idempotent — safe to call
    from the FastAPI startup event and also from request handlers if the state
    is still uninitialized (or after the error cooldown).
    """
    global _state, _started_at
    with _state_lock:
        if _state in (_STATE_INITIALIZING, _STATE_READY):
            return
        if _state == _STATE_ERROR and (time.time() - _completed_at) < _ERROR_RETRY_COOLDOWN_S:
            return
        _state = _STATE_INITIALIZING
        _started_at = time.time()

    threading.Thread(target=_run_init, name="rag-init", daemon=True).start()


def _snapshot() -> Dict[str, Any]:
    """Atomic read of the readiness state for status responses."""
    with _state_lock:
        return {
            "state":         _state,
            "error":         _error,
            "started_at":    _started_at,
            "completed_at":  _completed_at,
            "has_suggester": _suggester is not None,
        }


def _require_ready():
    """
    Return the suggester, or raise an HTTPException with a meaningful state
    code. Called by non-status endpoints that need a live engine.
    """
    with _state_lock:
        state = _state
        suggester = _suggester
        err = _error

    if state == _STATE_READY and suggester is not None:
        return suggester
    if state == _STATE_INITIALIZING:
        raise HTTPException(503, detail={"state": "initializing",
                                         "message": "RAG engine is still warming up — retry shortly."})
    if state == _STATE_ERROR:
        raise HTTPException(503, detail={"state": "error",
                                         "message": f"RAG unavailable: {err}",
                                         "hint": "Run: ollama serve && ollama pull llama3.2:3b"})
    # Uninitialized — something skipped the startup hook. Kick it off so the
    # next request has a chance.
    start_background_init()
    raise HTTPException(503, detail={"state": "initializing",
                                     "message": "RAG engine is initializing — retry shortly."})


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────
class FieldReq(BaseModel):
    field_name: str = Field(..., example="date_of_birth")
    field_type: str = Field("varchar", example="date")
    sample_values: Optional[List] = None
    fhir_resource: str = Field("Patient")


class ColDef(BaseModel):
    name: str
    type: str = "varchar"
    sample_values: Optional[List] = None

class SchemaReq(BaseModel):
    table_name: str
    columns: List[ColDef]
    fhir_resource: str = "Patient"

class ConfirmBatchReq(BaseModel):
    mappings: List[Dict[str, Any]] = Field(
        ..., description="The mappings array from /suggest/schema")
    confirmed_fields: List[str] = Field(
        ..., description="source_field names the user approved")

class SingleConfirmReq(BaseModel):
    source_field: str
    source_type: str = "varchar"
    target_path: str
    fhir_resource: str = "Patient"
    transformation: str = "none"
    confidence: float = 1.0

class ChatReq(BaseModel):
    question: str = Field(..., example="What FHIR path maps to date of birth?")
    context: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/status")
async def status(auth: AuthContext = Depends(require_auth)):
    """
    Structured readiness response — always returns 200 so the frontend can
    distinguish 'warming up' from 'broken' without parsing HTTP codes.
    """
    snap = _snapshot()
    now = time.time()
    elapsed = round(now - snap["started_at"], 1) if snap["started_at"] else None

    base = {
        "state":      snap["state"],
        "checked_at": datetime.utcnow().isoformat(),
    }

    if snap["state"] == _STATE_READY:
        with _state_lock:
            s = _suggester
        st = s.get_stats() if s else {}
        return {
            **base,
            "status":            "operational",
            "mapping_model":     st.get("mapping_model"),
            "chat_model":        st.get("chat_model"),
            "mapping_available": st.get("mapping_available"),
            "total_mappings":    st.get("total_mappings"),
            "architecture":      "dual-model: llama3.2:3b for mapping, phi3 for chat",
            "elapsed_init_s":    round(snap["completed_at"] - snap["started_at"], 1)
                                   if snap["completed_at"] else None,
        }

    if snap["state"] == _STATE_INITIALIZING:
        return {**base, "status": "initializing", "elapsed_s": elapsed}

    if snap["state"] == _STATE_ERROR:
        return {**base, "status": "error", "error": snap["error"]}

    # Uninitialized — kick off init so a follow-up poll finds it warming.
    start_background_init()
    return {**base, "status": "initializing", "elapsed_s": 0.0}


@router.post("/suggest/field")
async def suggest_field(req: FieldReq, auth: AuthContext = Depends(require_auth)):
    """Suggest FHIR mapping for one field. Returns status=pending_review."""
    s = _require_ready()
    r = s.suggest_mapping(req.field_name, req.field_type,
                          req.sample_values, req.fhir_resource)
    return {
        "field": req.field_name,
        "fhir_resource": req.fhir_resource,
        "suggestion": r,
        "similar_count": len(r.get("similar_mappings", [])),
        "note": "Call POST /mappings/confirm to save after review.",
        "suggested_at": datetime.utcnow().isoformat(),
    }


@router.post("/suggest/schema")
async def suggest_schema(req: SchemaReq, auth: AuthContext = Depends(require_auth)):
    """
    STEP 1 of verification workflow.
    Returns all suggestions with status=pending_review.
    Nothing is saved until POST /mappings/confirm-batch.
    """
    s = _require_ready()
    result = s.suggest_schema_mapping(
        {"table_name": req.table_name,
         "columns": [c.dict() for c in req.columns]},
        req.fhir_resource,
    )
    return {
        **result,
        "workflow": {
            "step": "1/2 - suggestions ready for review",
            "next": "POST /api/v1/rag/mappings/confirm-batch with confirmed_fields list",
        },
        "suggested_at": datetime.utcnow().isoformat(),
    }


@router.post("/mappings/confirm-batch")
async def confirm_batch(req: ConfirmBatchReq, auth: AuthContext = Depends(require_admin)):
    """
    STEP 2 of verification workflow (admin only).
    Saves only the fields listed in confirmed_fields.
    Everything else is skipped.
    """
    s = _require_ready()
    result = s.confirm_mappings(req.mappings, req.confirmed_fields)
    return {
        "status": "ok",
        "saved": result["saved"],
        "skipped": result["skipped"],
        "total_saved": result["total_saved"],
        "message": f"Saved {result['total_saved']} mappings. Skipped {len(result['skipped'])}.",
        "confirmed_at": datetime.utcnow().isoformat(),
    }


@router.post("/mappings/confirm")
async def confirm_single(req: SingleConfirmReq, auth: AuthContext = Depends(require_admin)):
    """Save a single manually-specified mapping (admin only)."""
    s = _require_ready()
    s.save_confirmed_mapping(req.source_field, req.source_type, req.target_path,
                              req.fhir_resource, req.transformation, req.confidence)
    return {"status": "saved", "mapping": req.dict(),
            "saved_at": datetime.utcnow().isoformat()}


@router.post("/chat")
async def chat(req: ChatReq, auth: AuthContext = Depends(require_auth)):
    """FHIR RAG chatbot using phi3. Ask anything about FHIR mappings."""
    s = _require_ready()
    answer = s.chat(req.question, req.context)
    return {"question": req.question, "answer": answer,
            "model": s._chat_model,
            "answered_at": datetime.utcnow().isoformat()}


@router.get("/knowledge/stats")
async def knowledge_stats(auth: AuthContext = Depends(require_auth)):
    """
    Returns {state: 'initializing'} with 200 instead of 503 while warming up,
    so the frontend banner stops flashing "backend unreachable" on page load.
    """
    snap = _snapshot()
    if snap["state"] != _STATE_READY:
        return {
            "state": snap["state"],
            "error": snap["error"],
            "message": "RAG knowledge base is not ready yet.",
        }

    with _state_lock:
        s = _suggester
    from rag.fhir_knowledge import get_all_mappings
    st = s.get_stats()
    return {
        "state": _STATE_READY,
        "mapping_model": st["mapping_model"],
        "chat_model": st["chat_model"],
        "vector_store_mappings": st["total_mappings"],
        "knowledge_base_entries": len(get_all_mappings()),
        "resources_covered": ["Patient", "Encounter", "Observation", "MedicationRequest"],
    }
