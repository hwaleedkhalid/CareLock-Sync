-- Shared Central Database Schema (FHIR R4 Compliant)
-- This is the standardized database that aggregates data from all hospitals

-- Drop existing tables
DROP TABLE IF EXISTS fhir_medication_request CASCADE;
DROP TABLE IF EXISTS fhir_observation CASCADE;
DROP TABLE IF EXISTS fhir_encounter CASCADE;
DROP TABLE IF EXISTS fhir_patient CASCADE;
DROP TABLE IF EXISTS hospital_tenants CASCADE;

-- Hospital Tenants table (for multi-tenancy)
CREATE TABLE hospital_tenants (
    tenant_id SERIAL PRIMARY KEY,
    hospital_name VARCHAR(200) NOT NULL,
    hospital_code VARCHAR(50) UNIQUE NOT NULL,
    hospital_address TEXT,
    contact_email VARCHAR(100),
    contact_phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    onboarded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FHIR Patient Resource
CREATE TABLE fhir_patient (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES hospital_tenants(tenant_id),
    source_patient_id VARCHAR(100) NOT NULL, -- Original patient ID from hospital
    identifier_system VARCHAR(200), -- e.g., "http://hospital.org/patients"
    identifier_value VARCHAR(100), -- Medical record number
    family_name VARCHAR(100),
    given_name VARCHAR(100)[], -- Array for multiple given names
    gender VARCHAR(20), -- male, female, other, unknown
    birth_date DATE,
    phone VARCHAR(20),
    email VARCHAR(100),
    address_line TEXT[], -- Array for address lines
    address_city VARCHAR(100),
    address_state VARCHAR(50),
    address_postal_code VARCHAR(20),
    address_country VARCHAR(50),
    active BOOLEAN DEFAULT TRUE,
    deceased BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, source_patient_id)
);

-- FHIR Encounter Resource
CREATE TABLE fhir_encounter (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES hospital_tenants(tenant_id),
    patient_id INTEGER NOT NULL REFERENCES fhir_patient(id),
    source_encounter_id VARCHAR(100) NOT NULL,
    identifier_system VARCHAR(200),
    identifier_value VARCHAR(100),
    status VARCHAR(50), -- planned, arrived, in-progress, finished, cancelled
    class_code VARCHAR(50), -- IMP (inpatient), AMB (ambulatory), EMER (emergency)
    type_code VARCHAR(100),
    type_display VARCHAR(200),
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    reason_code VARCHAR(100)[],
    reason_display TEXT[],
    diagnosis TEXT[],
    hospitalization_admit_source VARCHAR(100),
    hospitalization_discharge_disposition VARCHAR(100),
    location_name VARCHAR(200),
    participant_practitioner VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, source_encounter_id)
);

-- FHIR Observation Resource (Lab Results, Vitals)
CREATE TABLE fhir_observation (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES hospital_tenants(tenant_id),
    patient_id INTEGER NOT NULL REFERENCES fhir_patient(id),
    encounter_id INTEGER REFERENCES fhir_encounter(id),
    source_observation_id VARCHAR(100),
    identifier_system VARCHAR(200),
    identifier_value VARCHAR(100),
    status VARCHAR(50), -- registered, preliminary, final, amended
    category_code VARCHAR(100), -- laboratory, vital-signs, imaging, etc.
    category_display VARCHAR(200),
    code_system VARCHAR(200), -- e.g., "http://loinc.org"
    code_value VARCHAR(100), -- LOINC code
    code_display VARCHAR(200), -- Human-readable name
    value_quantity_value DECIMAL(10, 3),
    value_quantity_unit VARCHAR(50),
    value_quantity_system VARCHAR(200),
    value_string TEXT,
    interpretation_code VARCHAR(50), -- N (normal), H (high), L (low), etc.
    interpretation_display VARCHAR(100),
    reference_range_low DECIMAL(10, 3),
    reference_range_high DECIMAL(10, 3),
    reference_range_text VARCHAR(200),
    effective_datetime TIMESTAMP,
    issued_datetime TIMESTAMP,
    performer_reference VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FHIR MedicationRequest Resource
CREATE TABLE fhir_medication_request (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES hospital_tenants(tenant_id),
    patient_id INTEGER NOT NULL REFERENCES fhir_patient(id),
    encounter_id INTEGER REFERENCES fhir_encounter(id),
    source_medication_id VARCHAR(100),
    identifier_system VARCHAR(200),
    identifier_value VARCHAR(100),
    status VARCHAR(50), -- active, on-hold, cancelled, completed
    intent VARCHAR(50), -- proposal, plan, order, instance-order
    medication_code_system VARCHAR(200), -- e.g., "http://www.nlm.nih.gov/research/umls/rxnorm"
    medication_code_value VARCHAR(100), -- RxNorm code
    medication_code_display VARCHAR(200), -- Medication name
    dosage_text VARCHAR(500),
    dosage_route_code VARCHAR(50),
    dosage_route_display VARCHAR(100),
    dosage_dose_value DECIMAL(10, 3),
    dosage_dose_unit VARCHAR(50),
    dosage_frequency_code VARCHAR(50),
    dosage_frequency_display VARCHAR(100),
    authored_on TIMESTAMP,
    requester_reference VARCHAR(200),
    dispensation_validity_period_start DATE,
    dispensation_validity_period_end DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_fhir_patient_tenant ON fhir_patient(tenant_id);
CREATE INDEX idx_fhir_patient_identifier ON fhir_patient(identifier_value);
CREATE INDEX idx_fhir_patient_name ON fhir_patient(family_name, given_name);

CREATE INDEX idx_fhir_encounter_tenant ON fhir_encounter(tenant_id);
CREATE INDEX idx_fhir_encounter_patient ON fhir_encounter(patient_id);
CREATE INDEX idx_fhir_encounter_period ON fhir_encounter(period_start, period_end);

CREATE INDEX idx_fhir_observation_tenant ON fhir_observation(tenant_id);
CREATE INDEX idx_fhir_observation_patient ON fhir_observation(patient_id);
CREATE INDEX idx_fhir_observation_encounter ON fhir_observation(encounter_id);
CREATE INDEX idx_fhir_observation_code ON fhir_observation(code_value);
CREATE INDEX idx_fhir_observation_date ON fhir_observation(effective_datetime);

CREATE INDEX idx_fhir_medication_tenant ON fhir_medication_request(tenant_id);
CREATE INDEX idx_fhir_medication_patient ON fhir_medication_request(patient_id);
CREATE INDEX idx_fhir_medication_encounter ON fhir_medication_request(encounter_id);

-- Insert initial tenant (City General Hospital)
INSERT INTO hospital_tenants (
    hospital_name,
    hospital_code,
    hospital_address,
    contact_email,
    contact_phone,
    is_active
) VALUES (
    'City General Hospital',
    'CGH001',
    '123 Medical Center Drive, Healthcare City, HC 12345',
    'admin@citygeneralhospital.com',
    '555-0100',
    TRUE
);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO shared_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO shared_user;
