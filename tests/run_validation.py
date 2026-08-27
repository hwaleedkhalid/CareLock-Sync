"""
Simple Test Runner for CareLock Sync
Validates core functionality
"""
import sys
import os

# Setup paths
project_root = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_dir)

# Now imports should work
from common.database import hospital_db_session, shared_db_session
from common.models import Patient, Encounter, LabResult
from sqlalchemy import text


def test_database_connectivity():
    """Test database connections"""
    print("\n[1/8] Testing Database Connectivity...")
    
    try:
        with hospital_db_session() as db:
            db.execute(text("SELECT 1"))
        print("  ✓ Hospital database connected")
        
        with shared_db_session() as db:
            db.execute(text("SELECT 1"))
        print("  ✓ Shared database connected")
        
        return True
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        return False


def test_hospital_data_exists():
    """Test that hospital database has data"""
    print("\n[2/8] Testing Hospital Data...")
    
    try:
        with hospital_db_session() as db:
            patient_count = db.query(Patient).count()
            encounter_count = db.query(Encounter).count()
            lab_count = db.query(LabResult).count()
            
            print(f"  ✓ Patients: {patient_count}")
            print(f"  ✓ Encounters: {encounter_count}")
            print(f"  ✓ Lab Results: {lab_count}")
            
            return patient_count > 0
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_cdc_setup():
    """Test CDC is configured"""
    print("\n[3/8] Testing CDC Setup...")
    
    try:
        with hospital_db_session() as db:
            # Check change log table exists
            result = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'data_change_log'
            """))
            table_exists = result.scalar() == 1
            
            if table_exists:
                # Check for changes
                result = db.execute(text("SELECT COUNT(*) FROM data_change_log"))
                change_count = result.scalar()
                print(f"  ✓ CDC table exists with {change_count} changes")
                return True
            else:
                print("  ✗ CDC table not found")
                return False
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_fhir_schema_exists():
    """Test FHIR schema in shared database"""
    print("\n[4/8] Testing FHIR Schema...")
    
    try:
        with shared_db_session() as db:
            # Check FHIR tables exist
            tables = ['fhir_patient', 'fhir_encounter', 'fhir_observation', 'fhir_medication_request']
            
            for table in tables:
                result = db.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_name = '{table}'
                """))
                exists = result.scalar() == 1
                
                if exists:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"  ✓ {table}: {count} records")
                else:
                    print(f"  ✗ {table}: not found")
                    return False
            
            return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_synced_data_exists():
    """Test that data has been synced to shared database"""
    print("\n[5/8] Testing Synced Data...")
    
    try:
        with shared_db_session() as db:
            patient_count = db.execute(text(
                "SELECT COUNT(*) FROM fhir_patient WHERE tenant_id = 1"
            )).scalar()
            
            encounter_count = db.execute(text(
                "SELECT COUNT(*) FROM fhir_encounter WHERE tenant_id = 1"
            )).scalar()
            
            print(f"  ✓ Synced Patients: {patient_count}")
            print(f"  ✓ Synced Encounters: {encounter_count}")
            
            return patient_count > 0
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_data_integrity():
    """Test referential integrity"""
    print("\n[6/8] Testing Data Integrity...")
    
    try:
        with shared_db_session() as db:
            # Check for orphaned encounters
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
            orphaned = result.scalar()
            
            if orphaned == 0:
                print("  ✓ No orphaned encounters")
                return True
            else:
                print(f"  ✗ Found {orphaned} orphaned encounters")
                return False
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_fhir_data_validity():
    """Test FHIR data is valid"""
    print("\n[7/8] Testing FHIR Data Validity...")
    
    try:
        with shared_db_session() as db:
            # Check patients have required fields
            result = db.execute(text("""
                SELECT COUNT(*) FROM fhir_patient
                WHERE tenant_id = 1
                AND (family_name IS NULL OR given_name IS NULL OR birth_date IS NULL)
            """))
            invalid_patients = result.scalar()
            
            if invalid_patients == 0:
                print("  ✓ All patients have required FHIR fields")
            else:
                print(f"  ⚠ {invalid_patients} patients missing required fields")
            
            # Check sample patient data
            result = db.execute(text("""
                SELECT family_name, given_name[1], gender, birth_date
                FROM fhir_patient
                WHERE tenant_id = 1
                LIMIT 1
            """))
            sample = result.fetchone()
            
            if sample:
                print(f"  ✓ Sample: {sample[0]}, {sample[1]}, {sample[2]}, {sample[3]}")
            
            return invalid_patients == 0
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def test_tenant_configuration():
    """Test tenant is configured"""
    print("\n[8/8] Testing Tenant Configuration...")
    
    try:
        with shared_db_session() as db:
            result = db.execute(text("""
                SELECT hospital_name, hospital_code
                FROM hospital_tenants
                WHERE tenant_id = 1
            """))
            tenant = result.fetchone()
            
            if tenant:
                print(f"  ✓ Tenant: {tenant[0]} ({tenant[1]})")
                return True
            else:
                print("  ✗ Tenant not configured")
                return False
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def run_all_tests():
    """Run all validation tests"""
    print("=" * 70)
    print("CareLock Sync - Validation Test Suite")
    print("=" * 70)
    
    tests = [
        test_database_connectivity,
        test_hospital_data_exists,
        test_cdc_setup,
        test_fhir_schema_exists,
        test_synced_data_exists,
        test_data_integrity,
        test_fhir_data_validity,
        test_tenant_configuration
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n  ✗ Test crashed: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for production.")
        return True
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Review above for details.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
