"""
Database Migration: Add search hash column for encrypted MRN
Enables HMAC-based searchable encryption

Run this migration to add mrn_search_hash column to patients table
"""

from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.database import hospital_engine, shared_engine

def add_search_hash_column():
    """Add mrn_search_hash column to patients table"""
    
    print("="*70)
    print("Adding mrn_search_hash column for searchable encryption")
    print("="*70)
    
    # SQL to add column
    sql = """
    -- Add search hash column for encrypted MRN
    ALTER TABLE patients 
    ADD COLUMN IF NOT EXISTS mrn_search_hash VARCHAR(255);
    
    -- Create index on search hash for fast lookups
    CREATE INDEX IF NOT EXISTS idx_patients_mrn_search_hash 
    ON patients(mrn_search_hash);
    
    -- Add columns for encryption metadata
    ALTER TABLE patients 
    ADD COLUMN IF NOT EXISTS _encrypted BOOLEAN DEFAULT FALSE;
    
    ALTER TABLE patients 
    ADD COLUMN IF NOT EXISTS _encrypted_at TIMESTAMP;
    """
    
    try:
        with hospital_engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
            print("✅ Successfully added mrn_search_hash column to hospital database")
    except Exception as e:
        print(f"❌ Error adding column to hospital database: {e}")
    
    # Also add to FHIR central database if exists
    fhir_sql = """
    -- Add search hash column to FHIR patient table
    ALTER TABLE fhir_patient 
    ADD COLUMN IF NOT EXISTS mrn_search_hash VARCHAR(255);
    
    CREATE INDEX IF NOT EXISTS idx_fhir_patient_mrn_search_hash 
    ON fhir_patient(mrn_search_hash);
    
    ALTER TABLE fhir_patient 
    ADD COLUMN IF NOT EXISTS _encrypted BOOLEAN DEFAULT FALSE;
    
    ALTER TABLE fhir_patient 
    ADD COLUMN IF NOT EXISTS _encrypted_at TIMESTAMP;
    """
    
    try:
        with shared_engine.connect() as conn:
            conn.execute(text(fhir_sql))
            conn.commit()
            print("✅ Successfully added mrn_search_hash column to FHIR database")
    except Exception as e:
        print(f"⚠️  Could not add column to FHIR database: {e}")
        print("   (This is okay if FHIR database doesn't exist yet)")
    
    print("\n" + "="*70)
    print("Migration complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Encrypt existing patient records:")
    print("   python backend/security/migrate_encrypt_data.py")
    print("\n2. Start the secure server:")
    print("   python run_secure_server.py")

if __name__ == "__main__":
    add_search_hash_column()
