-- Phase 1: Partitioned parent tables + central CDC log

-- Rename legacy tables
ALTER TABLE IF EXISTS fhir_patient            RENAME TO fhir_patient_legacy;
ALTER TABLE IF EXISTS fhir_encounter          RENAME TO fhir_encounter_legacy;
ALTER TABLE IF EXISTS fhir_observation        RENAME TO fhir_observation_legacy;
ALTER TABLE IF EXISTS fhir_medication_request RENAME TO fhir_medication_request_legacy;

-- ── fhir_patient (partitioned)
CREATE TABLE fhir_patient (
    id                  BIGSERIAL,
    tenant_id           INTEGER       NOT NULL,
    source_patient_id   VARCHAR(100)  NOT NULL,
    identifier_system   VARCHAR(200),
    identifier_value    VARCHAR(100),
    family_name         VARCHAR(100),
    given_name          VARCHAR(100)[],
    gender              VARCHAR(20),
    birth_date          DATE,
    active              BOOLEAN  NOT NULL DEFAULT TRUE,
    deceased            BOOLEAN  NOT NULL DEFAULT FALSE,
    phone               VARCHAR(30),
    email               VARCHAR(150),
    address_line        TEXT[],
    address_city        VARCHAR(100),
    address_state       VARCHAR(50),
    address_postal_code VARCHAR(20),
    address_country     VARCHAR(50) DEFAULT 'PK',
    optional_data       JSONB,
    completeness_score  SMALLINT NOT NULL DEFAULT 0 CHECK (completeness_score BETWEEN 0 AND 100),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at   TIMESTAMP,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, source_patient_id)
) PARTITION BY LIST (tenant_id);

-- ── fhir_encounter (partitioned)
CREATE TABLE fhir_encounter (
    id                  BIGSERIAL,
    tenant_id           INTEGER NOT NULL,
    patient_id          BIGINT  NOT NULL,
    source_encounter_id VARCHAR(100) NOT NULL,
    status       VARCHAR(50),
    class_code   VARCHAR(50),
    type_code    VARCHAR(100),
    type_display VARCHAR(200),
    period_start TIMESTAMP,
    period_end   TIMESTAMP,
    location_name VARCHAR(200),
    participant_practitioner VARCHAR(200),
    reason_code   VARCHAR(100)[],
    reason_display TEXT[],
    diagnosis     TEXT[],
    optional_data JSONB,
    completeness_score SMALLINT NOT NULL DEFAULT 0 CHECK (completeness_score BETWEEN 0 AND 100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at  TIMESTAMP,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, source_encounter_id)
) PARTITION BY LIST (tenant_id);

-- ── fhir_observation (partitioned)
CREATE TABLE fhir_observation (
    id                    BIGSERIAL,
    tenant_id             INTEGER NOT NULL,
    patient_id            BIGINT  NOT NULL,
    encounter_id          BIGINT,
    source_observation_id VARCHAR(100),
    status          VARCHAR(50),
    category_code   VARCHAR(100),
    category_display VARCHAR(200),
    code_system     VARCHAR(200),
    code_value      VARCHAR(100),
    code_display    VARCHAR(200),
    value_quantity_value   DECIMAL(12,4),
    value_quantity_unit    VARCHAR(50),
    value_quantity_system  VARCHAR(200),
    value_string           TEXT,
    interpretation_code    VARCHAR(50),
    interpretation_display VARCHAR(100),
    reference_range_low    DECIMAL(12,4),
    reference_range_high   DECIMAL(12,4),
    reference_range_text   VARCHAR(200),
    effective_datetime TIMESTAMP,
    issued_datetime    TIMESTAMP,
    performer_reference VARCHAR(200),
    optional_data       JSONB,
    has_attachment      BOOLEAN NOT NULL DEFAULT FALSE,
    attachment_type     VARCHAR(50),
    attachment_storage_key VARCHAR(500),
    completeness_score SMALLINT NOT NULL DEFAULT 0 CHECK (completeness_score BETWEEN 0 AND 100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at  TIMESTAMP,
    PRIMARY KEY (tenant_id, id)
) PARTITION BY LIST (tenant_id);

-- ── fhir_medication_request (partitioned)
CREATE TABLE fhir_medication_request (
    id           BIGSERIAL,
    tenant_id    INTEGER NOT NULL,
    patient_id   BIGINT  NOT NULL,
    encounter_id BIGINT,
    source_medication_id    VARCHAR(100),
    status   VARCHAR(50),
    intent   VARCHAR(50),
    medication_code_system  VARCHAR(200),
    medication_code_value   VARCHAR(100),
    medication_code_display VARCHAR(200),
    dosage_text          VARCHAR(500),
    dosage_dose_value    DECIMAL(10,3),
    dosage_dose_unit     VARCHAR(50),
    dosage_frequency_code VARCHAR(50),
    dosage_route_code    VARCHAR(50),
    authored_on          TIMESTAMP,
    requester_reference  VARCHAR(200),
    optional_data JSONB,
    completeness_score SMALLINT NOT NULL DEFAULT 0 CHECK (completeness_score BETWEEN 0 AND 100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at  TIMESTAMP,
    PRIMARY KEY (tenant_id, id)
) PARTITION BY LIST (tenant_id);

-- ── central_cdc_log (partitioned)
CREATE TABLE central_cdc_log (
    log_id           BIGSERIAL,
    tenant_id        INTEGER      NOT NULL,
    source_db        VARCHAR(50)  NOT NULL,
    table_name       VARCHAR(100) NOT NULL,
    operation        VARCHAR(10)  NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    source_record_id VARCHAR(200) NOT NULL,
    changed_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sync_status      VARCHAR(20)  NOT NULL DEFAULT 'pending'
                     CHECK (sync_status IN ('pending','synced','failed','skipped')),
    retry_count      SMALLINT NOT NULL DEFAULT 0,
    payload          JSONB,
    error_message    TEXT,
    PRIMARY KEY (tenant_id, log_id)
) PARTITION BY LIST (tenant_id);

CREATE TABLE central_cdc_log_default PARTITION OF central_cdc_log DEFAULT;

-- Global indexes on parents
CREATE INDEX idx_patient_mrn_global    ON fhir_patient (identifier_value)     WHERE identifier_value IS NOT NULL;
CREATE INDEX idx_patient_active_global ON fhir_patient (tenant_id, family_name) WHERE active = TRUE AND deceased = FALSE;
CREATE INDEX idx_patient_quality_global ON fhir_patient (tenant_id, completeness_score);
CREATE INDEX idx_obs_numeric_global    ON fhir_observation (code_value, value_quantity_value) WHERE value_quantity_value IS NOT NULL;
CREATE INDEX idx_obs_attachments_global ON fhir_observation (tenant_id, category_code) WHERE has_attachment = TRUE;
CREATE INDEX idx_med_active_global     ON fhir_medication_request (tenant_id, medication_code_value) WHERE status = 'active';
CREATE INDEX idx_cdc_pending           ON central_cdc_log (changed_at) WHERE sync_status = 'pending';

SELECT 'Partitioned tables created' AS status;
