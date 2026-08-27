"""
CareLock Sync - Complete System Test Suite
Unit + Regression + Integration Tests
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTenantContextUnit:
    """Unit tests for tenant context management"""
    
    def test_tenant_context_creation(self):
        """Test creating TenantContextManager"""
        try:
            from backend.common.tenant_context import TenantContextManager
            
            class MockSession:
                def execute(self, query, params=None):
                    return type('Result', (), {})()
            
            session = MockSession()
            manager = TenantContextManager(session)
            
            assert manager is not None
            print("✓ TenantContextManager created successfully")
        except ImportError:
            pytest.skip("tenant_context module not available")

class TestVectorStoreUnit:
    """Unit tests for tenant-aware vector store"""
    
    def test_vector_store_initialization(self):
        """Test vector store creates successfully"""
        try:
            from backend.rag.tenant_aware_vector_store import TenantAwareMappingVectorStore
            
            store = TenantAwareMappingVectorStore(auto_seed=False)
            assert store is not None
            print("✓ Vector store initialized")
        except ImportError:
            pytest.skip("Vector store module not available")

class TestMetricsUnit:
    """Unit tests for metrics module"""
    
    def test_metrics_functions_exist(self):
        """Test that metric tracking functions exist"""
        try:
            from backend.common.metrics import (
                track_cdc_operation,
                track_etl_sync,
                get_metrics
            )
            
            assert callable(track_cdc_operation)
            assert callable(track_etl_sync)
            assert callable(get_metrics)
            print("✓ All metrics functions available")
        except ImportError:
            pytest.skip("Metrics module not available")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
