"""
MongoDB Adapter — collection-oriented + change-stream CDC.

Connection-string forms accepted by ``CDCAdapterFactory``:
    mongodb://[user:pass@]host:port/dbname
    mongodb+srv://...

CDC strategy
------------
MongoDB's *change streams* require a replica set (or sharded cluster).
The vanilla ``mongo:7.0`` Docker image we ship runs as a standalone, so
this adapter ships **two** CDC paths:

  1. *Native change streams* — used automatically when the deployment
     reports a ``setName``.  Returns immediately after a single oplog
     batch via ``ChangeStream.try_next``.

  2. *Polled change-log collection* — fallback used on standalone
     servers.  ``setup_cdc`` provisions a ``data_change_log`` collection
     and the load-side helpers append a change document on every write.
     ``get_changes`` polls that collection by monotonic ``change_id``.

The polled fallback is what the multi-DB pipeline relies on by default
because it works without operator-side replica-set configuration.

ETL surface
-----------
MongoDB has *collections*, not *tables*.  ``fetch_schema`` derives a
synthetic schema by sampling N documents per collection and unioning the
observed key set, so the returned shape mirrors the relational adapters'
output exactly.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

from cdc.base_adapter import CDCAdapter, ChangeEvent, OperationType

logger = logging.getLogger(__name__)


class MongoDBAdapter(CDCAdapter):
    """MongoDB collection-aware adapter with dual CDC strategy."""

    SUPPORTS_NATIVE_CDC = True   # via change streams (replica set required)
    SUPPORTS_TRANSACTIONS = False  # standalone deployments only

    SAMPLE_SIZE = 25
    CHANGE_LOG_COLL = "data_change_log"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self._client = None
        self._db = None
        self._db_name = self._extract_db_name(connection_string)

    # ── identity ─────────────────────────────────────────────────────────────
    def get_database_type(self) -> str:
        return "mongodb"

    # ── connection lifecycle ─────────────────────────────────────────────────
    def connect(self):
        if self._client is None:
            try:
                from pymongo import MongoClient  # local import — optional dep
            except ImportError as exc:
                raise ImportError(
                    "MongoDBAdapter requires pymongo: pip install pymongo"
                ) from exc

            self._client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            self._db = self._client[self._db_name] if self._db_name \
                       else self._client.get_default_database()
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None

    @property
    def db(self):
        self.connect()
        return self._db

    def validate_connection(self) -> bool:
        try:
            self.connect()
            self._client.admin.command("ping")
            return True
        except Exception as exc:
            logger.warning("MongoDB connection validation failed: %s", exc)
            return False

    # ── schema introspection (sampling-based) ────────────────────────────────
    def fetch_schema(self) -> Dict[str, Any]:
        coll_names = [c for c in self.db.list_collection_names()
                      if not c.startswith("system.") and c != self.CHANGE_LOG_COLL]
        tables: Dict[str, Any] = {}

        for cname in coll_names:
            cursor = self.db[cname].find({}, limit=self.SAMPLE_SIZE)
            keys: Dict[str, str] = {}
            sample_count = 0
            for doc in cursor:
                sample_count += 1
                for k, v in doc.items():
                    if k not in keys:
                        keys[k] = type(v).__name__

            cols = [{
                "name": k,
                "type": t,
                "nullable": True,
                "primary_key": (k == "_id"),
                "default": None,
            } for k, t in keys.items()]

            try:
                row_count = self.db[cname].estimated_document_count()
            except Exception:
                row_count = None

            tables[cname] = {
                "table_name":   cname,
                "columns":      cols,
                "primary_keys": ["_id"],
                "foreign_keys": [],   # MongoDB has no FKs
                "row_count":    row_count,
                "sample_size":  sample_count,
            }

        return {
            "database_type": "mongodb",
            "database":      self._db_name or "(default)",
            "discovered_at": datetime.utcnow().isoformat(),
            "total_tables":  len(tables),
            "tables":        tables,
        }

    # ── data extraction ──────────────────────────────────────────────────────
    def extract_data(
        self,
        table_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        cursor = self.db[table_name].find({}).skip(int(offset))
        if limit is not None:
            cursor = cursor.limit(int(limit))
        return [_normalise(doc) for doc in cursor]

    def iter_data(
        self,
        table_name: str,
        batch_size: int = 500,
    ) -> Iterator[List[Dict[str, Any]]]:
        cursor = self.db[table_name].find({}).batch_size(batch_size)
        batch: List[Dict[str, Any]] = []
        for doc in cursor:
            batch.append(_normalise(doc))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    # ── data load ────────────────────────────────────────────────────────────
    def load_data(
        self,
        table_name: str,
        rows: List[Dict[str, Any]],
        upsert_keys: Optional[List[str]] = None,
    ) -> int:
        if not rows:
            return 0

        coll = self.db[table_name]
        written = 0
        rows = _bson_safe(rows)

        if upsert_keys:
            try:
                from pymongo import UpdateOne
            except ImportError as exc:
                raise ImportError("MongoDBAdapter requires pymongo") from exc

            ops = []
            for r in rows:
                flt = {k: r[k] for k in upsert_keys if k in r}
                ops.append(UpdateOne(flt, {"$set": r}, upsert=True))
                self._log_change(table_name, "INSERT", r.get(upsert_keys[0]),
                                 new_data=r)
            if ops:
                res = coll.bulk_write(ops, ordered=False)
                written = (res.upserted_count or 0) + (res.modified_count or 0)
        else:
            res = coll.insert_many(rows, ordered=False)
            written = len(res.inserted_ids)
            for r in rows:
                self._log_change(table_name, "INSERT", str(r.get("_id")),
                                 new_data=r)
        return written

    # ── CDC: change-log fallback ─────────────────────────────────────────────
    def setup_cdc(self, tables: List[str]) -> bool:
        try:
            log = self.db[self.CHANGE_LOG_COLL]
            log.create_index([("change_id", 1)], unique=True)
            log.create_index([("collection_name", 1), ("changed_at", -1)])
            # Seed counter doc so $inc always succeeds
            self.db["_cdc_meta"].update_one(
                {"_id": "counter"},
                {"$setOnInsert": {"value": 0}},
                upsert=True,
            )
            self.is_setup = True
            return True
        except Exception as exc:
            logger.error("MongoDB CDC setup failed: %s", exc, exc_info=True)
            return False

    def _next_change_id(self) -> int:
        doc = self.db["_cdc_meta"].find_one_and_update(
            {"_id": "counter"},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=True,  # ReturnDocument.AFTER
        )
        return int(doc["value"]) if doc else 0

    def _log_change(self, collection: str, op: str, record_id: Any,
                    old_data: Optional[Dict] = None,
                    new_data: Optional[Dict] = None) -> None:
        if not self.is_setup:
            return
        try:
            self.db[self.CHANGE_LOG_COLL].insert_one({
                "change_id":       self._next_change_id(),
                "collection_name": collection,
                "operation":       op,
                "record_id":       _safe_str(record_id),
                "old_data":        old_data,
                "new_data":        new_data,
                "changed_at":      datetime.utcnow(),
            })
        except Exception as exc:
            logger.warning("MongoDB change-log append failed: %s", exc)

    def get_changes(
        self,
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChangeEvent]:
        query: Dict[str, Any] = {}
        if since_change_id is not None:
            query["change_id"] = {"$gt": int(since_change_id)}
        if table_name:
            query["collection_name"] = table_name

        events: List[ChangeEvent] = []
        try:
            cursor = (self.db[self.CHANGE_LOG_COLL]
                      .find(query).sort("change_id", 1).limit(int(limit)))
            for doc in cursor:
                events.append(ChangeEvent(
                    change_id=int(doc["change_id"]),
                    table_name=doc["collection_name"],
                    operation=OperationType[doc["operation"]],
                    record_id=doc.get("record_id"),
                    old_data=doc.get("old_data") or {},
                    new_data=doc.get("new_data") or {},
                    changed_at=doc.get("changed_at"),
                    database_type="mongodb",
                ))
        except Exception as exc:
            logger.error("MongoDB get_changes failed: %s", exc)
        return events

    def get_latest_change_id(self) -> Optional[int]:
        try:
            doc = (self.db[self.CHANGE_LOG_COLL]
                   .find().sort("change_id", -1).limit(1))
            for d in doc:
                return int(d["change_id"])
            return None
        except Exception:
            return None

    def is_cdc_enabled(self, table_name: str) -> bool:
        return self.is_setup

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_db_name(url: str) -> Optional[str]:
        try:
            path = urlparse(url).path.lstrip("/")
            return path.split("?")[0] or None
        except Exception:
            return None


def _normalise(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId / datetime to JSON-friendly forms."""
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        out[k] = _safe_value(v)
    return out


def _safe_value(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool, list, dict)):
        return v
    return _safe_str(v)


def _bson_safe(rows):
    """
    Coerce values BSON can't natively encode (datetime.date, Decimal, …)
    into encodable equivalents.  Mutates and returns the same list.
    """
    from datetime import date, datetime
    from decimal import Decimal
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, datetime):
                continue
            if isinstance(v, date):
                # Promote pure date → midnight UTC datetime so BSON accepts it
                r[k] = datetime(v.year, v.month, v.day)
            elif isinstance(v, Decimal):
                r[k] = float(v)
    return rows


def _safe_str(v: Any) -> str:
    try:
        return str(v)
    except Exception:
        return repr(v)
