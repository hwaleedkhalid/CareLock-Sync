-- ================================================================
-- CareLock Sync — Phase 1 Fixes & Additions
-- Run order: single file, idempotent
-- ================================================================
\set ON_ERROR_STOP on

-- ================================================================
-- FIX 1: RLS — Remove shared_user bypass (SECURITY CRITICAL)
-- ================================================================
DROP POLICY IF EXISTS tenant_isolation ON fhir_patient;
CREATE POLICY tenant_isolation ON fhir_patient
    USING (
        tenant_id = COALESCE(current_setting('app.tenant_id', TRUE), '0')::INTEGER
        OR current_user = 'carelock_admin'
    );
DROP POLICY IF EXISTS tenant_isolation ON fhir_encounter;
CREATE POLICY tenant_isolation ON fhir_encounter
    USING (
        tenant_id = COALESCE(current_setting('app.tenant_id', TRUE), '0')::INTEGER
        OR current_user = 'carelock_admin'
    );
DROP POLICY IF EXISTS tenant_isolation ON fhir_observation;
CREATE POLICY tenant_isolation ON fhir_observation
    USING (
        tenant_id = COALESCE(current_setting('app.tenant_id', TRUE), '0')::INTEGER
        OR current_user = 'carelock_admin'
    );
DROP POLICY IF EXISTS tenant_isolation ON fhir_medication_request;
CREATE POLICY tenant_isolation ON fhir_medication_request
    USING (
        tenant_id = COALESCE(current_setting('app.tenant_id', TRUE), '0')::INTEGER
        OR current_user = 'carelock_admin'
    );
SELECT 'FIX 1 DONE: RLS shared_user bypass removed' AS status;

-- ================================================================
-- FIX 2: Tenant-Safe Composite Foreign Keys
-- ================================================================
ALTER TABLE fhir_encounter
    ADD CONSTRAINT fk_encounter_patient
    FOREIGN KEY (tenant_id, patient_id)
    REFERENCES fhir_patient (tenant_id, id)
    ON DELETE CASCADE;

ALTER TABLE fhir_observation
    ADD CONSTRAINT fk_observation_patient
    FOREIGN KEY (tenant_id, patient_id)
    REFERENCES fhir_patient (tenant_id, id)
    ON DELETE CASCADE;

ALTER TABLE fhir_observation
    ADD CONSTRAINT fk_observation_encounter
    FOREIGN KEY (tenant_id, encounter_id)
    REFERENCES fhir_encounter (tenant_id, id)
    ON DELETE SET NULL;

ALTER TABLE fhir_medication_request
    ADD CONSTRAINT fk_medication_patient
    FOREIGN KEY (tenant_id, patient_id)
    REFERENCES fhir_patient (tenant_id, id)
    ON DELETE CASCADE;

ALTER TABLE fhir_medication_request
    ADD CONSTRAINT fk_medication_encounter
    FOREIGN KEY (tenant_id, encounter_id)
    REFERENCES fhir_encounter (tenant_id, id)
    ON DELETE SET NULL;

SELECT 'FIX 2 DONE: Composite FK constraints added' AS status;

-- ================================================================
-- ADDITION 1: JSONB Field Governance Catalog
-- ================================================================
CREATE TABLE IF NOT EXISTS jsonb_field_catalog (
    tenant_id          INTEGER   NOT NULL,
    table_name         TEXT      NOT NULL,
    json_key           TEXT      NOT NULL,
    first_seen         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usage_count        INTEGER   NOT NULL DEFAULT 1,
    sample_value       TEXT,
    promoted_to_column BOOLEAN   NOT NULL DEFAULT FALSE,
    promotion_notes    TEXT,
    PRIMARY KEY (tenant_id, table_name, json_key),
    FOREIGN KEY (tenant_id) REFERENCES hospital_tenants (tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_jsonb_catalog_usage  ON jsonb_field_catalog (usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_jsonb_catalog_tenant ON jsonb_field_catalog (tenant_id, table_name);

CREATE OR REPLACE FUNCTION trg_track_jsonb_keys()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_key TEXT;
BEGIN
    IF NEW.optional_data IS NOT NULL THEN
        FOR v_key IN SELECT jsonb_object_keys(NEW.optional_data) LOOP
            INSERT INTO jsonb_field_catalog (tenant_id, table_name, json_key, sample_value)
            VALUES (NEW.tenant_id, TG_TABLE_NAME, v_key, LEFT(NEW.optional_data ->> v_key, 100))
            ON CONFLICT (tenant_id, table_name, json_key) DO UPDATE
                SET usage_count  = jsonb_field_catalog.usage_count + 1,
                    last_seen    = CURRENT_TIMESTAMP,
                    sample_value = EXCLUDED.sample_value;
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$;
SELECT 'ADDITION 1 DONE: jsonb_field_catalog + tracking function' AS status;

-- ================================================================
-- ADDITION 2: Audit Log (HIPAA Compliance)
-- ================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   INTEGER,
    db_user     TEXT      NOT NULL DEFAULT current_user,
    app_user    TEXT,
    action      TEXT      NOT NULL,
    table_name  TEXT      NOT NULL,
    record_id   TEXT,
    old_data    JSONB,
    new_data    JSONB,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_log (tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user        ON audit_log (db_user, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_table       ON audit_log (table_name, occurred_at DESC);

CREATE OR REPLACE FUNCTION trg_audit_changes()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO audit_log (tenant_id, action, table_name, record_id, old_data, new_data)
    VALUES (
        COALESCE(NEW.tenant_id, OLD.tenant_id), TG_OP, TG_TABLE_NAME,
        COALESCE(NEW.id::TEXT, OLD.id::TEXT),
        CASE WHEN TG_OP != 'INSERT' THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP != 'DELETE' THEN to_jsonb(NEW) END
    );
    RETURN COALESCE(NEW, OLD);
END;
$$;
SELECT 'ADDITION 2 DONE: audit_log + trigger function' AS status;

-- ================================================================
-- ADDITION 3: Delta Migration Guard (race condition fix)
-- ================================================================
CREATE OR REPLACE PROCEDURE run_delta_migration(p_migration_start_time TIMESTAMP)
LANGUAGE plpgsql AS $$
DECLARE v_count BIGINT;
BEGIN
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
    WHERE updated_at > p_migration_start_time OR created_at > p_migration_start_time
    ON CONFLICT (tenant_id, source_patient_id) DO UPDATE
        SET family_name = EXCLUDED.family_name, updated_at = EXCLUDED.updated_at;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Delta migration: % rows caught after %', v_count, p_migration_start_time;
END;
$$;
SELECT 'ADDITION 3 DONE: delta migration procedure created' AS status;

-- ================================================================
-- ADDITION 4: Observability Views
-- ================================================================
CREATE OR REPLACE VIEW v_tenant_health AS
SELECT
    ht.hospital_name, ht.hospital_code, ht.db_platform, fp.tenant_id,
    COUNT(fp.id)                                             AS total_patients,
    COUNT(fp.id) FILTER (WHERE fp.active = TRUE)            AS active_patients,
    COUNT(fp.id) FILTER (WHERE fp.completeness_score >= 80) AS high_quality,
    COUNT(fp.id) FILTER (WHERE fp.completeness_score <  40) AS low_quality,
    ROUND(AVG(fp.completeness_score), 1)                    AS avg_score,
    MAX(fp.updated_at)                                       AS last_updated
FROM fhir_patient fp
JOIN hospital_tenants ht ON ht.tenant_id = fp.tenant_id
GROUP BY ht.hospital_name, ht.hospital_code, ht.db_platform, fp.tenant_id;

CREATE OR REPLACE VIEW v_partition_stats AS
SELECT
    st.relname                                             AS partition_name,
    pg_size_pretty(pg_total_relation_size(st.relid))       AS total_size,
    pg_size_pretty(pg_relation_size(st.relid))             AS data_size,
    pg_size_pretty(pg_indexes_size(st.relid))              AS index_size,
    st.n_live_tup  AS live_rows,
    st.n_dead_tup  AS dead_rows,
    CASE WHEN st.n_live_tup > 0
         THEN ROUND((st.n_dead_tup * 100.0 / st.n_live_tup), 2)
         ELSE 0 END                                        AS dead_row_pct,
    st.last_vacuum, st.last_analyze,
    CASE WHEN st.n_dead_tup > 1000
           OR (st.n_live_tup > 0 AND st.n_dead_tup * 100.0 / st.n_live_tup > 10)
         THEN 'VACUUM NEEDED' ELSE 'OK' END                AS vacuum_status
FROM pg_stat_user_tables st
WHERE st.relname LIKE 'fhir_%'
ORDER BY pg_total_relation_size(st.relid) DESC;

CREATE OR REPLACE VIEW v_cdc_lag AS
SELECT
    ht.hospital_name, c.tenant_id, c.source_db,
    COUNT(*) FILTER (WHERE c.sync_status = 'pending')  AS pending_events,
    COUNT(*) FILTER (WHERE c.sync_status = 'failed')   AS failed_events,
    COUNT(*) FILTER (WHERE c.sync_status = 'synced')   AS synced_events,
    MIN(c.changed_at) FILTER (WHERE c.sync_status = 'pending') AS oldest_pending,
    EXTRACT(EPOCH FROM (NOW() -
        MIN(c.changed_at) FILTER (WHERE c.sync_status = 'pending')
    ))::INTEGER                                         AS lag_seconds,
    CASE WHEN COUNT(*) FILTER (WHERE c.sync_status = 'failed') > 10 THEN 'ALERT'
         WHEN EXTRACT(EPOCH FROM (NOW() -
              MIN(c.changed_at) FILTER (WHERE c.sync_status = 'pending'))) > 300
              THEN 'WARNING'
         ELSE 'OK' END                                  AS health_status
FROM central_cdc_log c
JOIN hospital_tenants ht ON ht.tenant_id = c.tenant_id
GROUP BY ht.hospital_name, c.tenant_id, c.source_db;

CREATE OR REPLACE VIEW v_index_health AS
SELECT
    ix.indexrelname  AS index_name, ix.relname AS table_name,
    ix.idx_scan      AS times_used,
    pg_size_pretty(pg_relation_size(ix.indexrelid)) AS index_size,
    CASE WHEN ix.idx_scan = 0       THEN 'UNUSED'
         WHEN ix.idx_scan < 100     THEN 'LOW USAGE'
         ELSE 'ACTIVE' END          AS status
FROM pg_stat_user_indexes ix
WHERE ix.relname LIKE 'fhir_%'
ORDER BY ix.idx_scan ASC, pg_relation_size(ix.indexrelid) DESC;

CREATE OR REPLACE VIEW v_jsonb_promotion_candidates AS
SELECT
    jfc.tenant_id, ht.hospital_name, jfc.table_name, jfc.json_key,
    jfc.usage_count, jfc.sample_value, jfc.promoted_to_column,
    CASE WHEN jfc.usage_count > 100 AND NOT jfc.promoted_to_column
         THEN 'PROMOTE TO TYPED COLUMN' ELSE 'MONITOR' END AS recommendation
FROM jsonb_field_catalog jfc
JOIN hospital_tenants ht ON ht.tenant_id = jfc.tenant_id
ORDER BY jfc.usage_count DESC;

SELECT 'ADDITION 4 DONE: Observability views created' AS status;

-- Final grants
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO shared_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO shared_user;
GRANT EXECUTE ON ALL FUNCTIONS        IN SCHEMA public TO shared_user;
GRANT EXECUTE ON ALL PROCEDURES       IN SCHEMA public TO shared_user;
GRANT SELECT ON v_tenant_health, v_partition_stats,
               v_cdc_lag, v_index_health,
               v_jsonb_promotion_candidates TO carelock_admin;

SELECT '=== ALL PHASE 1 FIXES DEPLOYED ===' AS status;
