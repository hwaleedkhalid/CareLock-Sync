-- =================================================================
-- SECTION 3: TENANT OFFBOARDING PROCEDURE
-- Soft offboard = detach partition (data kept as archive table)
-- Hard offboard = DROP partition (GDPR erasure / permanent delete)
-- =================================================================
CREATE OR REPLACE PROCEDURE offboard_tenant(
    p_tenant_id   INTEGER,
    p_hard_delete BOOLEAN DEFAULT FALSE
)
LANGUAGE plpgsql AS $$
DECLARE
    v_pname VARCHAR(100);
BEGIN
    SELECT partition_name INTO v_pname
    FROM hospital_tenants
    WHERE tenant_id = p_tenant_id;

    IF v_pname IS NULL THEN
        RAISE EXCEPTION 'Tenant % not found', p_tenant_id;
    END IF;

    -- Mark tenant inactive regardless of mode
    UPDATE hospital_tenants
       SET is_active = FALSE,
           offboarded_at = CURRENT_TIMESTAMP,
           updated_at    = CURRENT_TIMESTAMP
     WHERE tenant_id = p_tenant_id;

    IF p_hard_delete THEN
        -- ── HARD DELETE: wipe all data immediately ─────────────
        -- Use this for GDPR "right to erasure" requests
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE',
            'fhir_patient_'            || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE',
            'fhir_encounter_'          || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE',
            'fhir_observation_'        || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE',
            'fhir_medication_request_' || v_pname);
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE',
            'central_cdc_log_'         || v_pname);
        RAISE NOTICE 'Tenant % HARD DELETED. All data permanently removed.', p_tenant_id;

    ELSE
        -- ── SOFT OFFBOARD: detach partitions, keep as archive ──
        -- Data stays accessible as standalone tables.
        -- Re-attach later with: ALTER TABLE fhir_patient
        --     ATTACH PARTITION fhir_patient_<pname> FOR VALUES IN (<tid>);
        EXECUTE format(
            'ALTER TABLE fhir_patient DETACH PARTITION %I',
            'fhir_patient_' || v_pname);
        EXECUTE format(
            'ALTER TABLE fhir_encounter DETACH PARTITION %I',
            'fhir_encounter_' || v_pname);
        EXECUTE format(
            'ALTER TABLE fhir_observation DETACH PARTITION %I',
            'fhir_observation_' || v_pname);
        EXECUTE format(
            'ALTER TABLE fhir_medication_request DETACH PARTITION %I',
            'fhir_medication_request_' || v_pname);
        EXECUTE format(
            'ALTER TABLE central_cdc_log DETACH PARTITION %I',
            'central_cdc_log_' || v_pname);
        RAISE NOTICE 'Tenant % SOFT OFFBOARDED. '
                     'Data retained in detached tables (prefix: %).',
                     p_tenant_id, v_pname;
    END IF;
END;
$$;

-- =================================================================
-- SECTION 4: MIGRATION VERIFICATION HELPER
-- Call after migrate_legacy_data() to confirm row counts match
-- =================================================================
CREATE OR REPLACE FUNCTION verify_migration()
RETURNS TABLE(
    resource       TEXT,
    legacy_count   BIGINT,
    new_count      BIGINT,
    counts_match   BOOLEAN
)
LANGUAGE sql AS $$
    SELECT 'fhir_patient'::TEXT,
        (SELECT COUNT(*) FROM fhir_patient_legacy),
        (SELECT COUNT(*) FROM fhir_patient),
        (SELECT COUNT(*) FROM fhir_patient_legacy)
            = (SELECT COUNT(*) FROM fhir_patient)
    UNION ALL
    SELECT 'fhir_encounter',
        (SELECT COUNT(*) FROM fhir_encounter_legacy),
        (SELECT COUNT(*) FROM fhir_encounter),
        (SELECT COUNT(*) FROM fhir_encounter_legacy)
            = (SELECT COUNT(*) FROM fhir_encounter)
    UNION ALL
    SELECT 'fhir_observation',
        (SELECT COUNT(*) FROM fhir_observation_legacy),
        (SELECT COUNT(*) FROM fhir_observation),
        (SELECT COUNT(*) FROM fhir_observation_legacy)
            = (SELECT COUNT(*) FROM fhir_observation)
    UNION ALL
    SELECT 'fhir_medication_request',
        (SELECT COUNT(*) FROM fhir_medication_request_legacy),
        (SELECT COUNT(*) FROM fhir_medication_request),
        (SELECT COUNT(*) FROM fhir_medication_request_legacy)
            = (SELECT COUNT(*) FROM fhir_medication_request);
$$;

-- Safe legacy drop: refuses to run if any count mismatches
CREATE OR REPLACE PROCEDURE drop_legacy_tables()
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM verify_migration() WHERE counts_match = FALSE) THEN
        RAISE EXCEPTION
            'Row-count mismatch detected. '
            'Run SELECT * FROM verify_migration(); and fix before dropping.';
    END IF;
    DROP TABLE IF EXISTS fhir_patient_legacy            CASCADE;
    DROP TABLE IF EXISTS fhir_encounter_legacy          CASCADE;
    DROP TABLE IF EXISTS fhir_observation_legacy        CASCADE;
    DROP TABLE IF EXISTS fhir_medication_request_legacy CASCADE;
    RAISE NOTICE 'Legacy tables dropped safely.';
END;
$$;
