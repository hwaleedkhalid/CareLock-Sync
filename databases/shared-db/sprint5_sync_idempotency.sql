-- ============================================================================
-- Sprint 5 — Sync idempotency + observability
-- ============================================================================
-- (1) Adds UNIQUE constraints on (tenant_id, source_*_id) for observation and
--     medication_request so ON CONFLICT upserts become possible.
-- (2) Backfills any pre-existing duplicates by keeping the highest id.
-- (3) Adds indexes that support incremental watermark queries.
--
-- Idempotent — safe to run repeatedly.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- fhir_observation: dedup then add UNIQUE constraint
-- ---------------------------------------------------------------------------
DELETE FROM fhir_observation o
USING  fhir_observation d
WHERE  o.tenant_id             = d.tenant_id
  AND  o.source_observation_id = d.source_observation_id
  AND  o.source_observation_id IS NOT NULL
  AND  o.id < d.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_fhir_observation_tenant_source'
    ) THEN
        ALTER TABLE fhir_observation
        ADD CONSTRAINT uq_fhir_observation_tenant_source
        UNIQUE (tenant_id, source_observation_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- fhir_medication_request: dedup then add UNIQUE constraint
-- ---------------------------------------------------------------------------
DELETE FROM fhir_medication_request m
USING  fhir_medication_request d
WHERE  m.tenant_id            = d.tenant_id
  AND  m.source_medication_id = d.source_medication_id
  AND  m.source_medication_id IS NOT NULL
  AND  m.id < d.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_fhir_medication_tenant_source'
    ) THEN
        ALTER TABLE fhir_medication_request
        ADD CONSTRAINT uq_fhir_medication_tenant_source
        UNIQUE (tenant_id, source_medication_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Support incremental queries — index updated_at for watermark filtering
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fhir_patient_updated
    ON fhir_patient(tenant_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_fhir_encounter_updated
    ON fhir_encounter(tenant_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_fhir_observation_updated
    ON fhir_observation(tenant_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_fhir_medication_updated
    ON fhir_medication_request(tenant_id, updated_at);

-- ---------------------------------------------------------------------------
-- sync_runs — persistent sync state (one row per sync invocation)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_runs (
    sync_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           INTEGER NOT NULL,
    sync_type           VARCHAR(20) NOT NULL CHECK (sync_type IN ('full','incremental')),
    status              VARCHAR(20) NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    started_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP,
    progress            SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    current_step        VARCHAR(100),
    records_processed   JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message       TEXT,
    last_checkpoint     BIGINT,
    triggered_by        VARCHAR(200),
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sync_runs_tenant  ON sync_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status  ON sync_runs(status);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_runs_active
    ON sync_runs(tenant_id, status) WHERE status IN ('queued','running');

COMMIT;
