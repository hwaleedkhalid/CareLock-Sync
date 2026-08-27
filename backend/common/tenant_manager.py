"""
Tenant Manager - Handles multi-tenant operations and context management
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, event
from contextlib import contextmanager
from typing import Optional, List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TenantManager:
    """
    Manages tenant context and isolation for multi-tenant operations
    """
    
    def __init__(self, session: Session):
        self.session = session
        self._current_tenant_id: Optional[int] = None
    
    def set_tenant_context(self, tenant_id: int):
        """
        Set the current tenant context for this session
        
        Args:
            tenant_id: ID of the tenant to set as current
        
        Raises:
            ValueError: If tenant doesn't exist or is inactive
        """
        # Verify tenant exists and is active
        result = self.session.execute(
            text("SELECT is_active FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).fetchone()
        
        if not result:
            raise ValueError(f"Tenant {tenant_id} does not exist")
        
        if not result[0]:
            raise ValueError(f"Tenant {tenant_id} is inactive")
        
        # Set tenant in PostgreSQL session variable
        self.session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id::TEXT, FALSE)"),
            {"tenant_id": tenant_id}
        )
        
        self._current_tenant_id = tenant_id
        logger.info(f"Tenant context set to: {tenant_id}")
    
    def get_current_tenant(self) -> Optional[int]:
        """Get the current tenant ID"""
        return self._current_tenant_id
    
    def clear_tenant_context(self):
        """Clear the tenant context"""
        self.session.execute(
            text("SELECT set_config('app.current_tenant', NULL, FALSE)")
        )
        self._current_tenant_id = None
        logger.info("Tenant context cleared")
    
    def create_tenant(self, tenant_data: Dict) -> int:
        """
        Create a new tenant
        
        Args:
            tenant_data: Dictionary with tenant information
                Required: tenant_name, tenant_code
                Optional: hospital_name, address, contact_email, contact_phone
        
        Returns:
            tenant_id of the newly created tenant
        """
        # Validate required fields
        if 'tenant_name' not in tenant_data or 'tenant_code' not in tenant_data:
            raise ValueError("tenant_name and tenant_code are required")
        
        # Insert tenant
        result = self.session.execute(
            text("""
                INSERT INTO tenants (
                    tenant_name, tenant_code, hospital_name, 
                    address, contact_email, contact_phone
                )
                VALUES (
                    :tenant_name, :tenant_code, :hospital_name,
                    :address, :contact_email, :contact_phone
                )
                RETURNING tenant_id
            """),
            {
                "tenant_name": tenant_data['tenant_name'],
                "tenant_code": tenant_data['tenant_code'],
                "hospital_name": tenant_data.get('hospital_name'),
                "address": tenant_data.get('address'),
                "contact_email": tenant_data.get('contact_email'),
                "contact_phone": tenant_data.get('contact_phone')
            }
        )
        
        tenant_id = result.fetchone()[0]
        self.session.commit()
        
        logger.info(f"Created tenant: {tenant_id} ({tenant_data['tenant_code']})")
        return tenant_id
    
    def get_tenant(self, tenant_id: int) -> Optional[Dict]:
        """Get tenant information"""
        result = self.session.execute(
            text("""
                SELECT tenant_id, tenant_name, tenant_code, hospital_name,
                       address, contact_email, contact_phone, is_active,
                       onboarded_at, created_at
                FROM tenants
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": tenant_id}
        ).fetchone()
        
        if not result:
            return None
        
        return {
            "tenant_id": result[0],
            "tenant_name": result[1],
            "tenant_code": result[2],
            "hospital_name": result[3],
            "address": result[4],
            "contact_email": result[5],
            "contact_phone": result[6],
            "is_active": result[7],
            "onboarded_at": result[8],
            "created_at": result[9]
        }
    
    def list_tenants(self, active_only: bool = True) -> List[Dict]:
        """List all tenants"""
        query = "SELECT tenant_id, tenant_name, tenant_code, is_active FROM tenants"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY tenant_name"
        
        results = self.session.execute(text(query)).fetchall()
        
        return [
            {
                "tenant_id": row[0],
                "tenant_name": row[1],
                "tenant_code": row[2],
                "is_active": row[3]
            }
            for row in results
        ]
    
    def deactivate_tenant(self, tenant_id: int):
        """Deactivate a tenant (soft delete)"""
        self.session.execute(
            text("""
                UPDATE tenants
                SET is_active = FALSE,
                    offboarded_at = CURRENT_TIMESTAMP
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": tenant_id}
        )
        self.session.commit()
        logger.info(f"Deactivated tenant: {tenant_id}")
    
    def reactivate_tenant(self, tenant_id: int):
        """Reactivate a tenant"""
        self.session.execute(
            text("""
                UPDATE tenants
                SET is_active = TRUE,
                    offboarded_at = NULL
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": tenant_id}
        )
        self.session.commit()
        logger.info(f"Reactivated tenant: {tenant_id}")
    
    def get_tenant_stats(self, tenant_id: Optional[int] = None) -> Dict:
        """
        Get statistics for a tenant or all tenants
        
        Args:
            tenant_id: Specific tenant ID, or None for all tenants
        
        Returns:
            Dictionary with statistics
        """
        if tenant_id:
            query = text("""
                SELECT * FROM tenant_statistics
                WHERE tenant_id = :tenant_id
            """)
            result = self.session.execute(query, {"tenant_id": tenant_id}).fetchone()
            
            if not result:
                return {}
            
            return {
                "tenant_id": result[0],
                "tenant_name": result[1],
                "tenant_code": result[2],
                "is_active": result[3],
                "patient_count": result[4],
                "encounter_count": result[5],
                "lab_result_count": result[6],
                "medication_count": result[7],
                "last_patient_added": result[8],
                "last_encounter_added": result[9]
            }
        else:
            query = text("SELECT * FROM tenant_statistics ORDER BY tenant_name")
            results = self.session.execute(query).fetchall()
            
            return [
                {
                    "tenant_id": row[0],
                    "tenant_name": row[1],
                    "tenant_code": row[2],
                    "is_active": row[3],
                    "patient_count": row[4],
                    "encounter_count": row[5],
                    "lab_result_count": row[6],
                    "medication_count": row[7],
                    "last_patient_added": row[8],
                    "last_encounter_added": row[9]
                }
                for row in results
            ]
    
    def verify_data_isolation(self, tenant_id: int) -> Dict:
        """
        Verify that data isolation is working correctly for a tenant
        
        Returns:
            Dictionary with verification results
        """
        # Set tenant context
        self.set_tenant_context(tenant_id)
        
        # Count records accessible with tenant context
        with_context = {
            "patients": self.session.execute(text("SELECT COUNT(*) FROM patients")).scalar(),
            "encounters": self.session.execute(text("SELECT COUNT(*) FROM encounters")).scalar(),
            "lab_results": self.session.execute(text("SELECT COUNT(*) FROM lab_results")).scalar(),
            "medications": self.session.execute(text("SELECT COUNT(*) FROM medications")).scalar()
        }
        
        # Clear context and count all records
        self.clear_tenant_context()
        
        # Disable RLS temporarily (requires superuser)
        try:
            self.session.execute(text("SET row_security = off"))
            
            without_context = {
                "patients": self.session.execute(
                    text("SELECT COUNT(*) FROM patients WHERE tenant_id = :tid"),
                    {"tid": tenant_id}
                ).scalar(),
                "encounters": self.session.execute(
                    text("SELECT COUNT(*) FROM encounters WHERE tenant_id = :tid"),
                    {"tid": tenant_id}
                ).scalar(),
                "lab_results": self.session.execute(
                    text("SELECT COUNT(*) FROM lab_results WHERE tenant_id = :tid"),
                    {"tid": tenant_id}
                ).scalar(),
                "medications": self.session.execute(
                    text("SELECT COUNT(*) FROM medications WHERE tenant_id = :tid"),
                    {"tid": tenant_id}
                ).scalar()
            }
            
            self.session.execute(text("SET row_security = on"))
        except Exception as e:
            logger.warning(f"Could not verify isolation without RLS: {e}")
            without_context = with_context
        
        # Compare counts
        isolated_correctly = all(
            with_context[table] == without_context[table]
            for table in with_context.keys()
        )
        
        return {
            "tenant_id": tenant_id,
            "isolated_correctly": isolated_correctly,
            "with_context": with_context,
            "without_context": without_context
        }
    
    def audit_tenant_access(self, tenant_id: int, action: str, 
                          table_name: str, record_id: Optional[int] = None,
                          user_id: Optional[int] = None, 
                          changes: Optional[Dict] = None,
                          ip_address: Optional[str] = None):
        """Log tenant access for audit purposes"""
        self.session.execute(
            text("""
                INSERT INTO tenant_audit_log (
                    tenant_id, action, table_name, record_id,
                    user_id, changes, ip_address
                )
                VALUES (
                    :tenant_id, :action, :table_name, :record_id,
                    :user_id, :changes::jsonb, :ip_address::inet
                )
            """),
            {
                "tenant_id": tenant_id,
                "action": action,
                "table_name": table_name,
                "record_id": record_id,
                "user_id": user_id,
                "changes": changes,
                "ip_address": ip_address
            }
        )
        self.session.commit()


@contextmanager
def tenant_context(session: Session, tenant_id: int):
    """
    Context manager for tenant-scoped operations
    
    Usage:
        with tenant_context(session, tenant_id=1):
            patients = session.query(Patient).all()  # Only tenant 1's patients
    """
    manager = TenantManager(session)
    manager.set_tenant_context(tenant_id)
    try:
        yield manager
    finally:
        manager.clear_tenant_context()


def configure_tenant_session(session: Session, tenant_id: int):
    """
    Configure a session to automatically filter by tenant
    
    This sets up the session so all queries are automatically
    scoped to the specified tenant.
    """
    @event.listens_for(session, "after_begin")
    def receive_after_begin(session, transaction, connection):
        connection.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id::TEXT, FALSE)"),
            {"tenant_id": tenant_id}
        )
