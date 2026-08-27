"""
Generate synthetic patient data for CareLock Sync
This script creates realistic hospital data for testing and development.
"""

import random
from datetime import datetime, timedelta
from faker import Faker
import psycopg2
from psycopg2.extras import execute_batch

# Initialize Faker
fake = Faker()

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'hospital_db',
    'user': 'hospital_user',
    'password': 'hospital_pass'
}

# Constants
NUM_PATIENTS = 500
BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
GENDERS = ['Male', 'Female', 'Other']
ENCOUNTER_TYPES = ['inpatient', 'outpatient', 'emergency']
DEPARTMENTS = ['Cardiology', 'Neurology', 'Orthopedics', 'Pediatrics', 'Emergency', 'Surgery']
STATUSES = ['active', 'discharged', 'transferred']

# Common lab tests
LAB_TESTS = [
    ('CBC', 'Complete Blood Count', '4.5-11.0', '10^3/μL'),
    ('HGB', 'Hemoglobin', '13.5-17.5', 'g/dL'),
    ('GLU', 'Glucose', '70-100', 'mg/dL'),
    ('CREAT', 'Creatinine', '0.7-1.3', 'mg/dL'),
    ('NA', 'Sodium', '135-145', 'mEq/L'),
    ('K', 'Potassium', '3.5-5.0', 'mEq/L'),
    ('ALT', 'Alanine Aminotransferase', '7-56', 'U/L'),
    ('AST', 'Aspartate Aminotransferase', '10-40', 'U/L'),
]

# Common medications
MEDICATIONS = [
    ('Lisinopril', '10mg', 'Once daily', 'oral'),
    ('Metformin', '500mg', 'Twice daily', 'oral'),
    ('Atorvastatin', '20mg', 'Once daily', 'oral'),
    ('Amlodipine', '5mg', 'Once daily', 'oral'),
    ('Omeprazole', '20mg', 'Once daily', 'oral'),
    ('Levothyroxine', '50mcg', 'Once daily', 'oral'),
    ('Aspirin', '81mg', 'Once daily', 'oral'),
    ('Gabapentin', '300mg', 'Three times daily', 'oral'),
]


def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


def generate_patients(num_patients):
    """Generate synthetic patient records"""
    patients = []
    for i in range(num_patients):
        patient = (
            f"MRN{str(i+1).zfill(6)}",  # medical_record_number
            fake.first_name(),
            fake.last_name(),
            fake.date_of_birth(minimum_age=1, maximum_age=90),
            random.choice(GENDERS),
            random.choice(BLOOD_TYPES),
            fake.phone_number()[:20],
            fake.email(),
            fake.street_address(),
            fake.secondary_address() if random.random() > 0.5 else None,
            fake.city(),
            fake.state_abbr(),
            fake.zipcode(),
            fake.name(),
            fake.phone_number()[:20],
        )
        patients.append(patient)
    return patients


def generate_encounters(patient_ids, num_encounters_per_patient=2):
    """Generate synthetic encounter records"""
    encounters = []
    for patient_id in patient_ids:
        num_encounters = random.randint(1, num_encounters_per_patient)
        for _ in range(num_encounters):
            admission_date = fake.date_time_between(start_date='-2y', end_date='now')
            encounter_type = random.choice(ENCOUNTER_TYPES)
            
            # Calculate discharge date (if applicable)
            if encounter_type == 'inpatient':
                discharge_date = admission_date + timedelta(days=random.randint(1, 14))
                status = random.choice(['discharged', 'active'])
            elif encounter_type == 'emergency':
                discharge_date = admission_date + timedelta(hours=random.randint(2, 24))
                status = 'discharged'
            else:  # outpatient
                discharge_date = admission_date + timedelta(hours=random.randint(1, 4))
                status = 'discharged'
            
            encounter = (
                patient_id,
                encounter_type,
                admission_date,
                discharge_date if status == 'discharged' else None,
                fake.sentence(nb_words=6),
                fake.sentence(nb_words=10),
                fake.name(),
                random.choice(DEPARTMENTS),
                f"{random.randint(1, 5)}{random.choice(['A', 'B', 'C'])}{random.randint(1, 20)}" if encounter_type == 'inpatient' else None,
                status,
            )
            encounters.append(encounter)
    return encounters


def generate_lab_results(encounter_ids, patient_encounter_map, num_labs_per_encounter=3):
    """Generate synthetic lab result records"""
    lab_results = []
    for encounter_id in encounter_ids:
        patient_id = patient_encounter_map[encounter_id]
        num_labs = random.randint(1, num_labs_per_encounter)
        
        for _ in range(num_labs):
            test_code, test_name, ref_range, unit = random.choice(LAB_TESTS)
            
            # Generate a result value within or slightly outside reference range
            range_parts = ref_range.split('-')
            if len(range_parts) == 2:
                min_val = float(range_parts[0])
                max_val = float(range_parts[1])
                
                # 80% normal, 20% abnormal
                if random.random() > 0.2:
                    result_value = round(random.uniform(min_val, max_val), 2)
                    abnormal_flag = 'normal'
                else:
                    if random.random() > 0.5:
                        result_value = round(random.uniform(max_val, max_val * 1.5), 2)
                        abnormal_flag = 'high'
                    else:
                        result_value = round(random.uniform(min_val * 0.5, min_val), 2)
                        abnormal_flag = 'low'
            else:
                result_value = round(random.uniform(50, 150), 2)
                abnormal_flag = 'normal'
            
            performed_date = fake.date_time_between(start_date='-1y', end_date='now')
            result_date = performed_date + timedelta(hours=random.randint(2, 48))
            
            lab_result = (
                encounter_id,
                patient_id,
                test_name,
                test_code,
                str(result_value),
                unit,
                ref_range,
                abnormal_flag,
                performed_date,
                result_date,
                f"{fake.company()} Laboratory",
                fake.name(),
            )
            lab_results.append(lab_result)
    return lab_results


def generate_medications(encounter_ids, patient_encounter_map, num_meds_per_encounter=2):
    """Generate synthetic medication records"""
    medications = []
    for encounter_id in encounter_ids:
        patient_id = patient_encounter_map[encounter_id]
        num_meds = random.randint(0, num_meds_per_encounter)
        
        for _ in range(num_meds):
            med_name, dosage, frequency, route = random.choice(MEDICATIONS)
            
            start_date = fake.date_between(start_date='-1y', end_date='today')
            
            # 60% active, 40% completed
            if random.random() > 0.4:
                end_date = None
                status = 'active'
            else:
                end_date = start_date + timedelta(days=random.randint(7, 90))
                status = 'completed'
            
            medication = (
                encounter_id,
                patient_id,
                med_name,
                dosage,
                frequency,
                route,
                start_date,
                end_date,
                fake.name(),
                fake.sentence(nb_words=8) if random.random() > 0.7 else None,
                status,
            )
            medications.append(medication)
    return medications


def main():
    """Main function to generate and insert data"""
    print("=" * 60)
    print("CareLock Sync - Synthetic Data Generator")
    print("=" * 60)
    
    # Connect to database
    print("\n[1/5] Connecting to database...")
    conn = connect_db()
    if not conn:
        print("Failed to connect to database. Exiting.")
        return
    
    cursor = conn.cursor()
    print("[OK] Connected successfully")
    
    try:
        # Generate and insert patients
        print(f"\n[2/5] Generating {NUM_PATIENTS} patients...")
        patients = generate_patients(NUM_PATIENTS)
        
        patient_query = """
            INSERT INTO patients (
                medical_record_number, first_name, last_name, date_of_birth,
                gender, blood_type, phone_number, email, address_line1,
                address_line2, city, state, zip_code, emergency_contact_name,
                emergency_contact_phone
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING patient_id
        """
        
        execute_batch(cursor, patient_query, patients)
        conn.commit()
        
        # Get patient IDs
        cursor.execute("SELECT patient_id FROM patients ORDER BY patient_id")
        patient_ids = [row[0] for row in cursor.fetchall()]
        print(f"[OK] Inserted {len(patient_ids)} patients")
        
        # Generate and insert encounters
        print(f"\n[3/5] Generating encounters...")
        encounters = generate_encounters(patient_ids, num_encounters_per_patient=3)
        
        encounter_query = """
            INSERT INTO encounters (
                patient_id, encounter_type, admission_date, discharge_date,
                chief_complaint, diagnosis, attending_physician, department,
                room_number, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING encounter_id, patient_id
        """
        
        execute_batch(cursor, encounter_query, encounters)
        conn.commit()
        
        # Get encounter IDs and map to patient IDs
        cursor.execute("SELECT encounter_id, patient_id FROM encounters ORDER BY encounter_id")
        encounter_data = cursor.fetchall()
        encounter_ids = [row[0] for row in encounter_data]
        patient_encounter_map = {row[0]: row[1] for row in encounter_data}
        print(f"[OK] Inserted {len(encounter_ids)} encounters")
        
        # Generate and insert lab results
        print(f"\n[4/5] Generating lab results...")
        lab_results = generate_lab_results(encounter_ids, patient_encounter_map, num_labs_per_encounter=5)
        
        lab_query = """
            INSERT INTO lab_results (
                encounter_id, patient_id, test_name, test_code, result_value,
                result_unit, reference_range, abnormal_flag, performed_date,
                result_date, performing_lab, technician_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        execute_batch(cursor, lab_query, lab_results)
        conn.commit()
        print(f"[OK] Inserted {len(lab_results)} lab results")
        
        # Generate and insert medications
        print(f"\n[5/5] Generating medications...")
        medications = generate_medications(encounter_ids, patient_encounter_map, num_meds_per_encounter=3)
        
        medication_query = """
            INSERT INTO medications (
                encounter_id, patient_id, medication_name, dosage, frequency,
                route, start_date, end_date, prescribing_physician,
                pharmacy_notes, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        execute_batch(cursor, medication_query, medications)
        conn.commit()
        print(f"[OK] Inserted {len(medications)} medications")
        
        # Display summary
        print("\n" + "=" * 60)
        print("Data Generation Complete!")
        print("=" * 60)
        
        cursor.execute("SELECT COUNT(*) FROM patients")
        print(f"Total Patients: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM encounters")
        print(f"Total Encounters: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM lab_results")
        print(f"Total Lab Results: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM medications")
        print(f"Total Medications: {cursor.fetchone()[0]}")
        
        print("\n[OK] Database is ready for testing!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()
