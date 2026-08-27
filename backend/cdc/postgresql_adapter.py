"""
PostgreSQL CDC Adapter - Trigger-based
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdc.base_adapter import CDCAdapter, ChangeEvent, OperationType
from sqlalchemy import create_engine, text, inspect as sa_inspect
from typing import Any, Dict, List, Optional
from datetime import datetime


class PostgreSQLAdapter(CDCAdapter):
    """PostgreSQL trigger-based CDC adapter (now with full ETL surface)"""

    SUPPORTS_NATIVE_CDC = True
    SUPPORTS_TRANSACTIONS = True

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.engine = create_engine(connection_string, pool_pre_ping=True)

    # ── operational ETL surface (added Sprint 6) ─────────────────────────────
    def connect(self):
        return self.engine

    def close(self) -> None:
        self.engine.dispose()

    def fetch_schema(self) -> Dict[str, Any]:
        inspector = sa_inspect(self.engine)
        tables: Dict[str, Any] = {}
        for tname in inspector.get_table_names():
            cols = []
            for col in inspector.get_columns(tname):
                cols.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col.get("primary_key", False),
                    "default": str(col.get("default")) if col.get("default") else None,
                })
            try:
                with self.engine.connect() as conn:
                    rc = conn.execute(text(f'SELECT COUNT(*) FROM "{tname}"')).scalar()
            except Exception:
                rc = None
            tables[tname] = {
                "table_name":   tname,
                "columns":      cols,
                "primary_keys": inspector.get_pk_constraint(tname).get(
                                    "constrained_columns", []),
                "foreign_keys": [{
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table":      fk["referred_table"],
                    "referred_columns":    fk["referred_columns"],
                } for fk in inspector.get_foreign_keys(tname)],
                "row_count":    rc,
            }
        return {
            "database_type": "postgresql",
            "discovered_at": datetime.utcnow().isoformat(),
            "total_tables":  len(tables),
            "tables":        tables,
        }

    def extract_data(self, table_name: str,
                     limit: Optional[int] = None,
                     offset: int = 0) -> List[Dict[str, Any]]:
        valid = sa_inspect(self.engine).get_table_names()
        if table_name not in valid:
            raise ValueError(f"Unknown PostgreSQL table: {table_name!r}")
        sql = f'SELECT * FROM "{table_name}"'
        params: Dict[str, Any] = {}
        if limit is not None:
            sql += " LIMIT :lim OFFSET :off"
            params = {"lim": int(limit), "off": int(offset)}
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def load_data(self, table_name: str, rows: List[Dict[str, Any]],
                  upsert_keys: Optional[List[str]] = None) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        col_csv = ", ".join(f'"{c}"' for c in cols)
        param_csv = ", ".join(f":{c}" for c in cols)
        if upsert_keys:
            non_key = [c for c in cols if c not in upsert_keys]
            update = ", ".join(f'"{c}"=EXCLUDED."{c}"' for c in non_key) \
                     or f'"{cols[0]}"=EXCLUDED."{cols[0]}"'
            on = ", ".join(f'"{k}"' for k in upsert_keys)
            sql = (f'INSERT INTO "{table_name}" ({col_csv}) VALUES ({param_csv}) '
                   f'ON CONFLICT ({on}) DO UPDATE SET {update}')
        else:
            sql = f'INSERT INTO "{table_name}" ({col_csv}) VALUES ({param_csv})'
        written = 0
        with self.engine.begin() as conn:
            for r in rows:
                conn.execute(text(sql), r)
                written += 1
        return written
    
    def get_database_type(self) -> str:
        return "postgresql"
    
    def setup_cdc(self, tables: List[str]) -> bool:
        """Setup CDC triggers for PostgreSQL tables"""
        try:
            from connector.cdc_monitor import CDCMonitor
            monitor = CDCMonitor(self.connection_string)
            
            for table in tables:
                monitor.add_trigger_to_table(table)
            
            self.is_setup = True
            return True
        except Exception as e:
            print(f"PostgreSQL CDC setup failed: {e}")
            return False
    
    def get_changes(
        self, 
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ChangeEvent]:
        """Get changes from data_change_log table"""
        changes = []
        
        try:
            with self.engine.connect() as conn:
                query = """
                    SELECT change_id, table_name, operation, 
                           record_id, old_data, new_data, changed_at
                    FROM data_change_log
                    WHERE 1=1
                """
                params = {}
                
                if since_change_id is not None:
                    query += " AND change_id > :since_id"
                    params['since_id'] = since_change_id
                
                if table_name:
                    query += " AND table_name = :table_name"
                    params['table_name'] = table_name
                
                query += " ORDER BY change_id LIMIT :limit"
                params['limit'] = limit
                
                result = conn.execute(text(query), params)
                
                for row in result:
                    changes.append(ChangeEvent(
                        change_id=row[0],
                        table_name=row[1],
                        operation=OperationType[row[2]],
                        record_id=row[3],
                        old_data=row[4],
                        new_data=row[5],
                        changed_at=row[6],
                        database_type='postgresql'
                    ))
        except Exception as e:
            print(f"Error getting PostgreSQL changes: {e}")
        
        return changes
    
    def get_latest_change_id(self) -> Optional[int]:
        """Get the latest change ID"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT MAX(change_id) FROM data_change_log"
                ))
                return result.scalar()
        except Exception as e:
            return None
    
    def is_cdc_enabled(self, table_name: str) -> bool:
        """Check if CDC trigger exists for table"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM information_schema.triggers
                    WHERE event_object_table = :table_name
                    AND trigger_name LIKE '%_change_trigger'
                """), {'table_name': table_name})
                return result.scalar() > 0
        except Exception as e:
            return False
    
    def validate_connection(self) -> bool:
        """Validate PostgreSQL connection"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            return False
