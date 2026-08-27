-- =================================================================
-- SECTION 5: ROW-LEVEL SECURITY  (tenant isolation at DB layer)
-- App must run:  SET app.tenant_id = '<id>';  on each connection
-- =================================================================

-- Admin role (can query all tenants)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carelock_admin') THEN
        CREATE ROLE carelock_admin;
    END IF;
END $$;

GRANT SELECT ON
    fhir_patient, fhir_encounter,
    fhir_observation, fhir_medication_request
TO carelock_admin;

-- Enable RLS on all partitioned parents
ALTER TABLE fhir_patient            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_encounter          ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_observation        ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_medication_request ENABLE ROW LEVEL SECURITY;

-- ── fhir_patient ─────────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON fhir_patient;
CREATE POLICY tenant_isolation ON fhir_patient
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE), '0'
        )::INTEGER
        OR current_user IN ('shared_user', 'carelock_admin')
    );

-- ── fhir_encounter ───────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON fhir_encounter;
CREATE POLICY tenant_isolation ON fhir_encounter
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE), '0'
        )::INTEGER
        OR current_user IN ('shared_user', 'carelock_admin')
    );

-- ── fhir_observation ─────────────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON fhir_observation;
CREATE POLICY tenant_isolation ON fhir_observation
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE), '0'
        )::INTEGER
        OR current_user IN ('shared_user', 'carelock_admin')
    );

-- ── fhir_medication_request ──────────────────────────────────────
DROP POLICY IF EXISTS tenant_isolation ON fhir_medication_request;
CREATE POLICY tenant_isolation ON fhir_medication_request
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE), '0'
        )::INTEGER
        OR current_user IN ('shared_user', 'carelock_admin')
    );

SELECT 'RLS policies deployed' AS status;
