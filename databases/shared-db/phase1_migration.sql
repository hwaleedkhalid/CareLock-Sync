-- Phase 1 Bootstrap: enrich tenants + create partitioned tables
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE hospital_tenants ADD COLUMN IF NOT EXISTS partition_name VARCHAR(100);
ALTER TABLE hospital_tenants ADD COLUMN IF NOT EXISTS db_platform VARCHAR(50) DEFAULT 'postgresql';
ALTER TABLE hospital_tenants ADD COLUMN IF NOT EXISTS sync_interval_s INTEGER DEFAULT 30;
ALTER TABLE hospital_tenants ADD COLUMN IF NOT EXISTS data_retention_days INTEGER DEFAULT 3650;
ALTER TABLE hospital_tenants ADD COLUMN IF NOT EXISTS offboarded_at TIMESTAMP;

UPDATE hospital_tenants
SET partition_name = 'tenant_' || lower(hospital_code)
WHERE partition_name IS NULL;
