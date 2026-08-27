"""
Setup Central FHIR Database
Creates tables for storing FHIR resources from all 5 hospital databases
"""
import psycopg2
from datetime import datetime

print("=" * 80)
print("Central FHIR Database - Setup")
print("=" * 80)

# Connect to central database
print("\n[1/3] Connecting to central FHIR database...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5433,  # Central DB is on port 5433
        database='carelock_shared',
        user='shared_user',
        password='shared_pass'
    )
    conn.autocommit = True
    cursor = conn.cursor()
    print("  [OK] Connected to central FHIR database")
except Exception as e:
    print(f"  [ERROR] {e}")
    exit(1)

# Create tables
print("\n[2/3] Creating FHIR resource tables...")
try:
    # Patients table (FHIR Patient resource)
    cursor.execute("""
        DROP TABLE IF EXISTS patients CASCADE;
        CREATE TABLE patients (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            source_database VARCHAR(50) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            medical_record_number VARCHAR(50),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            date_of_birth DATE,
            gender VARCHAR(20),
            blood_type VARCHAR(5),
            phone_number VARCHAR(20),
            email VARCHAR(100),
            address_line1 VARCHAR(200),
            address_city VARCHAR(100),
            address_state VARCHAR(50),
            address_zip VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, source_database, source_id)
        );
    """)
    
    # Encounters table (FHIR Encounter resource)
    cursor.execute("""
        DROP TABLE IF EXISTS encounters CASCADE;
        CREATE TABLE encounters (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            source_database VARCHAR(50) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            patient_id INTEGER REFERENCES patients(id),
            encounter_type VARCHAR(100),
            admission_date TIMESTAMP,
            discharge_date TIMESTAMP,
            department VARCHAR(100),
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, source_database, source_id)
        );
    """)
    
    # Lab Results table (FHIR Observation resource)
    cursor.execute("""
        DROP TABLE IF EXISTS lab_results CASCADE;
        CREATE TABLE lab_results (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            source_database VARCHAR(50) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            patient_id INTEGER REFERENCES patients(id),
            encounter_id INTEGER REFERENCES encounters(id),
            test_name VARCHAR(200),
            test_code VARCHAR(50),
            result_value VARCHAR(500),
            result_unit VARCHAR(50),
            reference_range VARCHAR(100),
            performed_date TIMESTAMP,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, source_database, source_id)
        );
    """)
    
    # Create indexes for performance
    cursor.execute("""
        CREATE INDEX idx_patients_tenant ON patients(tenant_id);
        CREATE INDEX idx_patients_source ON patients(source_database);
        CREATE INDEX idx_encounters_tenant ON encounters(tenant_id);
        CREATE INDEX idx_encounters_patient ON encounters(patient_id);
        CREATE INDEX idx_lab_results_patient ON lab_results(patient_id);
    """)
    
    print("  [OK] Tables created: patients, encounters, lab_results")
    print("  [OK] Indexes created")
    
except Exception as e:
    print(f"  [ERROR] {e}")
    exit(1)

# Show summary
print("\n[3/3] Database ready")
try:
    cursor.execute("SELECT COUNT(*) FROM patients")
    patient_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM encounters")
    encounter_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM lab_results")
    lab_count = cursor.fetchone()[0]
    
    print(f"  [OK] Current data:")
    print(f"       Patients: {patient_count}")
    print(f"       Encounters: {encounter_count}")
    print(f"       Lab Results: {lab_count}")
    
except Exception as e:
    print(f"  [WARN] {e}")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("Central FHIR Database Setup COMPLETE")
print("=" * 80)
print(f"\nConnection: postgresql://shared_user:shared_pass@localhost:5433/carelock_shared")
print("\nThis database will receive synchronized data from all 5 hospital databases")
print("=" * 80)
