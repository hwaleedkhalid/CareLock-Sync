-- ================================================================
-- CareLock Sync - Shared Central Database Schema (FHIR-Based)
-- This database stores standardized data from multiple hospitals
-- Based on HL7 FHIR R4 standard
-- ================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- ORGANIZATIONS TABLE (Hospitals/Tenants)
-- ================================================================
CREATE TABLE IF NOT EXISTS organizations (
    organization_id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    identifier VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50),
    address JSONB,
    contact JSONB,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
-- FHIR_PATIENTS TABLE (Standardized Patient Data)
-- ================================================================
CREATE TABLE IF NOT EXISTS fhir_patients (
    id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(organization_id),
    
    -- Identifiers (FHIR identifier)
    identifiers JSONB,  -- Array of {system, value, use}
    
    -- Name (FHIR HumanName)
    name JSONB,  -- {use, family, given[], prefix[], suffix[]}
    
    -- Demographics
    gender VARCHAR(20),  -- male | female | other | unknown
    birth_date DATE,
    deceased BOOLEAN DEFAULT FALSE,
    deceased_datetime TIMESTAMP,
    
    -- Contact information (FHIR ContactPoint)
    telecom JSONB,  -- Array of {system, value, use}
    
    -- Address (FHIR Address)
    address JSONB,  -- Array of address objects
    
    -- Marital status
    marital_status VARCHAR(50),
    
    -- Contact persons (emergency contact)
    contact JSONB,  -- Array of contact persons
    
    -- Communication preferences
    communication JSONB,
    
    -- Metadata
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    last_synced_at TIMESTAMP
);

-- ================================================================
-- FHIR_ENCOUNTERS TABLE (Hospital Visits)
-- ================================================================
CREATE TABLE IF NOT EXISTS fhir_encounters (
    id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(organization_id),
    patient_id INTEGER REFERENCES fhir_patients(id) ON DELETE CASCADE,
    
    -- Identifiers
    identifier JSONB,
    
    -- Status: planned | arrived | triaged | in-progress | onleave | finished | cancelled
    status VARCHAR(50) NOT NULL,
    
    -- Class: ambulatory | emergency | inpatient | outpatient
    class VARCHAR(50),
    
    -- Type of encounter
    type JSONB,  -- Array of CodeableConcept
    
    -- Service type
    service_type JSONB,
    
    -- Priority
    priority JSONB,
    
    -- Subject (patient reference)
    subject_reference VARCHAR(200),
    
    -- Period
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    
    -- Length of encounter
    length_minutes INTEGER,
    
    -- Reason for encounter
    reason_code JSONB,  -- Array of CodeableConcept
    reason_reference JSONB,  -- References to Condition, Procedure, etc.
    
    -- Diagnosis
    diagnosis JSONB,  -- Array of {condition, use, rank}
    
    -- Hospitalization details
    hospitalization JSONB,  -- admit source, destination, etc.
    
    -- Location
    location JSONB,  -- Array of locations
    
    -- Practitioners
    participant JSONB,  -- Array of {type, period, individual}
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    last_synced_at TIMESTAMP
);

-- ================================================================
-- FHIR_OBSERVATIONS TABLE (Lab Results, Vital Signs)
-- ================================================================
CREATE TABLE IF NOT EXISTS fhir_observations (
    id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(organization_id),
    patient_id INTEGER REFERENCES fhir_patients(id) ON DELETE CASCADE,
    encounter_id INTEGER REFERENCES fhir_encounters(id) ON DELETE CASCADE,
    
    -- Identifiers
    identifier JSONB,
    
    -- Status: registered | preliminary | final | amended | corrected | cancelled
    status VARCHAR(50) NOT NULL,
    
    -- Category: vital-signs | laboratory | exam | survey | etc.
    category JSONB,  -- Array of CodeableConcept
    
    -- Code (LOINC, SNOMED, etc.)
    code JSONB NOT NULL,  -- CodeableConcept: {coding: [{system, code, display}], text}
    
    -- Subject (patient reference)
    subject_reference VARCHAR(200),
    
    -- Encounter reference
    encounter_reference VARCHAR(200),
    
    -- Effective time
    effective_datetime TIMESTAMP,
    effective_period JSONB,
    
    -- Issued time
    issued TIMESTAMP,
    
    -- Performer
    performer JSONB,  -- Array of references
    
    -- Value
    value_quantity JSONB,  -- {value, unit, system, code}
    value_codeable_concept JSONB,
    value_string TEXT,
    value_boolean BOOLEAN,
    value_integer INTEGER,
    value_range JSONB,
    value_ratio JSONB,
    value_sampled_data JSONB,
    value_time TIME,
    value_datetime TIMESTAMP,
    value_period JSONB,
    
    -- Data absent reason
    data_absent_reason JSONB,
    
    -- Interpretation
    interpretation JSONB,  -- Array of CodeableConcept
    
    -- Reference range
    reference_range JSONB,  -- Array of {low, high, type, text}
    
    -- Specimen reference
    specimen_reference VARCHAR(200),
    
    -- Method
    method JSONB,
    
    -- Body site
    body_site JSONB,
    
    -- Components (for multi-component observations like BP)
    component JSONB,  -- Array of observation components
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    last_synced_at TIMESTAMP
);

-- ================================================================
-- FHIR_MEDICATION_REQUESTS TABLE
-- ================================================================
CREATE TABLE IF NOT EXISTS fhir_medication_requests (
    id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(organization_id),
    patient_id INTEGER REFERENCES fhir_patients(id) ON DELETE CASCADE,
    encounter_id INTEGER REFERENCES fhir_encounters(id) ON DELETE CASCADE,
    
    -- Identifiers
    identifier JSONB,
    
    -- Status: active | on-hold | cancelled | completed
    status VARCHAR(50) NOT NULL,
    
    -- Intent: proposal | plan | order | instance-order
    intent VARCHAR(50) NOT NULL,
    
    -- Category
    category JSONB,
    
    -- Priority: routine | urgent | asap | stat
    priority VARCHAR(50),
    
    -- Medication
    medication_codeable_concept JSONB,  -- CodeableConcept
    medication_reference VARCHAR(200),
    
    -- Subject (patient)
    subject_reference VARCHAR(200),
    
    -- Encounter
    encounter_reference VARCHAR(200),
    
    -- Authored on
    authored_on TIMESTAMP,
    
    -- Requester
    requester JSONB,
    
    -- Dosage instruction
    dosage_instruction JSONB,  -- Array of dosage
    
    -- Dispense request
    dispense_request JSONB,
    
    -- Substitution
    substitution JSONB,
    
    -- Reason
    reason_code JSONB,
    reason_reference JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    last_synced_at TIMESTAMP
);

-- ================================================================
-- FHIR_ALLERGY_INTOLERANCES TABLE
-- ================================================================
CREATE TABLE IF NOT EXISTS fhir_allergy_intolerances (
    id SERIAL PRIMARY KEY,
    fhir_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(organization_id),
    patient_id INTEGER REFERENCES fhir_patients(id) ON DELETE CASCADE,
    
    -- Identifiers
    identifier JSONB,
    
    -- Clinical status: active | inactive | resolved
    clinical_status JSONB,
    
    -- Verification status: unconfirmed | confirmed | refuted
    verification_status JSONB,
    
    -- Type: allergy | intolerance
    type VARCHAR(50),
    
    -- Category: food | medication | environment | biologic
    category JSONB,  -- Array
    
    -- Criticality: low | high | unable-to-assess
    criticality VARCHAR(50),
    
    -- Code
    code JSONB,  -- CodeableConcept
    
    -- Patient
    patient_reference VARCHAR(200),
    
    -- Encounter
    encounter_reference VARCHAR(200),
    
    -- Onset
    onset_datetime TIMESTAMP,
    onset_age JSONB,
    onset_period JSONB,
    onset_range JSONB,
    onset_string VARCHAR(200),
    
    -- Recorded date
    recorded_date TIMESTAMP,
    
    -- Recorder
    recorder JSONB,
    
    -- Asserter
    asserter JSONB,
    
    -- Reactions
    reaction JSONB,  -- Array of reactions
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_system VARCHAR(100),
    last_synced_at TIMESTAMP
);

-- ================================================================
-- SYNC_STATUS TABLE (Track synchronization status)
-- ================================================================
CREATE TABLE IF NOT EXISTS sync_status (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(organization_id),
    resource_type VARCHAR(50) NOT NULL,  -- Patient, Encounter, Observation, etc.
    last_sync_time TIMESTAMP NOT NULL,
    records_synced INTEGER DEFAULT 0,
    status VARCHAR(50),  -- success | failed | in_progress
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
-- INDEXES for Performance
-- ================================================================
CREATE INDEX idx_fhir_patients_org ON fhir_patients(organization_id);
CREATE INDEX idx_fhir_patients_fhir_id ON fhir_patients(fhir_id);
CREATE INDEX idx_fhir_encounters_patient ON fhir_encounters(patient_id);
CREATE INDEX idx_fhir_encounters_org ON fhir_encounters(organization_id);
CREATE INDEX idx_fhir_observations_patient ON fhir_observations(patient_id);
CREATE INDEX idx_fhir_observations_encounter ON fhir_observations(encounter_id);
CREATE INDEX idx_fhir_observations_org ON fhir_observations(organization_id);
CREATE INDEX idx_fhir_medications_patient ON fhir_medication_requests(patient_id);
CREATE INDEX idx_fhir_allergies_patient ON fhir_allergy_intolerances(patient_id);
CREATE INDEX idx_sync_status_org ON sync_status(organization_id);

-- GIN indexes for JSONB columns (for searching within JSON)
CREATE INDEX idx_fhir_patients_identifiers ON fhir_patients USING GIN (identifiers);
CREATE INDEX idx_fhir_observations_code ON fhir_observations USING GIN (code);

-- ================================================================
-- Comments
-- ================================================================
COMMENT ON TABLE organizations IS 'Hospitals and healthcare organizations (multi-tenant)';
COMMENT ON TABLE fhir_patients IS 'FHIR R4 Patient resource - standardized patient data';
COMMENT ON TABLE fhir_encounters IS 'FHIR R4 Encounter resource - hospital visits and admissions';
COMMENT ON TABLE fhir_observations IS 'FHIR R4 Observation resource - lab results and vital signs';
COMMENT ON TABLE fhir_medication_requests IS 'FHIR R4 MedicationRequest resource';
COMMENT ON TABLE fhir_allergy_intolerances IS 'FHIR R4 AllergyIntolerance resource';
COMMENT ON TABLE sync_status IS 'Tracks synchronization status for each hospital';

-- ================================================================
-- Insert Sample Organization
-- ================================================================
INSERT INTO organizations (name, identifier, type, active)
VALUES 
    ('General Hospital Lahore', 'GHL-001', 'Hospital', TRUE),
    ('City Medical Center', 'CMC-002', 'Hospital', TRUE),
    ('National Health Institute', 'NHI-003', 'Hospital', TRUE)
ON CONFLICT (identifier) DO NOTHING;

-- ================================================================
-- Success Message
-- ================================================================
DO $$
BEGIN
    RAISE NOTICE 'Shared Central Database Schema Created Successfully!';
    RAISE NOTICE 'FHIR R4 Tables: patients, encounters, observations, medication_requests, allergy_intolerances';
    RAISE NOTICE 'Sample organizations created: 3 hospitals';
END $$;
