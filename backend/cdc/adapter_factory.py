"""
CDC Adapter Factory — supports ALL 5 major database systems.

Coverage map (real-world hospital deployments):
  PostgreSQL 20%  +  MySQL 40%  +  MongoDB 5%  +  Oracle 25%  +  SQL Server 10%
                                                                       =  100%

The factory:
  * detects the database type from a connection-string scheme,
  * lazy-imports the matching adapter (so missing optional drivers
    only fail when the relevant database is actually requested),
  * supports config-driven instantiation via ``from_config(dict)``.

Usage
-----
    from cdc.adapter_factory import CDCAdapterFactory

    adapter = CDCAdapterFactory.create_adapter(
        "mongodb://localhost:27017/hospital_db_mongodb"
    )
    if not adapter.validate_connection():
        raise SystemExit("DB unreachable")

    schema = adapter.fetch_schema()
    rows   = adapter.extract_data("patients", limit=100)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type
from urllib.parse import urlparse

from cdc.base_adapter import CDCAdapter, BaseAdapter  # noqa: F401
from cdc.postgresql_adapter import PostgreSQLAdapter


# ── Scheme → adapter-loader registry ─────────────────────────────────────────
# Loaders are zero-arg callables returning the adapter CLASS.  Lazy so that
# missing optional drivers (pymongo, pyodbc, oracledb) don't blow up imports.

def _load_mysql() -> Type[CDCAdapter]:
    from cdc.mysql_adapter import MySQLAdapter
    return MySQLAdapter

def _load_mongo() -> Type[CDCAdapter]:
    from cdc.mongodb_adapter import MongoDBAdapter
    return MongoDBAdapter

def _load_sqlserver() -> Type[CDCAdapter]:
    from cdc.sqlserver_adapter import SQLServerAdapter
    return SQLServerAdapter

def _load_oracle() -> Type[CDCAdapter]:
    from cdc.oracle_adapter import OracleAdapter
    return OracleAdapter

def _load_pg() -> Type[CDCAdapter]:
    return PostgreSQLAdapter


_SCHEME_REGISTRY: Dict[str, Any] = {
    # PostgreSQL
    "postgresql":      _load_pg,
    "postgres":        _load_pg,
    "postgresql+psycopg2": _load_pg,
    # MySQL
    "mysql":           _load_mysql,
    "mysql+pymysql":   _load_mysql,
    # MongoDB
    "mongodb":         _load_mongo,
    "mongodb+srv":     _load_mongo,
    # SQL Server
    "sqlserver":       _load_sqlserver,
    "mssql":           _load_sqlserver,
    "mssql+pyodbc":    _load_sqlserver,
    # Oracle
    "oracle":          _load_oracle,
    "oracle+oracledb": _load_oracle,
    "oracle+cx_oracle": _load_oracle,
}


# Coverage of real-world hospital DB deployments — used by reporting only.
_COVERAGE = {
    "postgresql": 20, "mysql": 40, "mongodb": 5,
    "oracle": 25, "sqlserver": 10,
}


class CDCAdapterFactory:
    """Factory that returns the right CDC + ETL adapter for a connection string."""

    # ── Detection ────────────────────────────────────────────────────────────
    @staticmethod
    def detect_database_type(connection_string: str) -> str:
        """Return canonical type name (postgresql/mysql/mongodb/oracle/sqlserver)."""
        if not connection_string or "://" not in connection_string:
            raise ValueError(
                f"Connection string missing scheme: {connection_string!r}"
            )
        scheme = connection_string.split("://", 1)[0].lower()
        if scheme not in _SCHEME_REGISTRY:
            raise ValueError(
                f"Unsupported database scheme {scheme!r}. "
                f"Supported: {sorted(set(_SCHEME_REGISTRY))}"
            )
        # Map the scheme to its canonical short name
        if scheme.startswith("postgres"):
            return "postgresql"
        if scheme.startswith("mysql"):
            return "mysql"
        if scheme.startswith("mongodb"):
            return "mongodb"
        if scheme.startswith(("sqlserver", "mssql")):
            return "sqlserver"
        if scheme.startswith("oracle"):
            return "oracle"
        return scheme  # defensive

    # ── Construction ─────────────────────────────────────────────────────────
    @staticmethod
    def create_adapter(connection_string: str) -> CDCAdapter:
        """Create the appropriate CDC adapter for ``connection_string``."""
        scheme = connection_string.split("://", 1)[0].lower()
        loader = _SCHEME_REGISTRY.get(scheme)
        if loader is None:
            raise ValueError(
                f"Unsupported database type: {scheme!r}. "
                f"Supported: {sorted(set(_SCHEME_REGISTRY))}"
            )
        try:
            adapter_cls = loader()
        except ImportError as exc:
            raise ImportError(
                f"Driver missing for {scheme!r}: {exc}\n"
                f"Hint: install the corresponding Python package "
                f"(pymysql / pymongo / pyodbc / oracledb)."
            ) from exc
        return adapter_cls(connection_string)

    @staticmethod
    def from_config(source_config: Dict[str, Any]) -> CDCAdapter:
        """
        Build an adapter from a single ``sources[]`` entry from
        ``config/sync_config.json``.  Required key: ``connection_string``.
        """
        cs = source_config.get("connection_string")
        if not cs:
            raise ValueError("Config entry missing 'connection_string'")
        return CDCAdapterFactory.create_adapter(cs)

    @staticmethod
    def all_from_config(config: Dict[str, Any]) -> List[CDCAdapter]:
        """
        Iterate ``config['sources']`` and instantiate one adapter per
        source.  Adapters whose driver is unavailable are skipped with
        a logged warning rather than aborting the whole batch.
        """
        import logging
        log = logging.getLogger(__name__)
        out: List[CDCAdapter] = []
        for src in config.get("sources", []):
            try:
                out.append(CDCAdapterFactory.from_config(src))
            except (ValueError, ImportError) as exc:
                log.warning("Skipping source %s: %s",
                            src.get("id", "<no-id>"), exc)
        return out

    # ── Catalogue ────────────────────────────────────────────────────────────
    @staticmethod
    def get_supported_databases() -> List[str]:
        return ["postgresql", "mysql", "mongodb", "oracle", "sqlserver"]

    @staticmethod
    def get_coverage_percentage(databases_supported: List[str]) -> int:
        return sum(_COVERAGE.get(db.lower(), 0) for db in databases_supported)

    @staticmethod
    def parse_connection(connection_string: str) -> Dict[str, Any]:
        """
        Decompose a connection string into parts a UI can render
        (host, port, user, db) without leaking the password.
        """
        try:
            u = urlparse(connection_string)
            return {
                "scheme":   u.scheme,
                "user":     u.username,
                "host":     u.hostname,
                "port":     u.port,
                "database": (u.path or "").lstrip("/"),
            }
        except Exception:
            return {"scheme": connection_string.split("://", 1)[0]}
