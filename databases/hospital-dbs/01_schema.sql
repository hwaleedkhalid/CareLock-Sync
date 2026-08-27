-- Hospital Database Schema - Version 1 (City General Hospital)
-- This represents a typical hospital's database structure

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS medications CASCADE;
DROP TABLE IF EXISTS lab_results CASCADE;
DROP TABLE IF EXISTS encounters CASCADE;
DROP TABLE IF EXISTS patients CASCADE;

-- Patients table
CREATE TABLE patients (
    patient_id SERIAL PRIMARY KEY,
    medical_record_number VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    blood_type VARCHAR(10),
    phone_number VARCHAR(20),
    email VARCHAR(100),
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    emergency_contact_name VARCHAR(200),
    emergency_contact_phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Encounters table (hospital visits)
CREATE TABLE encounters (
    encounter_id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    encounter_type VARCHAR(50) NOT NULL, -- 'inpatient', 'outpatient', 'emergency'
    admission_date TIMESTAMP NOT NULL,
    discharge_date TIMESTAMP,
    chief_complaint TEXT,
    diagnosis TEXT,
    attending_physician VARCHAR(200),
    department VARCHAR(100),
    room_number VARCHAR(20),
    status VARCHAR(50), -- 'active', 'discharged', 'transferred'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lab Results table
CREATE TABLE lab_results (
    lab_id SERIAL PRIMARY KEY,
    encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    test_name VARCHAR(200) NOT NULL,
    test_code VARCHAR(50),
    result_value VARCHAR(200),
    result_unit VARCHAR(50),
    reference_range VARCHAR(100),
    abnormal_flag VARCHAR(20), -- 'normal', 'high', 'low', 'critical'
    performed_date TIMESTAMP NOT NULL,
    result_date TIMESTAMP,
    performing_lab VARCHAR(200),
    technician_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Medications table
CREATE TABLE medications (
    medication_id SERIAL PRIMARY KEY,
    encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
    medication_name VARCHAR(200) NOT NULL,
    dosage VARCHAR(100),
    frequency VARCHAR(100),
    route VARCHAR(50), -- 'oral', 'IV', 'injection', etc.
    start_date DATE NOT NULL,
    end_date DATE,
    prescribing_physician VARCHAR(200),
    pharmacy_notes TEXT,
    status VARCHAR(50), -- 'active', 'completed', 'discontinued'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_patients_mrn ON patients(medical_record_number);
CREATE INDEX idx_patients_name ON patients(last_name, first_name);
CREATE INDEX idx_encounters_patient ON encounters(patient_id);
CREATE INDEX idx_encounters_date ON encounters(admission_date);
CREATE INDEX idx_lab_patient ON lab_results(patient_id);
CREATE INDEX idx_lab_encounter ON lab_results(encounter_id);
CREATE INDEX idx_medications_patient ON medications(patient_id);
CREATE INDEX idx_medications_encounter ON medications(encounter_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hospital_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hospital_user;
