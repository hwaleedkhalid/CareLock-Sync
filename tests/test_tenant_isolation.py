"""
CareLock Sync - Tenant Isolation Tests
Tests RLS enforcement, API isolation, and RAG security
"""

import pytest
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestRLSEnforcement:
    """Test PostgreSQL Row-Level Security enforcement"""
    
    @pytest.fixture
    def db_session(self):
        DATABASE_URL = os.getenv(
            "SHARED_DB_URL",
            "postgresql://postgres:postgres@localhost:5432/carelock_central_fhir"
        )
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        engine.dispose()
    
    def test_rls_enabled_on_tables(self, db_session):
        """Test that RLS is enabled on all FHIR tables"""
        tables = ['fhir_patient', 'fhir_encounter', 'fhir_observation', 'fhir_medication_request']
        
        for table in tables:
            result = db_session.execute(text(f"""
                SELECT relrowsecurity 
                FROM pg_class 
                WHERE relname = '{table}'
            """)).fetchone()
            
            assert result is not None, f"Table {table} not found"
            assert result[0] is True, f"RLS not enabled on {table}"
            print(f"✓ RLS enabled on {table}")
    
    def test_query_without_context_returns_nothing(self, db_session):
        """Test that queries without tenant context return no data"""
        db_session.execute(text("SELECT set_config('app.tenant_id', NULL, false)"))
        db_session.commit()
        
        result = db_session.execute(text("SELECT COUNT(*) FROM fhir_patient")).fetchone()
        count = result[0]
        
        print(f"✓ Without context: {count} rows (expected: 0)")
        assert count == 0, f"Expected 0 rows without context, got {count}"
    
    def test_rls_blocks_cross_tenant_access(self, db_session):
        """Test that RLS blocks access to other tenant's data"""
        db_session.execute(text("SELECT set_config('app.tenant_id', '2', false)"))
        db_session.commit()
        
        result = db_session.execute(text("""
            SELECT COUNT(*) 
            FROM fhir_patient 
            WHERE tenant_id = 1
        """)).fetchone()
        
        count = result[0]
        print(f"✓ Cross-tenant query blocked: {count} rows")
        assert count == 0, f"RLS FAILED: Can see other tenant data"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
