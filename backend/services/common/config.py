"""
Per-source CDC configuration loader.

Reads `config/cdc_sources.yaml` (or path overridden by $CDC_SOURCES_FILE)
and exposes typed dataclasses for the worker / ingestion / ETL services.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


def _default_sources_file() -> str:
    return os.environ.get(
        "CDC_SOURCES_FILE",
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "config", "cdc_sources.yaml",
        ),
    )


@dataclass
class BatchConfig:
    max_rows: int = 500
    max_bytes: int = 1_048_576           # 1 MB compressed cap
    max_latency_ms: int = 2_000


@dataclass
class RetryConfig:
    max_attempts: int = 8
    initial_backoff_ms: int = 1_000
    max_backoff_ms: int = 60_000
    jitter_pct: int = 20


@dataclass
class SchemaConfig:
    unknown_columns_default: str = "store_raw"   # store_raw | ignore | reject
    new_table_policy: str = "require_config"     # require_config | ignore | auto_register
    registry_auto_stub: bool = False


@dataclass
class FkConfig:
    max_wait_seconds: int = 300
    allow_placeholder_parent: bool = False


@dataclass
class SourceConfig:
    id: str
    db_url: str
    tables: List[str]
    poll_interval_seconds: int = 5
    poll_interval_min_seconds: int = 1
    listen_notify: bool = True
    auto_setup: bool = False
    ingestion_endpoint: str = "http://localhost:8004/api/v1/cdc/ingest"
    ingestion_health_endpoint: str = "http://localhost:8004/healthz"
    auth_key_env: str = ""
    admin_port: int = 9101
    batch: BatchConfig = field(default_factory=BatchConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    schema: SchemaConfig = field(default_factory=SchemaConfig)
    fk: FkConfig = field(default_factory=FkConfig)

    def resolved_auth_key(self) -> str:
        """Read the HMAC key from the env var named by auth_key_env."""
        if not self.auth_key_env:
            raise ValueError(
                f"Source {self.id!r}: auth_key_env is empty — set it to the "
                f"name of an env var holding the HMAC key."
            )
        key = os.environ.get(self.auth_key_env)
        if not key:
            raise ValueError(
                f"Source {self.id!r}: env var {self.auth_key_env!r} is unset "
                f"or empty. Cannot start without an HMAC key."
            )
        return key


def _coerce_source(raw: Dict) -> SourceConfig:
    batch = BatchConfig(**(raw.get("batch") or {}))
    retry = RetryConfig(**(raw.get("retry") or {}))
    schema = SchemaConfig(**(raw.get("schema") or {}))
    fk = FkConfig(**(raw.get("fk") or {}))
    return SourceConfig(
        id=raw["id"],
        db_url=raw["db_url"],
        tables=list(raw["tables"]),
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 5)),
        poll_interval_min_seconds=int(raw.get("poll_interval_min_seconds", 1)),
        listen_notify=bool(raw.get("listen_notify", True)),
        auto_setup=bool(raw.get("auto_setup", False)),
        ingestion_endpoint=raw.get(
            "ingestion_endpoint", "http://localhost:8004/api/v1/cdc/ingest"
        ),
        ingestion_health_endpoint=raw.get(
            "ingestion_health_endpoint", "http://localhost:8004/healthz"
        ),
        auth_key_env=raw.get("auth_key_env", ""),
        admin_port=int(raw.get("admin_port", 9101)),
        batch=batch,
        retry=retry,
        schema=schema,
        fk=fk,
    )


def load_sources(path: Optional[str] = None) -> Dict[str, SourceConfig]:
    """Return {source_id: SourceConfig} from yaml on disk."""
    fpath = path or _default_sources_file()
    if not os.path.exists(fpath):
        raise FileNotFoundError(
            f"CDC sources file not found at {fpath}. "
            f"Set $CDC_SOURCES_FILE or create config/cdc_sources.yaml."
        )
    with open(fpath, "r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    raw_sources = doc.get("sources") or []
    out: Dict[str, SourceConfig] = {}
    for raw in raw_sources:
        cfg = _coerce_source(raw)
        if cfg.id in out:
            raise ValueError(f"Duplicate source id: {cfg.id!r}")
        out[cfg.id] = cfg
    return out


def load_source(source_id: str, path: Optional[str] = None) -> SourceConfig:
    sources = load_sources(path)
    if source_id not in sources:
        raise KeyError(
            f"Source {source_id!r} not found in {path or _default_sources_file()}. "
            f"Known sources: {sorted(sources)}"
        )
    return sources[source_id]


# ── shared / ingestion side ─────────────────────────────────────────────────
def shared_db_url() -> str:
    """Resolve the shared DB URL; defaults to the existing backend settings."""
    url = os.environ.get("INGESTION_DB_URL") or os.environ.get("ETL_SHARED_DB_URL")
    if url:
        return url
    # Fall back to the existing backend settings module so a single .env works.
    from common.config import settings  # type: ignore  # backend.common
    return settings.shared_db_url


def parse_hmac_keys() -> Dict[str, str]:
    """
    Parse CDC_HMAC_KEYS env var of the form
        source_a:secret_a,source_b:secret_b
    into {source_id: secret}.
    """
    raw = os.environ.get("CDC_HMAC_KEYS", "").strip()
    if not raw:
        return {}
    out: Dict[str, str] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(
                f"CDC_HMAC_KEYS entry {chunk!r} is malformed; expected source_id:secret"
            )
        src, secret = chunk.split(":", 1)
        out[src.strip()] = secret.strip()
    return out
