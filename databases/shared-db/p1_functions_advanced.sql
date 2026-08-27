-- Phase 1: Onboarding, offboarding, RLS, maintenance, admin views

-- ── ONBOARD TENANT FUNCTION ───────────────────────────────────────
CREATE OR REPLACE FUNCTION onboard_tenant(
    p_hospital_name   VARCHAR,
    p_hospital_code   VARCHAR,
    p_hospital_address TEXT    DEFAULT NULL,
    p_contact_email   VARCHAR  DEFAULT NULL,
    p_contact_phone   VARCHAR  DEFAULT NULL,
    p_db_platform     VARCHAR  DEFAULT 'postgresql'
)
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE
    v_tenant_id INTEGER;
    v_pname     VARCHAR(100);
BEGIN
    INSERT INTO hospital_tenants (hospital_name, hospital_code, hospital_address,
        contact_email, contact_phone, db_platform, is_active)
    VALUES (p_hospital_name, p_hospital_code, p_hospital_address,
        p_contact_email, p_contact_phone, p_db_platform, TRUE)
    RETURNING tenant_id, partition_name INTO v_tenant_id, v_pname;

    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF fhir_patient            FOR VALUES IN (%s)', 'fhir_patient_'            || v_pname, v_tenant_id);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF fhir_encounter          FOR VALUES IN (%s)', 'fhir_encounter_'          || v_pname, v_tenant_id);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF fhir_observation        FOR VALUES IN (%s)', 'fhir_observation_'        || v_pname, v_tenant_id);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF fhir_medication_request FOR VALUES IN (%s)', 'fhir_medication_request_' || v_pname, v_tenant_id);
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF central_cdc_log         FOR VALUES IN (%s)', 'central_cdc_log_'         || v_pname, v_tenant_id);

    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (family_name, given_name)',     'idx_' || v_pname || '_pt_name',   'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (birth_date)',                  'idx_' || v_pname || '_pt_dob',    'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (identifier_value) WHERE identifier_value IS NOT NULL', 'idx_' || v_pname || '_pt_mrn', 'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (email) WHERE email IS NOT NULL',  'idx_' || v_pname || '_pt_email', 'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (completeness_score)',          'idx_' || v_pname || '_pt_score',  'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (optional_data) WHERE optional_data IS NOT NULL', 'idx_' || v_pname || '_pt_opt', 'fhir_patient_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',                  'idx_' || v_pname || '_enc_pat',   'fhir_encounter_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (period_start, period_end)',    'idx_' || v_pname || '_enc_per',   'fhir_encounter_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',                  'idx_' || v_pname || '_obs_pat',   'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (code_value, effective_datetime)', 'idx_' || v_pname || '_obs_code', 'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (has_attachment) WHERE has_attachment = TRUE', 'idx_' || v_pname || '_obs_img', 'fhir_observation_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (patient_id)',                  'idx_' || v_pname || '_med_pat',   'fhir_medication_request_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (medication_code_value)',       'idx_' || v_pname || '_med_code',  'fhir_medication_request_' || v_pname);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (sync_status, changed_at)',     'idx_' || v_pname || '_cdc_stat',  'central_cdc_log_' || v_pname);

    EXECUTE format('CREATE TRIGGER %I BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION trg_calc_patient_completeness()',
        'trg_' || v_pname || '_score', 'fhir_patient_' || v_pname);

    RAISE NOTICE 'Tenant % (id=%) onboarded. Partition: %', p_hospital_name, v_tenant_id, v_pname;
    RETURN v_tenant_id;
END;
$$;

-- ── OFFBOARD TENANT PROCEDURE ─────────────────────────────────────
CREATE OR REPLACE PROCEDURE offboard_tenant(p_tenant_id INTEGER, p_hard_delete BOOLEAN DEFAULT FALSE)
LANGUAGE plpgsql AS $$
DECLARE v_pname VARCHAR(100);
BEGIN
    SELECT partition_name INTO v_pname FROM hospital_tenants WHERE tenant_id = p_tenant_id;
    IF v_pname IS NULL THEN RAISE EXCEPTION 'Tenant % not found', p_tenant_id; END IF;

    UPDATE hospital_tenants SET is_active = FALSE, offboarded_at = CURRENT_TIMESTAMP WHERE tenant_id = p_tenant_id;

    IF p_hard_delete THEN
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', 'fhir_patient_'            || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', 'fhir_encounter_'          || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', 'fhir_observation_'        || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', 'fhir_medication_request_' || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', 'central_cdc_log_'         || v_pname);
        RAISE NOTICE 'Tenant % HARD deleted.', p_tenant_id;
    ELSE
        EXECUTE format('ALTER TABLE fhir_patient            DETACH PARTITION %I', 'fhir_patient_'            || v_pname);
        EXECUTE format('ALTER TABLE fhir_encounter          DETACH PARTITION %I', 'fhir_encounter_'          || v_pname);
        EXECUTE format('ALTER TABLE fhir_observation        DETACH PARTITION %I', 'fhir_observation_'        || v_pname);
        EXECUTE format('ALTER TABLE fhir_medication_request DETACH PARTITION %I', 'fhir_medication_request_' || v_pname);
        EXECUTE format('ALTER TABLE central_cdc_log         DETACH PARTITION %I', 'central_cdc_log_'         || v_pname);
        RAISE NOTICE 'Tenant % SOFT offboarded (detached, data retained).', p_tenant_id;
    END IF;
END;
$$;

-- ── MAINTENANCE PROCEDURE ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_log (
    id SERIAL PRIMARY KEY, tenant_id INTEGER,
    operation VARCHAR(50), table_name VARCHAR(200),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, finished_at TIMESTAMP, notes TEXT
);

CREATE OR REPLACE PROCEDURE run_tenant_maintenance(p_tenant_id INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_pname VARCHAR(100); v_tbl TEXT; v_tables TEXT[]; v_start TIMESTAMP;
BEGIN
    SELECT partition_name INTO v_pname FROM hospital_tenants WHERE tenant_id = p_tenant_id;
    v_tables := ARRAY[
        'fhir_patient_'            || v_pname,
        'fhir_encounter_'          || v_pname,
        'fhir_observation_'        || v_pname,
        'fhir_medication_request_' || v_pname,
        'central_cdc_log_'         || v_pname ];
    FOREACH v_tbl IN ARRAY v_tables LOOP
        v_start := CURRENT_TIMESTAMP;
        EXECUTE format('VACUUM ANALYZE %I', v_tbl);
        INSERT INTO maintenance_log(tenant_id, operation, table_name, started_at, finished_at, notes)
        VALUES (p_tenant_id, 'VACUUM ANALYZE', v_tbl, v_start, CURRENT_TIMESTAMP, 'Scheduled');
    END LOOP;
    RAISE NOTICE 'Maintenance complete for tenant %', p_tenant_id;
END;
$$;

-- CDC log purge
CREATE OR REPLACE PROCEDURE purge_cdc_log(p_tenant_id INTEGER, p_retain_days INTEGER DEFAULT 30)
LANGUAGE plpgsql AS $$
DECLARE v_deleted BIGINT;
BEGIN
    DELETE FROM central_cdc_log
    WHERE tenant_id = p_tenant_id
      AND sync_status = 'synced'
      AND changed_at < CURRENT_TIMESTAMP - (p_retain_days || ' days')::INTERVAL;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RAISE NOTICE 'Purged % CDC rows for tenant %', v_deleted, p_tenant_id;
END;
$$;

-- ── ROW-LEVEL SECURITY ────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carelock_admin') THEN
        CREATE ROLE carelock_admin;
    END IF;
END $$;

GRANT SELECT ON fhir_patient, fhir_encounter, fhir_observation, fhir_medication_request TO carelock_admin;

ALTER TABLE fhir_patient            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_encounter          ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_observation        ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_medication_request ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON fhir_patient;
CREATE POLICY tenant_isolation ON fhir_patient
    USING (tenant_id = COALESCE(current_setting('app.tenant_id', TRUE),'0')::INTEGER
           OR current_user IN ('shared_user','carelock_admin'));

DROP POLICY IF EXISTS tenant_isolation ON fhir_encounter;
CREATE POLICY tenant_isolation ON fhir_encounter
    USING (tenant_id = COALESCE(current_setting('app.tenant_id', TRUE),'0')::INTEGER
           OR current_user IN ('shared_user','carelock_admin'));

DROP POLICY IF EXISTS tenant_isolation ON fhir_observation;
CREATE POLICY tenant_isolation ON fhir_observation
    USING (tenant_id = COALESCE(current_setting('app.tenant_id', TRUE),'0')::INTEGER
           OR current_user IN ('shared_user','carelock_admin'));

DROP POLICY IF EXISTS tenant_isolation ON fhir_medication_request;
CREATE POLICY tenant_isolation ON fhir_medication_request
    USING (tenant_id = COALESCE(current_setting('app.tenant_id', TRUE),'0')::INTEGER
           OR current_user IN ('shared_user','carelock_admin'));

-- ── ADMIN VIEWS ───────────────────────────────────────────────────
CREATE OR REPLACE VIEW admin_patient_summary AS
SELECT ht.hospital_name, ht.hospital_code, fp.tenant_id,
    COUNT(*)                                             AS total_patients,
    ROUND(AVG(fp.completeness_score),1)                 AS avg_completeness,
    COUNT(*) FILTER (WHERE fp.completeness_score >= 80) AS high_quality,
    COUNT(*) FILTER (WHERE fp.completeness_score <  40) AS low_quality,
    COUNT(*) FILTER (WHERE fp.active = TRUE)            AS active_patients
FROM fhir_patient fp
JOIN hospital_tenants ht ON ht.tenant_id = fp.tenant_id
GROUP BY ht.hospital_name, ht.hospital_code, fp.tenant_id;

CREATE OR REPLACE VIEW admin_sync_status AS
SELECT ht.hospital_name, c.source_db, c.sync_status,
    COUNT(*) AS event_count, MIN(c.changed_at) AS oldest, MAX(c.changed_at) AS newest
FROM central_cdc_log c
JOIN hospital_tenants ht ON ht.tenant_id = c.tenant_id
GROUP BY ht.hospital_name, c.source_db, c.sync_status;

-- Final grants
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO shared_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO shared_user;
GRANT EXECUTE ON ALL FUNCTIONS        IN SCHEMA public TO shared_user;
GRANT EXECUTE ON ALL PROCEDURES       IN SCHEMA public TO shared_user;

SELECT 'Phase 1 COMPLETE - RLS, onboarding, maintenance all deployed' AS status;
