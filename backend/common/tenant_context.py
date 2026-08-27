"""
Tenant Context Management for Federated Architecture
Provides tenant-scoped database sessions for API routes

ARCHITECTURE NOTE:
- Hospital source databases remain single-tenant (NO tenant_id)
- Multi-tenancy ONLY in central FHIR database
- This module provides tenant context for central DB queries
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, event
from contextlib import contextmanager
from typing import Optional, Generator
import logging

logger = logging.getLogger(__name__)


class TenantContextManager:
    """
    Manages tenant context for multi-tenant central FHIR database
    
    Usage in API routes:
        from common.tenant_context import get_tenant_context
        
        @app.get("/patients")
        async def get_patients(
            db: Session = Depends(get_shared_db),
            tenant_id: int = Depends(get_current_tenant_id)
        ):
            with tenant_context(db, tenant_id):
                # All queries automatically scoped to this tenant
                patients = db.query(Patient).all()
                return patients
    """
    
    def __init__(self, session: Session):
        self.session = session
        self._current_tenant_id: Optional[int] = None
    
    def set_tenant_context(self, tenant_id: int) -> None:
        """
        Set tenant context for this session (for RLS)
        
        Args:
            tenant_id: ID of the hospital/tenant
        """
        if tenant_id is None:
            raise ValueError("tenant_id cannot be None")
        
        # Set PostgreSQL session variable for Row-Level Security
        self.session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id::TEXT, FALSE)"),
            {"tenant_id": tenant_id}
        )
        
        self._current_tenant_id = tenant_id
        logger.debug(f"Tenant context set to: {tenant_id}")
    
    def get_current_tenant(self) -> Optional[int]:
        """Get the current tenant ID"""
        return self._current_tenant_id
    
    def clear_tenant_context(self) -> None:
        """Clear the tenant context"""
        self.session.execute(
            text("SELECT set_config('app.tenant_id', NULL, FALSE)")
        )
        self._current_tenant_id = None
        logger.debug("Tenant context cleared")


@contextmanager
def tenant_context(session: Session, tenant_id: int) -> Generator[TenantContextManager, None, None]:
    """
    Context manager for tenant-scoped database operations
    
    This ensures all queries within the context are automatically
    filtered to the specified tenant (when RLS is enabled).
    
    Args:
        session: SQLAlchemy session (must be for shared/central DB)
        tenant_id: ID of the hospital/tenant
    
    Usage:
        with tenant_context(db, tenant_id=1):
            patients = db.query(Patient).all()  # Only tenant 1's patients
    
    Example in FastAPI:
        @app.get("/patients")
        async def get_patients(
            db: Session = Depends(get_shared_db),
            current_user: User = Depends(get_current_user)
        ):
            with tenant_context(db, current_user.hospital_id):
                patients = db.query(Patient).all()
                return patients
    """
    manager = TenantContextManager(session)
    manager.set_tenant_context(tenant_id)
    try:
        yield manager
    finally:
        manager.clear_tenant_context()


def configure_tenant_session(session: Session, tenant_id: int) -> None:
    """
    Configure a session to automatically set tenant context on each transaction
    
    This sets up event listeners so the tenant context is automatically
    set at the beginning of each transaction.
    
    Args:
        session: SQLAlchemy session
        tenant_id: ID of the hospital/tenant
    """
    @event.listens_for(session, "after_begin")
    def receive_after_begin(session, transaction, connection):
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id::TEXT, FALSE)"),
            {"tenant_id": tenant_id}
        )
