"""
CDC Module — multi-database CDC + ETL adapters.

Public surface:
  * CDCAdapter / BaseAdapter    — abstract contract
  * ChangeEvent / OperationType — uniform change-event model
  * CDCAdapterFactory           — scheme-driven adapter creation
  * PostgreSQLAdapter           — PostgreSQL adapter (always importable)

Other adapters (MySQL, MongoDB, Oracle, SQL Server) are imported lazily
by the factory so missing optional drivers never break a plain
``from cdc import CDCAdapterFactory``.
"""
from cdc.base_adapter import (
    BaseAdapter,
    CDCAdapter,
    ChangeEvent,
    OperationType,
)
from cdc.adapter_factory import CDCAdapterFactory
from cdc.postgresql_adapter import PostgreSQLAdapter

__all__ = [
    "BaseAdapter",
    "CDCAdapter",
    "ChangeEvent",
    "OperationType",
    "CDCAdapterFactory",
    "PostgreSQLAdapter",
]
