-- =================================================================
-- CARELOCK SYNC  |  PHASE 1 COMPLETE
-- Multi-Tenancy + Hybrid Schema + Zero-Downtime Migration
-- Run against: carelock_central_fhir  (PostgreSQL 15)
-- =================================================================

-- =================================================================
-- SECTION 1: AUTO-SET partition_name ON TENANT INSERT
-- =================================================================
CREATE OR REPLACE FUNCTION trg_set_partition_name()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.partition_name IS NULL THEN
        NEW.partition_name := 'tenant_' || lower(NEW.hospital_code);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS set_partition_name ON hospital_tenants;
CREATE TRIGGER set_partition_name
    BEFORE INSERT ON hospital_tenants
    FOR EACH ROW EXECUTE FUNCTION trg_set_partition_name();
