-- =================================================================
-- SECTION 2: TENANT ONBOARDING FUNCTION
-- Creates all 5 partitions + per-partition indexes + trigger
-- =================================================================
CREATE OR REPLACE FUNCTION onboard_tenant(
    p_hospital_name    VARCHAR,
    p_hospital_code    VARCHAR,
    p_hospital_address TEXT    DEFAULT NULL,
    p_contact_email    VARCHAR DEFAULT NULL,
    p_contact_phone    VARCHAR DEFAULT NULL,
    p_db_platform      VARCHAR DEFAULT 'postgresql'
)
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE
    v_tid   INTEGER;
    v_pname VARCHAR(100);
BEGIN
    -- 1. Insert tenant row (trigger auto-sets partition_name)
    INSERT INTO hospital_tenants (
        hospital_name, hospital_code, hospital_address,
        contact_email, contact_phone, db_platform, is_active
    ) VALUES (
        p_hospital_name, p_hospital_code, p_hospital_address,
        p_contact_email, p_contact_phone, p_db_platform, TRUE
    ) RETURNING tenant_id, partition_name INTO v_tid, v_pname;

    -- 2. Create one partition per FHIR table + CDC log
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I
        PARTITION OF fhir_patient            FOR VALUES IN (%s)',
        'fhir_patient_'            || v_pname, v_tid);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I
        PARTITION OF fhir_encounter          FOR VALUES IN (%s)',
        'fhir_encounter_'          || v_pname, v_tid);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I
        PARTITION OF fhir_observation        FOR VALUES IN (%s)',
        'fhir_observation_'        || v_pname, v_tid);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I
        PARTITION OF fhir_medication_request FOR VALUES IN (%s)',
        'fhir_medication_request_' || v_pname, v_tid);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I
        PARTITION OF central_cdc_log         FOR VALUES IN (%s)',
        'central_cdc_log_'         || v_pname, v_tid);

    -- 3. Per-partition indexes  (fhir_patient)
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (family_name, given_name)',
        'idx_' || v_pname || '_pt_name',  'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (birth_date)',
        'idx_' || v_pname || '_pt_dob',   'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (identifier_value)
        WHERE identifier_value IS NOT NULL',
        'idx_' || v_pname || '_pt_mrn',   'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (email)
        WHERE email IS NOT NULL',
        'idx_' || v_pname || '_pt_email', 'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (completeness_score)',
        'idx_' || v_pname || '_pt_score', 'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (optional_data)
        WHERE optional_data IS NOT NULL',
        'idx_' || v_pname || '_pt_opt',   'fhir_patient_' || v_pname);

    -- 4. Per-partition indexes  (fhir_encounter)
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',
        'idx_' || v_pname || '_enc_pat',    'fhir_encounter_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (period_start, period_end)',
        'idx_' || v_pname || '_enc_period', 'fhir_encounter_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (status)',
        'idx_' || v_pname || '_enc_status', 'fhir_encounter_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (optional_data)
        WHERE optional_data IS NOT NULL',
        'idx_' || v_pname || '_enc_opt',    'fhir_encounter_' || v_pname);

    -- 5. Per-partition indexes  (fhir_observation)
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',
        'idx_' || v_pname || '_obs_pat',  'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (code_value, effective_datetime)',
        'idx_' || v_pname || '_obs_code', 'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (category_code)',
        'idx_' || v_pname || '_obs_cat',  'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (has_attachment)
        WHERE has_attachment = TRUE',
        'idx_' || v_pname || '_obs_img',  'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (optional_data)
        WHERE optional_data IS NOT NULL',
        'idx_' || v_pname || '_obs_opt',  'fhir_observation_' || v_pname);

    -- 6. Per-partition indexes  (fhir_medication_request)
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',
        'idx_' || v_pname || '_med_pat',  'fhir_medication_request_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (medication_code_value)',
        'idx_' || v_pname || '_med_code', 'fhir_medication_request_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (status)',
        'idx_' || v_pname || '_med_stat', 'fhir_medication_request_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (optional_data)
        WHERE optional_data IS NOT NULL',
        'idx_' || v_pname || '_med_opt',  'fhir_medication_request_' || v_pname);

    -- 7. CDC log partition index
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (sync_status, changed_at)',
        'idx_' || v_pname || '_cdc_stat', 'central_cdc_log_' || v_pname);

    -- 8. Completeness score trigger on patient partition
    EXECUTE format(
        'CREATE TRIGGER %I
         BEFORE INSERT OR UPDATE ON %I
         FOR EACH ROW EXECUTE FUNCTION trg_calc_patient_completeness()',
        'trg_' || v_pname || '_score', 'fhir_patient_' || v_pname);

    RAISE NOTICE 'Tenant "%" (id=%) onboarded. Partition: %',
                 p_hospital_name, v_tid, v_pname;
    RETURN v_tid;
END;
$$;
