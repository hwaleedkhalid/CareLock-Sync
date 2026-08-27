"""
Multi-Database ETL Pipeline
===========================

Adapter-driven ETL that works against ANY database that ships a
``CDCAdapter`` implementation (PostgreSQL, MySQL, MongoDB, Oracle,
SQL Server).  Differs from ``etl/pipeline.py`` in two important ways:

  1. **Source is abstract** — rows are pulled via ``adapter.extract_data``
     (or ``adapter.iter_data``) instead of via a SQLAlchemy ORM model.
     This is the only viable shape for MongoDB documents and for
     Oracle / SQL Server schemas where we have no ORM mapping.

  2. **Target stays the same** — transformed FHIR resources are written
     to the canonical ``fhir_*`` tables in the central PostgreSQL
     database, exactly as ``etl/pipeline.py`` does.  The legacy PG full
     sync is therefore unaffected: when the source is PostgreSQL with
     a complete ORM mapping, callers should keep using
     ``etl.pipeline.ETLPipeline``.

Usage
-----
    from cdc.adapter_factory import CDCAdapterFactory
    from etl.multi_db_pipeline import MultiDBPipeline

    adapter = CDCAdapterFactory.create_adapter(
        "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql"
    )
    pipeline = MultiDBPipeline(adapter, tenant_id=2)
    stats = pipeline.sync_all(limit=50)
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text

# ── path bootstrap ──────────────────────────────────────────────────────────
_THIS = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_THIS)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
_SCHEMA = os.path.join(_BACKEND, "schema_mapper")
if _SCHEMA not in sys.path:
    sys.path.insert(0, _SCHEMA)

from cdc.base_adapter import CDCAdapter        # noqa: E402
from common.database import shared_db_session  # noqa: E402

logger = logging.getLogger(__name__)


# Per-resource (source-table, transformer-name, target-loader-name) routing.
# The transformer is resolved against MappingService at runtime.
DEFAULT_RESOURCE_PLAN = [
    {"resource": "patients",     "source": "patients",
     "transform": "map_dict_to_fhir_patient"},
    {"resource": "encounters",   "source": "encounters",
     "transform": "map_dict_to_fhir_encounter"},
    {"resource": "observations", "source": "lab_results",
     "transform": "map_dict_to_fhir_observation"},
    {"resource": "medications",  "source": "medications",
     "transform": "map_dict_to_fhir_medication"},
]


class MultiDBPipeline:
    """ETL pipeline that drives extraction from any ``CDCAdapter``."""

    def __init__(
        self,
        adapter: CDCAdapter,
        tenant_id: int = 1,
        progress_cb: Optional[Callable[[str, int, Dict[str, int]], None]] = None,
        resource_plan: Optional[List[Dict[str, str]]] = None,
    ):
        self.adapter = adapter
        self.tenant_id = tenant_id
        self.progress_cb = progress_cb
        self.plan = resource_plan or DEFAULT_RESOURCE_PLAN
        self.stats: Dict[str, Dict[str, int]] = {
            r["resource"]: {"extracted": 0, "transformed": 0,
                             "loaded": 0, "errors": 0}
            for r in self.plan
        }
        self._mapper = self._build_mapper()

    # ── internals ────────────────────────────────────────────────────────────
    def _build_mapper(self):
        """Lazy-import MappingService so import-time deps stay light."""
        try:
            from mapping_service import MappingService  # noqa
            return MappingService()
        except Exception as exc:
            logger.warning("MappingService unavailable: %s — using passthrough", exc)
            return None

    def _emit(self, step: str, progress: int) -> None:
        if self.progress_cb is None:
            return
        try:
            self.progress_cb(step, progress, {
                k: v.get("loaded", 0) for k, v in self.stats.items()
            })
        except Exception as exc:
            logger.warning("progress_cb raised: %s", exc)

    def _set_tenant_context(self, sdb) -> None:
        sdb.execute(text("SET app.tenant_id = :tid"),
                    {"tid": str(self.tenant_id)})

    # ── transform routing ────────────────────────────────────────────────────
    def _transform(self, transform_name: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a source-row dict through a named MappingService method.

        We use *_dict_to_fhir_* variants which accept a plain dict (vs the
        legacy ORM-model variants in MappingService).  If the variant is
        missing we fall back to MappingConfig + FHIRMapper directly.
        """
        if self._mapper and hasattr(self._mapper, transform_name):
            return getattr(self._mapper, transform_name)(row)

        # Fallback: pull mapping config and apply FHIRMapper inline.
        try:
            from mapping_config import MappingConfig
            from data_transformer import FHIRMapper
        except Exception as exc:
            raise RuntimeError(f"FHIRMapper unavailable: {exc}") from exc

        # transform_name like "map_dict_to_fhir_patient" → mapping_key
        # Mapping keys exposed by MappingConfig: patient, encounter,
        # observation, medication_request.
        suffix = transform_name.replace("map_dict_to_fhir_", "")
        mapping_key = {
            "patient":     "patient",
            "patients":    "patient",
            "encounter":   "encounter",
            "encounters":  "encounter",
            "observation": "observation",
            "observations":"observation",
            "medication":  "medication_request",
            "medications": "medication_request",
        }.get(suffix, suffix)
        mappings = MappingConfig.get_all_mappings()
        if mapping_key not in mappings:
            return {"_unmapped": True, **row}
        return FHIRMapper(mappings[mapping_key]).map_record(row)

    # ── per-resource sync ────────────────────────────────────────────────────
    def _sync_resource(self, item: Dict[str, str],
                       limit: Optional[int]) -> Dict[str, int]:
        resource  = item["resource"]
        source    = item["source"]
        transform = item["transform"]
        s = self.stats[resource]

        logger.info("─── %s  src=%s  tenant=%s ───",
                    resource, source, self.tenant_id)

        # 1. Extract
        try:
            rows = self.adapter.extract_data(source, limit=limit)
        except Exception as exc:
            logger.warning("extract failed for %s: %s", source, exc)
            return s
        s["extracted"] = len(rows)
        logger.info("  extracted=%d", len(rows))

        # 2. Transform
        fhir_rows: List[Dict[str, Any]] = []
        for r in rows:
            try:
                fhir_rows.append(self._transform(transform, r))
                s["transformed"] += 1
            except Exception as exc:
                logger.warning("transform error on row: %s", exc)
                s["errors"] += 1
        logger.info("  transformed=%d", len(fhir_rows))

        # 3. Load — into central FHIR DB.  We keep this best-effort: many
        # mapped rows will satisfy the canonical loaders, but unmapped /
        # passthrough rows are reported as 'extracted only' and counted.
        loaded = self._load(resource, fhir_rows)
        s["loaded"] = loaded
        logger.info("  loaded=%d", loaded)
        return s

    def _load(self, resource: str, fhir_rows: List[Dict[str, Any]]) -> int:
        """
        Load FHIR rows into the central database.  We delegate to the
        existing legacy loaders in ``etl.pipeline.ETLPipeline`` so that
        the SQL surface stays in ONE place.
        """
        if not fhir_rows:
            return 0
        try:
            from etl.pipeline import ETLPipeline
        except Exception as exc:
            logger.warning("legacy loader import failed: %s", exc)
            return 0

        loader = ETLPipeline(tenant_id=self.tenant_id)
        with shared_db_session() as sdb:
            self._set_tenant_context(sdb)
            try:
                if resource == "patients":
                    return loader.load_patients(sdb, fhir_rows)
                if resource == "encounters":
                    return loader._load_encounters(sdb, fhir_rows)
                if resource == "observations":
                    return loader._load_observations(sdb, fhir_rows)
                if resource == "medications":
                    return loader._load_medications(sdb, fhir_rows)
            except Exception as exc:
                logger.warning("load failed for %s: %s", resource, exc)
        return 0

    # ── public API ───────────────────────────────────────────────────────────
    def sync_all(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Run extract → transform → load for every resource in ``self.plan``.
        Returns ``self.stats``.
        """
        start = datetime.utcnow()
        logger.info("[multi-db] FULL SYNC tenant=%s adapter=%s",
                    self.tenant_id, self.adapter.get_database_type())

        if not self.adapter.validate_connection():
            raise ConnectionError(
                f"Source {self.adapter.get_database_type()} unreachable"
            )

        steps = max(1, len(self.plan))
        for i, item in enumerate(self.plan):
            self._emit(item["resource"], int(5 + 90 * i / steps))
            try:
                self._sync_resource(item, limit)
            except Exception as exc:
                logger.error("resource %s failed: %s", item["resource"], exc)

        self._emit("finalising", 95)
        dur = (datetime.utcnow() - start).total_seconds()
        total_loaded = sum(v["loaded"] for v in self.stats.values())
        total_err = sum(v["errors"] for v in self.stats.values())
        logger.info("[multi-db] DONE  %.2fs  loaded=%d  errors=%d",
                    dur, total_loaded, total_err)
        return self.stats
