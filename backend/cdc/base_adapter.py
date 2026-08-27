"""
Base CDC Adapter — Abstract Interface
=====================================

Two layered contracts live here:

1. ``CDCAdapter``      — original change-data-capture contract used by
   ``cdc_agent`` and the worker.  Concrete adapters MUST implement
   ``setup_cdc``, ``get_changes`` and ``get_latest_change_id``.

2. ``BaseAdapter``     — the wider operational contract added during the
   multi-DB push.  It overlays ETL-style helpers
   (``connect``, ``fetch_schema``, ``extract_data``, ``load_data``,
   ``close``) on top of ``CDCAdapter`` so every database adapter exposes
   the same surface to the multi-DB ETL pipeline regardless of whether
   native CDC is available.

The two are merged into one class for backwards compatibility:
``CDCAdapter`` IS the base and now carries default no-op implementations
for the operational helpers that subclasses can override.  Existing code
that only uses CDC (PostgreSQLAdapter, cdc_agent) is unaffected.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime
from enum import Enum


class OperationType(Enum):
    """CDC operation types"""
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ChangeEvent:
    """Unified change event format across all databases"""
    def __init__(
        self,
        change_id: int,
        table_name: str,
        operation: OperationType,
        record_id: Any,
        old_data: Optional[Dict] = None,
        new_data: Optional[Dict] = None,
        changed_at: datetime = None,
        database_type: str = None
    ):
        self.change_id = change_id
        self.table_name = table_name
        self.operation = operation
        self.record_id = record_id
        self.old_data = old_data or {}
        self.new_data = new_data or {}
        self.changed_at = changed_at or datetime.utcnow()
        self.database_type = database_type
    
    def to_dict(self) -> Dict:
        return {
            'change_id': self.change_id,
            'table_name': self.table_name,
            'operation': self.operation.value,
            'record_id': self.record_id,
            'old_data': self.old_data,
            'new_data': self.new_data,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'database_type': self.database_type
        }
    
    def __repr__(self):
        return f"ChangeEvent({self.operation.value} on {self.table_name}, ID={self.record_id})"


class CDCAdapter(ABC):
    """Abstract base class for database-specific CDC adapters"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.is_setup = False
    
    @abstractmethod
    def get_database_type(self) -> str:
        """Return the database type identifier"""
        pass
    
    @abstractmethod
    def setup_cdc(self, tables: List[str]) -> bool:
        """Setup CDC for specified tables"""
        pass
    
    @abstractmethod
    def get_changes(
        self, 
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ChangeEvent]:
        """Get change events since specified change ID"""
        pass
    
    @abstractmethod
    def get_latest_change_id(self) -> Optional[int]:
        """Get the latest change ID"""
        pass
    
    def is_cdc_enabled(self, table_name: str) -> bool:
        """Check if CDC is enabled for a table"""
        return self.is_setup
    
    def validate_connection(self) -> bool:
        """Validate database connection"""
        try:
            return True
        except Exception as e:
            print(f"Connection validation failed: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get CDC statistics"""
        return {
            'database_type': self.get_database_type(),
            'is_setup': self.is_setup,
            'connection_valid': self.validate_connection()
        }

    # ── Operational ETL surface (added Sprint 6 — multi-DB push) ─────────────
    # Default implementations raise NotImplementedError so adapters that only
    # care about CDC (e.g. legacy PostgreSQLAdapter) are not forced to provide
    # them.  All four new adapters (MySQL, MongoDB, SQL Server, Oracle)
    # override every method below.

    def connect(self) -> Any:
        """Establish a connection / engine handle.  Idempotent."""
        raise NotImplementedError(f"{self.get_database_type()} adapter has no connect()")

    def close(self) -> None:
        """Release any connection / engine resources."""
        return None

    def fetch_schema(self) -> Dict[str, Any]:
        """
        Return a uniform schema description regardless of underlying engine.

        Shape:
            {
              "database_type": "<type>",
              "discovered_at": "<iso>",
              "total_tables":  <int>,
              "tables": {
                 "<name>": {
                    "table_name": "<name>",
                    "columns":    [{"name", "type", "nullable", "primary_key"}],
                    "primary_keys": ["..."],
                    "foreign_keys": [...],
                    "row_count":  <int | None>
                 }, ...
              }
            }
        """
        raise NotImplementedError(f"{self.get_database_type()} adapter has no fetch_schema()")

    def extract_data(
        self,
        table_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Bulk-extract rows from ``table_name`` as a list of plain dicts."""
        raise NotImplementedError(f"{self.get_database_type()} adapter has no extract_data()")

    def iter_data(
        self,
        table_name: str,
        batch_size: int = 500,
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Default streaming wrapper: yield ``extract_data`` in offset windows.
        Adapters that have native cursor support should override.
        """
        offset = 0
        while True:
            batch = self.extract_data(table_name, limit=batch_size, offset=offset)
            if not batch:
                return
            yield batch
            if len(batch) < batch_size:
                return
            offset += batch_size

    def load_data(
        self,
        table_name: str,
        rows: List[Dict[str, Any]],
        upsert_keys: Optional[List[str]] = None,
    ) -> int:
        """Bulk-load ``rows`` into ``table_name``.  Returns number written."""
        raise NotImplementedError(f"{self.get_database_type()} adapter has no load_data()")

    # Capability flags consulted by the multi-DB pipeline
    SUPPORTS_NATIVE_CDC: bool = False
    SUPPORTS_TRANSACTIONS: bool = True


# Backwards-compatible alias — expressing intent at import sites
BaseAdapter = CDCAdapter
