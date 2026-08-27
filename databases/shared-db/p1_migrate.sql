-- Bootstrap tenant 1 partition + migrate legacy data

-- Create partitions for existing tenant 1
CREATE TABLE fhir_patient_tenant_cgh001            PARTITION OF fhir_patient            FOR VALUES IN (1);
CREATE TABLE fhir_encounter_tenant_cgh001          PARTITION OF fhir_encounter          FOR VALUES IN (1);
CREATE TABLE fhir_observation_tenant_cgh001        PARTITION OF fhir_observation        FOR VALUES IN (1);
CREATE TABLE fhir_medication_request_tenant_cgh001 PARTITION OF fhir_medication_request FOR VALUES IN (1);
CREATE TABLE central_cdc_log_tenant_cgh001         PARTITION OF central_cdc_log         FOR VALUES IN (1);

-- Per-partition indexes for tenant 1
CREATE INDEX idx_cgh001_pt_name  ON fhir_patient_tenant_cgh001 (family_name, given_name);
CREATE INDEX idx_cgh001_pt_dob   ON fhir_patient_tenant_cgh001 (birth_date);
CREATE INDEX idx_cgh001_pt_mrn   ON fhir_patient_tenant_cgh001 (identifier_value) WHERE identifier_value IS NOT NULL;
CREATE INDEX idx_cgh001_pt_email ON fhir_patient_tenant_cgh001 (email)            WHERE email IS NOT NULL;
CREATE INDEX idx_cgh001_pt_score ON fhir_patient_tenant_cgh001 (completeness_score);
CREATE INDEX idx_cgh001_pt_opt   ON fhir_patient_tenant_cgh001 USING GIN (optional_data) WHERE optional_data IS NOT NULL;

CREATE INDEX idx_cgh001_enc_pat    ON fhir_encounter_tenant_cgh001 (patient_id);
CREATE INDEX idx_cgh001_enc_period ON fhir_encounter_tenant_cgh001 (period_start, period_end);
CREATE INDEX idx_cgh001_enc_opt    ON fhir_encounter_tenant_cgh001 USING GIN (optional_data) WHERE optional_data IS NOT NULL;

CREATE INDEX idx_cgh001_obs_pat  ON fhir_observation_tenant_cgh001 (patient_id);
CREATE INDEX idx_cgh001_obs_code ON fhir_observation_tenant_cgh001 (code_value, effective_datetime);
CREATE INDEX idx_cgh001_obs_cat  ON fhir_observation_tenant_cgh001 (category_code);
CREATE INDEX idx_cgh001_obs_img  ON fhir_observation_tenant_cgh001 (has_attachment) WHERE has_attachment = TRUE;
CREATE INDEX idx_cgh001_obs_opt  ON fhir_observation_tenant_cgh001 USING GIN (optional_data) WHERE optional_data IS NOT NULL;

CREATE INDEX idx_cgh001_med_pat  ON fhir_medication_request_tenant_cgh001 (patient_id);
CREATE INDEX idx_cgh001_med_code ON fhir_medication_request_tenant_cgh001 (medication_code_value);
CREATE INDEX idx_cgh001_med_opt  ON fhir_medication_request_tenant_cgh001 USING GIN (optional_data) WHERE optional_data IS NOT NULL;

CREATE INDEX idx_cgh001_cdc_stat ON central_cdc_log_tenant_cgh001 (sync_status, changed_at);

-- Completeness trigger on tenant partition
CREATE TRIGGER trg_cgh001_patient_score
    BEFORE INSERT OR UPDATE ON fhir_patient_tenant_cgh001
    FOR EACH ROW EXECUTE FUNCTION trg_calc_patient_completeness();

-- Migrate patients from legacy
INSERT INTO fhir_patient (
    tenant_id, source_patient_id, identifier_system, identifier_value,
    family_name, given_name, gender, birth_date, active, deceased,
    phone, email, address_line, address_city, address_state,
    address_postal_code, address_country, created_at, updated_at
)
SELECT
    tenant_id, source_patient_id, identifier_system, identifier_value,
    family_name, given_name, gender, birth_date,
    COALESCE(active, TRUE), COALESCE(deceased, FALSE),
    phone, email, address_line, address_city, address_state,
    address_postal_code, address_country, created_at, updated_at
FROM fhir_patient_legacy
ON CONFLICT (tenant_id, source_patient_id) DO NOTHING;

-- Migrate encounters
INSERT INTO fhir_encounter (
    tenant_id, patient_id, source_encounter_id, status, class_code,
    type_code, type_display, period_start, period_end,
    reason_code, reason_display, diagnosis,
    location_name, participant_practitioner, created_at, updated_at
)
SELECT
    e.tenant_id, np.id, e.source_encounter_id, e.status, e.class_code,
    e.type_code, e.type_display, e.period_start, e.period_end,
    e.reason_code, e.reason_display, e.diagnosis,
    e.location_name, e.participant_practitioner, e.created_at, e.updated_at
FROM fhir_encounter_legacy e
JOIN fhir_patient_legacy lp ON lp.id = e.patient_id
JOIN fhir_patient np        ON np.tenant_id = e.tenant_id
                           AND np.source_patient_id = lp.source_patient_id
ON CONFLICT (tenant_id, source_encounter_id) DO NOTHING;

-- Verify migration
SELECT
    'fhir_patient'   AS resource,
    (SELECT COUNT(*) FROM fhir_patient_legacy) AS legacy,
    (SELECT COUNT(*) FROM fhir_patient)        AS new_partitioned,
    (SELECT COUNT(*) FROM fhir_patient_legacy) = (SELECT COUNT(*) FROM fhir_patient) AS match
UNION ALL
SELECT
    'fhir_encounter',
    (SELECT COUNT(*) FROM fhir_encounter_legacy),
    (SELECT COUNT(*) FROM fhir_encounter),
    (SELECT COUNT(*) FROM fhir_encounter_legacy) = (SELECT COUNT(*) FROM fhir_encounter);

-- Show completeness scores populated automatically
SELECT completeness_score, COUNT(*) as patients
FROM fhir_patient
GROUP BY completeness_score
ORDER BY completeness_score DESC;
