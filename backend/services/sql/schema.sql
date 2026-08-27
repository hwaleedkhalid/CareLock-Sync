-- =====================================================================
-- CareLock CDC pipeline — shared-DB schema
--
-- Owner: ingestion / etl_worker / cdc_worker services.
-- Idempotent: every statement uses IF NOT EXISTS or CREATE OR REPLACE,
-- so the file is safe to apply on every service start.
--
-- Tables:
--   cdc_inbox          — data-only queue, ordered per (source, table)
--   cdc_dead_letter    — terminal failures
--   cdc_watermarks     — per (source, table) progress, multi-DB safe
--   cdc_control_jobs   — manual triggers / control plane (NOT data)
--   cdc_table_registry — schema contract per (source, table)
--   cdc_schema_audit   — drift events
-- =====================================================================

CREATE TABLE IF NOT EXISTS cdc_inbox (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT        NOT NULL,
    change_id       BIGINT      NOT NULL,
    source_seq      BIGINT      NOT NULL,
    source_ts       TIMESTAMPTZ NOT NULL,
    table_name      TEXT        NOT NULL,
    op              CHAR(1)     NOT NULL CHECK (op IN ('I','U','D')),
    pk              JSONB       NOT NULL,
    payload         JSONB       NOT NULL,
    payload_before  JSONB,
    schema_version  INT         NOT NULL DEFAULT 1,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at      TIMESTAMPTZ,
    claimed_by      TEXT,
    processed_at    TIMESTAMPTZ,
    attempts        INT         NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error      TEXT,
    last_error_class TEXT,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','done','failed','parked')),
    CONSTRAINT cdc_inbox_uq UNIQUE (source_id, change_id)
);

CREATE INDEX IF NOT EXISTS cdc_inbox_partition_order_idx
    ON cdc_inbox (source_id, table_name, source_seq)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS cdc_inbox_due_idx
    ON cdc_inbox (next_attempt_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS cdc_inbox_parked_idx
    ON cdc_inbox (source_id, table_name, source_seq)
    WHERE status = 'parked';

-- Used by /api/v1/system/metrics throughput + error_rate windows.
CREATE INDEX IF NOT EXISTS cdc_inbox_processed_at_idx
    ON cdc_inbox (processed_at)
    WHERE status = 'done';


CREATE TABLE IF NOT EXISTS cdc_dead_letter (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT        NOT NULL,
    change_id       BIGINT      NOT NULL,
    source_seq      BIGINT      NOT NULL,
    table_name      TEXT        NOT NULL,
    op              CHAR(1)     NOT NULL,
    pk              JSONB       NOT NULL,
    payload         JSONB       NOT NULL,
    payload_before  JSONB,
    schema_version  INT         NOT NULL,
    error_class     TEXT        NOT NULL,
    error_detail    TEXT        NOT NULL,
    attempts        INT         NOT NULL,
    failed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cdc_dlq_uq UNIQUE (source_id, change_id)
);

CREATE INDEX IF NOT EXISTS cdc_dlq_class_idx
    ON cdc_dead_letter (error_class, failed_at);


-- New cdc_watermarks (multi-DB safe).
-- NOTE: legacy cdc_watermarks (tenant_id PK) lives in the *hospital* DB;
-- this version lives in the shared DB and is keyed by (source_id, table_name).
CREATE TABLE IF NOT EXISTS cdc_watermarks (
    source_id        TEXT        NOT NULL,
    table_name       TEXT        NOT NULL,
    last_change_id   BIGINT      NOT NULL DEFAULT 0,
    last_source_seq  BIGINT      NOT NULL DEFAULT 0,
    last_source_ts   TIMESTAMPTZ,
    last_pushed_at   TIMESTAMPTZ,
    last_acked_at    TIMESTAMPTZ,
    PRIMARY KEY (source_id, table_name)
);


CREATE TABLE IF NOT EXISTS cdc_control_jobs (
    id           BIGSERIAL PRIMARY KEY,
    source_id    TEXT        NOT NULL,
    kind         TEXT        NOT NULL CHECK (kind IN
                  ('manual_full_sync','manual_incremental','reseed_watermark',
                   'pause','resume','register_table','reload_schema')),
    args         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    requested_by TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    status       TEXT        NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','in_progress','done','failed')),
    result       JSONB,
    last_error   TEXT
);

CREATE INDEX IF NOT EXISTS cdc_control_pending_idx
    ON cdc_control_jobs (source_id, requested_at)
    WHERE status = 'pending';


CREATE TABLE IF NOT EXISTS cdc_table_registry (
    source_id        TEXT        NOT NULL,
    table_name       TEXT        NOT NULL,
    central_table    TEXT        NOT NULL,
    column_map       JSONB       NOT NULL,
    pk_columns       JSONB       NOT NULL,
    schema_version   INT         NOT NULL DEFAULT 1,
    unknown_columns  TEXT        NOT NULL DEFAULT 'store_raw'
                     CHECK (unknown_columns IN ('store_raw','ignore','reject')),
    status           TEXT        NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','paused','pending_review')),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, table_name)
);


CREATE TABLE IF NOT EXISTS cdc_schema_audit (
    id            BIGSERIAL PRIMARY KEY,
    source_id     TEXT        NOT NULL,
    table_name    TEXT        NOT NULL,
    event         TEXT        NOT NULL,
    detail        JSONB       NOT NULL,
    detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS cdc_schema_audit_unresolved_idx
    ON cdc_schema_audit (source_id, table_name) WHERE resolved_at IS NULL;
