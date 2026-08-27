"""
Complete PostgreSQL Hospital Database Setup with Sample Data
Includes: Schema, tables, sample data, CDC triggers
"""
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
import random
from faker import Faker

fake = Faker()

print("=" * 80)
print("PostgreSQL Hospital Database - Complete Setup")
print("=" * 80)

try:
    # Connect to PostgreSQL
    print("\n[1/7] Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db"
    )
    conn.autocommit = True
    cursor = conn.cursor()
    print("  [OK] Connected to PostgreSQL")
    
    # Drop existing tables
    print("\n[2/7] Dropping existing tables...")
    cursor.execute("""
        DROP TABLE IF EXISTS medications CASCADE;
        DROP TABLE IF EXISTS lab_results CASCADE;
        DROP TABLE IF EXISTS encounters CASCADE;
        DROP TABLE IF EXISTS patients CASCADE;
        DROP TABLE IF EXISTS data_change_log CASCADE;
        DROP FUNCTION IF EXISTS log_table_changes() CASCADE;
    """)
    print("  [OK] Tables dropped")
    
    # Create tables
    print("\n[3/7] Creating tables...")
    cursor.execute("""
        CREATE TABLE patients (
            patient_id SERIAL PRIMARY KEY,
            medical_record_number VARCHAR(50) UNIQUE NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE encounters (
            encounter_id SERIAL PRIMARY KEY,
            patient_id INTEGER REFERENCES patients(patient_id),
            encounter_type VARCHAR(50),
            admission_date TIMESTAMP,
            discharge_date TIMESTAMP,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE lab_results (
            lab_result_id SERIAL PRIMARY KEY,
            encounter_id INTEGER REFERENCES encounters(encounter_id),
            patient_id INTEGER REFERENCES patients(patient_id),
            test_name VARCHAR(200),
            result_value VARCHAR(100),
            unit VARCHAR(50),
            reference_range VARCHAR(100),
            status VARCHAR(50),
            performed_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE medications (
            medication_id SERIAL PRIMARY KEY,
            encounter_id INTEGER REFERENCES encounters(encounter_id),
            patient_id INTEGER REFERENCES patients(patient_id),
            medication_name VARCHAR(200),
            dosage VARCHAR(100),
            frequency VARCHAR(100),
            route VARCHAR(50),
            start_date DATE,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE data_change_log (
            change_id BIGSERIAL PRIMARY KEY,
            table_name VARCHAR(100) NOT NULL,
            operation VARCHAR(10) NOT NULL,
            record_id INTEGER,
            old_data TEXT,
            new_data TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_change_log_table ON data_change_log(table_name);
        CREATE INDEX idx_change_log_id ON data_change_log(change_id);
    """)
    print("  [OK] Tables created: patients, encounters, lab_results, medications, data_change_log")
    
    # Insert sample patients
    print("\n[4/7] Inserting sample patients...")
    blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    genders = ['male', 'female', 'other']
    
    patients = []
    for i in range(500):
        dob = fake.date_of_birth(minimum_age=18, maximum_age=90)
        patient = (
            f'MRN-PG-{i+1:05d}',
            fake.first_name(),
            fake.last_name(),
            dob,
            random.choice(genders),
            random.choice(blood_types),
            fake.phone_number()[:20],
            fake.email(),
            fake.street_address(),
            fake.city(),
            fake.state_abbr(),
            fake.zipcode()
        )
        patients.append(patient)
    
    cursor.executemany("""
        INSERT INTO patients (
            medical_record_number, first_name, last_name, date_of_birth,
            gender, blood_type, phone_number, email,
            address_line1, address_city, address_state, address_zip
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, patients)
    print(f"  [OK] Inserted 500 patients")
    
    # Get patient IDs
    cursor.execute("SELECT patient_id FROM patients")
    patient_ids = [row[0] for row in cursor.fetchall()]
    
    # Insert encounters
    print("\n[5/7] Inserting sample encounters...")
    encounter_types = ['Emergency', 'Outpatient', 'Inpatient', 'Observation']
    statuses = ['in-progress', 'finished', 'planned']
    
    encounters = []
    for i in range(1000):
        patient_id = random.choice(patient_ids)
        admission = fake.date_time_between(start_date='-1y', end_date='now')
        discharge = admission + timedelta(days=random.randint(1, 7))
        
        encounter = (
            patient_id,
            random.choice(encounter_types),
            admission,
            discharge,
            random.choice(statuses)
        )
        encounters.append(encounter)
    
    cursor.executemany("""
        INSERT INTO encounters (
            patient_id, encounter_type, admission_date, discharge_date, status
        ) VALUES (%s, %s, %s, %s, %s)
    """, encounters)
    print(f"  [OK] Inserted 1000 encounters")
    
    # Get encounter IDs
    cursor.execute("SELECT encounter_id, patient_id FROM encounters")
    encounter_data = cursor.fetchall()
    
    # Insert lab results
    print("\n[6/7] Inserting sample lab results...")
    lab_tests = [
        ('Hemoglobin', '12-16', 'g/dL'),
        ('White Blood Cell Count', '4000-11000', 'cells/uL'),
        ('Glucose', '70-100', 'mg/dL'),
        ('Creatinine', '0.7-1.3', 'mg/dL'),
        ('ALT', '7-56', 'U/L')
    ]
    
    lab_results = []
    for i in range(2000):
        enc_id, pat_id = random.choice(encounter_data)
        test_name, ref_range, unit = random.choice(lab_tests)
        
        lab_result = (
            enc_id,
            pat_id,
            test_name,
            f'{random.uniform(5, 20):.2f}',
            unit,
            ref_range,
            random.choice(['final', 'preliminary']),
            fake.date_time_between(start_date='-1y', end_date='now')
        )
        lab_results.append(lab_result)
    
    cursor.executemany("""
        INSERT INTO lab_results (
            encounter_id, patient_id, test_name, result_value,
            unit, reference_range, status, performed_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, lab_results)
    print(f"  [OK] Inserted 2000 lab results")
    
    # Insert medications
    medications_list = [
        'Aspirin 81mg', 'Lisinopril 10mg', 'Metformin 500mg',
        'Atorvastatin 20mg', 'Levothyroxine 50mcg'
    ]
    routes = ['oral', 'IV', 'IM']
    
    medications = []
    for i in range(1500):
        enc_id, pat_id = random.choice(encounter_data)
        start_date = fake.date_between(start_date='-1y', end_date='now')
        
        medication = (
            enc_id,
            pat_id,
            random.choice(medications_list),
            f'{random.randint(1, 4)} tablet(s)',
            f'{random.randint(1, 3)} times daily',
            random.choice(routes),
            start_date,
            'active'
        )
        medications.append(medication)
    
    cursor.executemany("""
        INSERT INTO medications (
            encounter_id, patient_id, medication_name, dosage,
            frequency, route, start_date, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, medications)
    print(f"  [OK] Inserted 1500 medications")
    
    # Create CDC function and triggers
    print("\n[7/7] Creating CDC triggers...")
    cursor.execute("""
        CREATE OR REPLACE FUNCTION log_table_changes()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO data_change_log (table_name, operation, record_id, new_data)
                VALUES (TG_TABLE_NAME, 'INSERT', NEW.patient_id, row_to_json(NEW)::text);
            ELSIF TG_OP = 'UPDATE' THEN
                INSERT INTO data_change_log (table_name, operation, record_id, old_data, new_data)
                VALUES (TG_TABLE_NAME, 'UPDATE', NEW.patient_id, row_to_json(OLD)::text, row_to_json(NEW)::text);
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO data_change_log (table_name, operation, record_id, old_data)
                VALUES (TG_TABLE_NAME, 'DELETE', OLD.patient_id, row_to_json(OLD)::text);
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    tables = ['patients', 'encounters', 'lab_results', 'medications']
    for table in tables:
        cursor.execute(f"""
            DROP TRIGGER IF EXISTS {table}_change_trigger ON {table};
            CREATE TRIGGER {table}_change_trigger
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION log_table_changes();
        """)
        print(f"  [OK] CDC triggers created for: {table}")
    
    # Summary
    cursor.execute("SELECT COUNT(*) FROM patients")
    patient_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM encounters")
    encounter_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM lab_results")
    lab_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM medications")
    med_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM data_change_log")
    log_count = cursor.fetchone()[0]
    
    print("\n" + "=" * 80)
    print("PostgreSQL Database Setup COMPLETE")
    print("=" * 80)
    print(f"  Patients      : {patient_count}")
    print(f"  Encounters    : {encounter_count}")
    print(f"  Lab Results   : {lab_count}")
    print(f"  Medications   : {med_count}")
    print(f"  Change Log    : {log_count} entries")
    print("\nConnection: postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db")
    print("=" * 80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
