-- ================================================================
-- Sprint 3: API Keys table + TLS setup
-- Persistent key management with rotation support
-- ================================================================

-- API Keys table: DB-backed key registry (complements env-var keys)
CREATE TABLE IF NOT EXISTS api_keys (
    id            BIGSERIAL    PRIMARY KEY,
    api_key_id    TEXT         NOT NULL UNIQUE,
    key_hash      TEXT         NOT NULL,        -- SHA-256 of the actual key
    role          TEXT         NOT NULL CHECK (role IN ('admin','hospital','readonly')),
    tenant_id     INTEGER      REFERENCES hospital_tenants(tenant_id),
    hospital_name TEXT,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP,
    last_used_at  TIMESTAMP,
    created_by    TEXT         NOT NULL DEFAULT current_user,
    notes         TEXT
);

CREATE INDEX idx_api_keys_active  ON api_keys (is_active, role);
CREATE INDEX idx_api_keys_tenant  ON api_keys (tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX idx_api_keys_expires ON api_keys (expires_at) WHERE expires_at IS NOT NULL;

-- Seed dev keys (hash of dev key values — never store raw keys)
-- SHA-256("clk-admin-change-me-in-prod") = stored as reference only
INSERT INTO api_keys (api_key_id, key_hash, role, tenant_id, hospital_name, notes)
VALUES
  ('admin-dev',          encode(sha256('clk-admin-change-me-in-prod'::bytea), 'hex'),
   'admin',    NULL, NULL,                     'DEV ONLY — rotate before production'),
  ('hospital-cgh001',    encode(sha256('clk-cgh001-hospital-key'::bytea), 'hex'),
   'hospital', 1,    'City General Hospital',  'Hospital connector key'),
  ('hospital-pgh002',    encode(sha256('clk-pgh002-hospital-key'::bytea), 'hex'),
   'hospital', 2,    'Punjab General Hospital','Hospital connector key'),
  ('hospital-nmh003',    encode(sha256('clk-nmh003-hospital-key'::bytea), 'hex'),
   'hospital', 3,    'National Medical Hospital','Hospital connector key'),
  ('hospital-chi004',    encode(sha256('clk-chi004-hospital-key'::bytea), 'hex'),
   'hospital', 4,    'City Hospital Islamabad','Hospital connector key'),
  ('hospital-akh005',    encode(sha256('clk-akh005-hospital-key'::bytea), 'hex'),
   'hospital', 5,    'Aga Khan University Hospital','Hospital connector key'),
  ('readonly-analytics', encode(sha256('clk-readonly-analytics-key'::bytea), 'hex'),
   'readonly', NULL, NULL,                     'Read-only analytics access')
ON CONFLICT (api_key_id) DO NOTHING;

-- Function to record key usage (called from application layer)
CREATE OR REPLACE FUNCTION record_key_usage(p_api_key_id TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP
    WHERE api_key_id = p_api_key_id AND is_active = TRUE;
END;
$$;

-- View: active keys summary (safe — no raw key values)
CREATE OR REPLACE VIEW v_api_keys_summary AS
SELECT
    api_key_id, role,
    COALESCE(hospital_name, 'All Tenants')  AS scope,
    is_active,
    created_at,
    expires_at,
    last_used_at,
    CASE WHEN expires_at IS NOT NULL AND expires_at < NOW()
         THEN 'EXPIRED'
         WHEN NOT is_active THEN 'REVOKED'
         ELSE 'ACTIVE' END                  AS key_status,
    notes
FROM api_keys
ORDER BY role, api_key_id;

GRANT SELECT ON api_keys TO carelock_admin;
GRANT SELECT ON v_api_keys_summary TO carelock_admin;
GRANT ALL PRIVILEGES ON api_keys TO shared_user;
GRANT ALL PRIVILEGES ON api_keys_id_seq TO shared_user;
GRANT EXECUTE ON FUNCTION record_key_usage TO shared_user;

SELECT 'api_keys table + view created' AS status;
SELECT api_key_id, role, key_status FROM v_api_keys_summary;
