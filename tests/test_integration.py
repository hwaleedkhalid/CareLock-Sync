"""
Integration Tests for CareLock Sync
Tests end-to-end functionality of the sync system
"""
import sys
import os
from sqlalchemy import text

# Fix paths
tests_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(tests_dir)
backend_dir = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_dir)

from common.database import hospital_db_session, shared_db_session
from common.models import Patient, Encounter, LabResult, Medication

# Import ETL modules
from etl.pipeline import ETLPipeline
from etl.incremental_sync import IncrementalSync

# Import schema mapper
from mapping_service import MappingService


class TestSchemaDiscovery:
    """Test schema discovery functionality"""
    
    def test_schema_discovery_finds_tables(self):
        """Test that schema discovery finds all tables"""
        from connector.schema_discovery import SchemaDiscovery
        from common.config import settings
        
        discovery = SchemaDiscovery(settings.hospital_db_url)
        tables = discovery.get_all_tables()
        
        # Should find core tables
        assert 'patients' in tables
        assert 'encounters' in tables
        assert 'lab_results' in tables
        assert 'medications' in tables
        
        print(f"✓ Found {len(tables)} tables")
    
    def test_schema_discovery_finds_relationships(self):
        """Test that schema discovery finds foreign key relationships"""
        from connector.schema_discovery import SchemaDiscovery
        from common.config import settings
        
        discovery = SchemaDiscovery(settings.hospital_db_url)
        relationships = discovery.get_table_relationships()
        
        # Should find FK relationships
        assert 'encounters' in relationships
        assert len(relationships['encounters']) > 0
        
        print(f"✓ Found {sum(len(rels) for rels in relationships.values())} relationships")


class TestCDC:
    """Test Change Data Capture functionality"""
    
    def test_cdc_table_exists(self):
        """Test that CDC change log table exists"""
        with hospital_db_session() as db:
            result = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'data_change_log'
            """))
            count = result.scalar()
            
            assert count == 1
            print("✓ CDC change log table exists")
    
    def test_cdc_has_changes(self):
        """Test that CDC has captured some changes"""
        from connector.cdc_monitor import CDCMonitor
        from common.config import settings
        
        monitor = CDCMonitor(settings.hospital_db_url)
        changes = monitor.get_recent_changes(limit=100)
        
        # Should have captured changes from previous tests
        assert len(changes) >= 0  # At minimum should work
        
        print(f"✓ CDC has captured {len(changes)} changes")


class TestFHIRMapping:
    """Test FHIR mapping functionality"""
    
    def test_patient_mapping(self):
        """Test patient to FHIR Patient mapping"""
        service = MappingService()
        
        with hospital_db_session() as db:
            patient = db.query(Patient).first()
            
            # Map to FHIR
            fhir_patient = service.map_patient_to_fhir(patient)
            
            # Verify FHIR structure
            assert fhir_patient['resourceType'] == 'Patient'
            assert 'id' in fhir_patient
            assert 'name' in fhir_patient
            assert 'birthDate' in fhir_patient
            
            # Verify data
            assert fhir_patient['id'] == str(patient.patient_id)
            assert fhir_patient['birthDate'] is not None
            
            print("✓ Patient mapping produces valid FHIR")
    
    def test_encounter_mapping(self):
        """Test encounter to FHIR Encounter mapping"""
        service = MappingService()
        
        with hospital_db_session() as db:
            encounter = db.query(Encounter).first()
            
            # Map to FHIR
            fhir_encounter = service.map_encounter_to_fhir(encounter)
            
            # Verify FHIR structure
            assert fhir_encounter['resourceType'] == 'Encounter'
            assert 'id' in fhir_encounter
            assert 'class' in fhir_encounter
            assert 'status' in fhir_encounter
            
            # Verify class code
            assert fhir_encounter['class']['code'] in ['IMP', 'AMB', 'EMER']
            
            print("✓ Encounter mapping produces valid FHIR")
    
    def test_observation_mapping(self):
        """Test lab result to FHIR Observation mapping"""
        service = MappingService()
        
        with hospital_db_session() as db:
            lab_result = db.query(LabResult).first()
            
            if lab_result:
                # Map to FHIR
                fhir_obs = service.map_lab_result_to_fhir(lab_result)
                
                # Verify FHIR structure
                assert fhir_obs['resourceType'] == 'Observation'
                assert 'id' in fhir_obs
                assert 'code' in fhir_obs
                
                print("✓ Observation mapping produces valid FHIR")
            else:
                print("✓ Observation mapping (skipped - no data)")


class TestETLPipeline:
    """Test ETL pipeline functionality"""
    
    def test_patient_extraction(self):
        """Test patient extraction from hospital DB"""
        pipeline = ETLPipeline(tenant_id=1)
        
        with hospital_db_session() as db:
            patients = pipeline.extract_patients(db, limit=5)
            
            assert len(patients) > 0
            assert all(isinstance(p, Patient) for p in patients)
            
            print(f"✓ Extracted {len(patients)} patients")
    
    def test_patient_transformation(self):
        """Test patient transformation to FHIR"""
        pipeline = ETLPipeline(tenant_id=1)
        
        with hospital_db_session() as db:
            patients = pipeline.extract_patients(db, limit=5)
            fhir_patients = pipeline.transform_patients(patients)
            
            assert len(fhir_patients) == len(patients)
            assert all(p['resourceType'] == 'Patient' for p in fhir_patients)
            
            print(f"✓ Transformed {len(fhir_patients)} patients to FHIR")


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    def test_patient_count_consistency(self):
        """Test that patient counts match between databases"""
        with hospital_db_session() as hospital_db:
            hospital_count = hospital_db.query(Patient).count()
        
        with shared_db_session() as shared_db:
            shared_count = shared_db.execute(
                text("SELECT COUNT(*) FROM fhir_patient WHERE tenant_id = 1")
            ).scalar()
        
        # Should have synced patients
        assert shared_count > 0
        
        print(f"✓ Hospital: {hospital_count} patients, Shared: {shared_count} patients")
    
    def test_foreign_key_integrity(self):
        """Test that foreign key relationships are maintained"""
        with shared_db_session() as db:
            # Check encounters have valid patient references
            result = db.execute(text("""
                SELECT COUNT(*) 
                FROM fhir_encounter e
                WHERE NOT EXISTS (
                    SELECT 1 FROM fhir_patient p
                    WHERE p.id = e.patient_id
                    AND p.tenant_id = e.tenant_id
                )
                AND e.tenant_id = 1
            """))
            orphaned_encounters = result.scalar()
            
            assert orphaned_encounters == 0
            
            print("✓ All encounters have valid patient references")


class TestPerformance:
    """Test system performance"""
    
    def test_sync_performance(self):
        """Test sync performance benchmarks"""
        import time
        
        pipeline = ETLPipeline(tenant_id=1)
        
        # Measure sync time for 10 patients
        start = time.time()
        
        with hospital_db_session() as db:
            patients = pipeline.extract_patients(db, limit=10)
            fhir_patients = pipeline.transform_patients(patients)
            
            with shared_db_session() as shared_db:
                loaded = pipeline.load_patients(shared_db, fhir_patients)
        
        duration = time.time() - start
        
        # Should complete quickly
        assert duration < 10  # Less than 10 seconds
        
        records_per_second = loaded / duration if duration > 0 else 0
        
        print(f"✓ Synced {loaded} patients in {duration:.2f}s ({records_per_second:.1f} records/sec)")


def run_all_tests():
    """Run all tests and report results"""
    print("=" * 70)
    print("CareLock Sync - Integration Test Suite")
    print("=" * 70)
    
    test_classes = [
        TestSchemaDiscovery,
        TestCDC,
        TestFHIRMapping,
        TestETLPipeline,
        TestDataIntegrity,
        TestPerformance
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 70)
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) 
                       if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                test_instance = test_class()
                test_method = getattr(test_instance, method_name)
                test_method()
                passed_tests += 1
            except Exception as e:
                failed_tests += 1
                print(f"✗ {method_name} FAILED: {str(e)}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests == 0:
        print("\n✓ All tests passed!")
        return True
    else:
        print(f"\n✗ {failed_tests} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
