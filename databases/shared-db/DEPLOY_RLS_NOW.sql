-- ============================================================================
-- CARELOCK SYNC - ROW-LEVEL SECURITY DEPLOYMENT
-- CRITICAL: Deploy this to central FHIR database IMMEDIATELY
-- ============================================================================

\echo '========================================='
\echo 'CareLock Sync - RLS Deployment Starting'
\echo '========================================='
\echo ''

-- ============================================================================
-- STEP 2: ENABLE ROW-LEVEL SECURITY
-- ============================================================================
\echo 'Step 2: Enabling Row-Level Security on all FHIR tables...'

ALTER TABLE fhir_patient ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_encounter ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_medication_request ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners
ALTER TABLE fhir_patient FORCE ROW LEVEL SECURITY;
ALTER TABLE fhir_encounter FORCE ROW LEVEL SECURITY;
ALTER TABLE fhir_observation FORCE ROW LEVEL SECURITY;
ALTER TABLE fhir_medication_request FORCE ROW LEVEL SECURITY;

\echo '  ✓ RLS enabled on fhir_patient'
\echo '  ✓ RLS enabled on fhir_encounter'
\echo '  ✓ RLS enabled on fhir_observation'
\echo '  ✓ RLS enabled on fhir_medication_request'

-- ============================================================================
-- STEP 3: CREATE TENANT ISOLATION POLICIES
-- ============================================================================
\echo 'Step 3: Creating tenant isolation policies...'

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation ON fhir_patient;
DROP POLICY IF EXISTS tenant_isolation ON fhir_encounter;
DROP POLICY IF EXISTS tenant_isolation ON fhir_observation;
DROP POLICY IF EXISTS tenant_isolation ON fhir_medication_request;

-- FHIR Patient Policy
CREATE POLICY tenant_isolation ON fhir_patient
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    )
    WITH CHECK (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    );

-- FHIR Encounter Policy
CREATE POLICY tenant_isolation ON fhir_encounter
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    )
    WITH CHECK (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    );

-- FHIR Observation Policy
CREATE POLICY tenant_isolation ON fhir_observation
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    )
    WITH CHECK (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    );

-- FHIR Medication Request Policy
CREATE POLICY tenant_isolation ON fhir_medication_request
    USING (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    )
    WITH CHECK (
        tenant_id = COALESCE(
            current_setting('app.tenant_id', TRUE)::INTEGER,
            -1
        )
    );

\echo '========================================='
\echo 'RLS Deployment Complete!'
\echo '========================================='
