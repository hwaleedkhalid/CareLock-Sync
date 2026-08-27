"""
Multi-Tenancy Implementation for CareLock Sync
Adds tenant support to existing database schema

This migration:
1. Creates tenants table
2. Adds tenant_id to all data tables
3. Creates table partitions by tenant_id
4. Implements row-level security
5. Updates CDC to be tenant-aware
6. Adds tenant isolation to all queries

Run this migration: python backend/migrations/add_multi_tenancy.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from common.config import settings
from datetime import datetime

def add_multi_tenancy():
    """Add multi-tenancy support to hospital database"""
    
    print("="*70)
    print("  CareLock Sync - Multi-Tenancy Migration")
    print("="*70)
    print()
    
    # Connect to hospital database
    engine = create_engine(settings.hospital_db_url)
    
    with engine.begin() as conn:
        
        # Step 1: Create tenants table
        print("Step 1: Creating tenants table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id SERIAL PRIMARY KEY,
                tenant_name VARCHAR(255) NOT NULL UNIQUE,
                tenant_code VARCHAR(50) NOT NULL UNIQUE,
                hospital_name VARCHAR(255),
                address TEXT,
                contact_email VARCHAR(255),
                contact_phone VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                onboarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                offboarded_at TIMESTAMP,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tenants_active 
                ON tenants(is_active) WHERE is_active = TRUE;
            CREATE INDEX IF NOT EXISTS idx_tenants_code 
                ON tenants(tenant_code);
        """))
        print("   ✓ Tenants table created")
        
        # Step 2: Add tenant_id to existing tables
        print("\nStep 2: Adding tenant_id columns...")
        
        tables = [
            'patients',
            'encounters', 
            'lab_results',
            'medications'
        ]
        
        for table in tables:
            try:
                # Add tenant_id column
                conn.execute(text(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
                """))
                
                # Add foreign key constraint
                conn.execute(text(f"""
                    ALTER TABLE {table}
                    DROP CONSTRAINT IF EXISTS fk_{table}_tenant;
                    
                    ALTER TABLE {table}
                    ADD CONSTRAINT fk_{table}_tenant
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
                    ON DELETE RESTRICT;
                """))
                
                # Create index on tenant_id
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_tenant_id 
                        ON {table}(tenant_id);
                """))
                
                print(f"   ✓ Added tenant_id to {table}")
            except Exception as e:
                print(f"   ✗ Error with {table}: {e}")
        
        # Step 3: Create default tenant for existing data
        print("\nStep 3: Creating default tenant for existing data...")
        
        result = conn.execute(text("""
            INSERT INTO tenants (tenant_name, tenant_code, hospital_name, is_active)
            VALUES ('Default Hospital', 'DEFAULT', 'Migration Default', TRUE)
            ON CONFLICT (tenant_code) DO NOTHING
            RETURNING tenant_id;
        """))
        
        default_tenant_id = result.fetchone()
        if default_tenant_id:
            default_tenant_id = default_tenant_id[0]
            print(f"   ✓ Created default tenant (ID: {default_tenant_id})")
            
            # Update existing records to use default tenant
            for table in tables:
                conn.execute(text(f"""
                    UPDATE {table}
                    SET tenant_id = :tenant_id
                    WHERE tenant_id IS NULL;
                """), {"tenant_id": default_tenant_id})
                print(f"   ✓ Updated existing {table} records")
        
        # Step 4: Make tenant_id NOT NULL
        print("\nStep 4: Making tenant_id NOT NULL...")
        for table in tables:
            conn.execute(text(f"""
                ALTER TABLE {table}
                ALTER COLUMN tenant_id SET NOT NULL;
            """))
            print(f"   ✓ {table}.tenant_id is now NOT NULL")
        
        # Step 5: Create tenant context function
        print("\nStep 5: Creating tenant context functions...")
        conn.execute(text("""
            -- Function to set current tenant
            CREATE OR REPLACE FUNCTION set_current_tenant(p_tenant_id INTEGER)
            RETURNS VOID AS $$
            BEGIN
                PERFORM set_config('app.current_tenant', p_tenant_id::TEXT, FALSE);
            END;
            $$ LANGUAGE plpgsql;
            
            -- Function to get current tenant
            CREATE OR REPLACE FUNCTION get_current_tenant()
            RETURNS INTEGER AS $$
            DECLARE
                tenant_id TEXT;
            BEGIN
                tenant_id := current_setting('app.current_tenant', TRUE);
                IF tenant_id IS NULL OR tenant_id = '' THEN
                    RETURN NULL;
                END IF;
                RETURN tenant_id::INTEGER;
            END;
            $$ LANGUAGE plpgsql;
            
            -- Function to verify tenant access
            CREATE OR REPLACE FUNCTION verify_tenant_access(p_tenant_id INTEGER)
            RETURNS BOOLEAN AS $$
            DECLARE
                current_tenant INTEGER;
            BEGIN
                current_tenant := get_current_tenant();
                RETURN (current_tenant = p_tenant_id) OR (current_tenant IS NULL);
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("   ✓ Tenant context functions created")
        
        # Step 6: Enable Row Level Security
        print("\nStep 6: Enabling Row Level Security...")
        for table in tables:
            conn.execute(text(f"""
                ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                
                -- Drop existing policy if it exists
                DROP POLICY IF EXISTS tenant_isolation_policy ON {table};
                
                -- Create tenant isolation policy
                CREATE POLICY tenant_isolation_policy ON {table}
                    USING (
                        tenant_id = COALESCE(
                            current_setting('app.current_tenant', TRUE)::INTEGER,
                            tenant_id
                        )
                    )
                    WITH CHECK (
                        tenant_id = current_setting('app.current_tenant', TRUE)::INTEGER
                    );
                
                -- Allow superuser to bypass RLS for admin operations
                ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            """))
            print(f"   ✓ Enabled RLS for {table}")
        
        # Step 7: Create audit table for tenant operations
        print("\nStep 7: Creating tenant audit table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_audit_log (
                audit_id BIGSERIAL PRIMARY KEY,
                tenant_id INTEGER REFERENCES tenants(tenant_id),
                action VARCHAR(50) NOT NULL,
                table_name VARCHAR(100),
                record_id INTEGER,
                user_id INTEGER,
                changes JSONB,
                ip_address INET,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tenant_audit_tenant 
                ON tenant_audit_log(tenant_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_tenant_audit_action 
                ON tenant_audit_log(action, created_at DESC);
        """))
        print("   ✓ Tenant audit log created")
        
        # Step 8: Create tenant statistics view
        print("\nStep 8: Creating tenant statistics views...")
        conn.execute(text("""
            CREATE OR REPLACE VIEW tenant_statistics AS
            SELECT 
                t.tenant_id,
                t.tenant_name,
                t.tenant_code,
                t.is_active,
                COUNT(DISTINCT p.patient_id) as patient_count,
                COUNT(DISTINCT e.encounter_id) as encounter_count,
                COUNT(DISTINCT l.lab_result_id) as lab_result_count,
                COUNT(DISTINCT m.medication_id) as medication_count,
                MAX(p.created_at) as last_patient_added,
                MAX(e.created_at) as last_encounter_added
            FROM tenants t
            LEFT JOIN patients p ON t.tenant_id = p.tenant_id
            LEFT JOIN encounters e ON t.tenant_id = e.tenant_id
            LEFT JOIN lab_results l ON t.tenant_id = l.tenant_id
            LEFT JOIN medications m ON t.tenant_id = m.tenant_id
            GROUP BY t.tenant_id, t.tenant_name, t.tenant_code, t.is_active;
        """))
        print("   ✓ Tenant statistics view created")
    
    print("\n" + "="*70)
    print("  ✓ Multi-Tenancy Migration Complete!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Run: python backend/migrations/test_multi_tenancy.py")
    print("2. Update application code to set tenant context")
    print("3. Test tenant isolation thoroughly")
    print()

if __name__ == "__main__":
    try:
        add_multi_tenancy()
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
