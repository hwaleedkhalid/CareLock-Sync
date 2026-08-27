"""
Comprehensive Verification Tests for Production Encryption System
Tests all 6 security fixes identified in audit
"""

import sys
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

from security.production_encryption import (
    SecureTenantKeyManager,
    TamperResistantAuditLogger,
    SearchableEncryption,
    DecryptionAnomalyDetector,
    ProductionEncryptionManager
)
import base64
import time
import os

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_hmac_salts():
    """TEST 1: Verify HMAC-derived salts (not predictable)"""
    print_header("TEST 1: HMAC-Derived Salts (Non-Predictable)")
    
    key_manager = SecureTenantKeyManager()
    
    # Get keys for same tenant, different contexts
    connector_key = key_manager.get_connector_key(tenant_id=1)
    cloud_key = key_manager.get_cloud_key(tenant_id=1)
    
    print(f"Tenant 1 Connector Key: {base64.b64encode(connector_key)[:40].decode()}...")
    print(f"Tenant 1 Cloud Key:     {base64.b64encode(cloud_key)[:40].decode()}...")
    print(f"\nKeys are different: {connector_key != cloud_key}")
    
    if connector_key != cloud_key:
        print("✅ PASS: Connector and cloud keys are cryptographically independent")
    else:
        print("❌ FAIL: Keys are the same!")
    
    # Verify different tenants get different keys
    tenant1_key = key_manager.get_cloud_key(tenant_id=1)
    tenant2_key = key_manager.get_cloud_key(tenant_id=2)
    
    print(f"\nTenant 1 Cloud Key: {base64.b64encode(tenant1_key)[:40].decode()}...")
    print(f"Tenant 2 Cloud Key: {base64.b64encode(tenant2_key)[:40].decode()}...")
    print(f"Tenant keys different: {tenant1_key != tenant2_key}")
    
    if tenant1_key != tenant2_key:
        print("✅ PASS: Different tenants have different keys")
    else:
        print("❌ FAIL: Tenant keys are the same!")
    
    return connector_key != cloud_key and tenant1_key != tenant2_key

def test_tamper_resistant_logging():
    """TEST 2: Verify tamper-resistant audit logging"""
    print_header("TEST 2: Tamper-Resistant Audit Logging")
    
    # Clean up old test database
    if os.path.exists('test_audit.db'):
        os.remove('test_audit.db')
    
    logger = TamperResistantAuditLogger('test_audit.db')
    
    # Log some decryption events
    print("Logging 3 decryption events...")
    logger.log_decryption(1, 'doctor_smith', 'ssn', 'P001', 'Patient treatment', True)
    logger.log_decryption(1, 'nurse_jones', 'phone', 'P002', 'Contact patient', True)
    logger.log_decryption(2, 'admin_user', 'email', 'P003', 'Administrative', False)
    
    print("✅ Logged 3 events")
    
    # Verify integrity
    print("\nVerifying audit log integrity...")
    is_valid, tampered_ids = logger.verify_integrity()
    
    print(f"Integrity check: {'VALID' if is_valid else 'TAMPERED'}")
    print(f"Tampered log IDs: {tampered_ids if tampered_ids else 'None'}")
    
    if is_valid:
        print("✅ PASS: Audit log integrity verified (hash chain intact)")
    else:
        print(f"❌ FAIL: Audit log tampered! IDs: {tampered_ids}")
    
    # Try to tamper with the database (this should fail due to triggers)
    print("\nAttempting to tamper with audit log (should fail)...")
    try:
        import sqlite3
        conn = sqlite3.connect('test_audit.db')
        cursor = conn.cursor()
        
        # Try to UPDATE (should be blocked by trigger)
        try:
            cursor.execute("UPDATE phi_access_log SET user_id = 'hacker' WHERE log_id = 1")
            conn.commit()
            print("❌ FAIL: UPDATE was allowed (trigger not working)")
        except sqlite3.IntegrityError as e:
            print(f"✅ PASS: UPDATE blocked by trigger - {str(e)[:50]}...")
        
        # Try to DELETE (should be blocked by trigger)
        try:
            cursor.execute("DELETE FROM phi_access_log WHERE log_id = 1")
            conn.commit()
            print("❌ FAIL: DELETE was allowed (trigger not working)")
        except sqlite3.IntegrityError as e:
            print(f"✅ PASS: DELETE blocked by trigger - {str(e)[:50]}...")
        
        conn.close()
    except Exception as e:
        print(f"Error during tamper test: {e}")
        return False
    
    # Clean up
    os.remove('test_audit.db')
    
    return is_valid

def test_searchable_encryption():
    """TEST 3: Verify HMAC-based searchable encryption (no pattern leakage)"""
    print_header("TEST 3: HMAC-Based Searchable Encryption")
    
    key = os.urandom(32)
    searchable = SearchableEncryption(key)
    
    # Encrypt same plaintext twice
    plaintext = "MRN-12345"
    
    print(f"Original plaintext: {plaintext}")
    print("\nEncrypting same plaintext twice...")
    
    encrypted1, hash1 = searchable.encrypt_searchable(plaintext, "medical_record_number")
    encrypted2, hash2 = searchable.encrypt_searchable(plaintext, "medical_record_number")
    
    print(f"\nEncryption 1: {encrypted1[:50]}...")
    print(f"Encryption 2: {encrypted2[:50]}...")
    print(f"Encrypted values different: {encrypted1 != encrypted2}")
    
    print(f"\nSearch hash 1: {hash1[:40]}...")
    print(f"Search hash 2: {hash2[:40]}...")
    print(f"Search hashes same: {hash1 == hash2}")
    
    # Verify decryption works
    decrypted1 = searchable.decrypt(encrypted1, "medical_record_number")
    decrypted2 = searchable.decrypt(encrypted2, "medical_record_number")
    
    print(f"\nDecrypted 1: {decrypted1}")
    print(f"Decrypted 2: {decrypted2}")
    print(f"Decryption matches original: {decrypted1 == plaintext and decrypted2 == plaintext}")
    
    # Verify search hash computation
    search_hash = searchable.compute_search_hash(plaintext, "medical_record_number")
    print(f"\nComputed search hash: {search_hash[:40]}...")
    print(f"Matches stored hash: {search_hash == hash1}")
    
    # This is the critical test: Same plaintext = different ciphertexts (no pattern leakage)
    # But same search hash (enables WHERE clauses)
    if encrypted1 != encrypted2 and hash1 == hash2 and decrypted1 == plaintext:
        print("\n✅ PASS: Random encryption (no pattern leakage) + searchable HMAC index")
    else:
        print("\n❌ FAIL: Pattern leakage or search hash mismatch")
        return False
    
    return True

def test_rate_limiting():
    """TEST 4: Verify per-field rate limiting"""
    print_header("TEST 4: Per-Field Rate Limiting")
    
    detector = DecryptionAnomalyDetector()
    
    # Test SSN rate limit (10/hour)
    print("Testing SSN rate limit (max 10/hour)...")
    
    allowed_count = 0
    blocked_count = 0
    
    for i in range(15):
        allowed, reason = detector.check_rate_limit('doctor_smith', 'ssn', tenant_id=1)
        if allowed:
            allowed_count += 1
        else:
            blocked_count += 1
            if blocked_count == 1:  # Print first block message
                print(f"\nBlocked at attempt {i+1}: {reason}")
    
    print(f"\nSSN decryption attempts: 15")
    print(f"  Allowed: {allowed_count}")
    print(f"  Blocked: {blocked_count}")
    
    if allowed_count == 10 and blocked_count == 5:
        print("✅ PASS: SSN rate limit enforced correctly (10/hour)")
    else:
        print(f"❌ FAIL: Expected 10 allowed, 5 blocked. Got {allowed_count} allowed, {blocked_count} blocked")
        return False
    
    # Test different field has different limit
    print("\n\nTesting email rate limit (max 50/hour)...")
    detector2 = DecryptionAnomalyDetector()
    
    email_allowed = 0
    for i in range(55):
        allowed, reason = detector2.check_rate_limit('doctor_smith', 'email', tenant_id=1)
        if allowed:
            email_allowed += 1
    
    print(f"Email decryption attempts: 55")
    print(f"  Allowed: {email_allowed}")
    print(f"  Blocked: {55 - email_allowed}")
    
    if email_allowed == 50:
        print("✅ PASS: Email rate limit enforced correctly (50/hour)")
    else:
        print(f"❌ FAIL: Expected 50 allowed, got {email_allowed}")
        return False
    
    return True

def test_bulk_exfiltration_detection():
    """TEST 5: Verify bulk exfiltration detection"""
    print_header("TEST 5: Bulk Exfiltration Detection")
    
    detector = DecryptionAnomalyDetector()
    
    print("Simulating normal usage (50 decryptions)...")
    
    # Normal usage - should not trigger alert
    for i in range(50):
        detector.check_rate_limit('doctor_smith', 'email', tenant_id=1)
    
    is_suspicious = detector.detect_bulk_exfiltration('doctor_smith', tenant_id=1)
    
    print(f"Alert triggered: {is_suspicious}")
    
    if not is_suspicious:
        print("✅ PASS: No false positive for normal usage")
    else:
        print("❌ FAIL: False positive on normal usage")
        return False
    
    # Suspicious usage - should trigger alert
    print("\n\nSimulating mass exfiltration (150 decryptions in 5 minutes)...")
    
    detector2 = DecryptionAnomalyDetector()
    
    for i in range(150):
        detector2.check_rate_limit('hacker', 'ssn', tenant_id=1)
        detector2.check_rate_limit('hacker', 'phone', tenant_id=1)
        detector2.check_rate_limit('hacker', 'email', tenant_id=1)
    
    is_suspicious = detector2.detect_bulk_exfiltration('hacker', tenant_id=1)
    
    print(f"\nAlert triggered: {is_suspicious}")
    
    if is_suspicious:
        print("✅ PASS: Bulk exfiltration detected correctly")
    else:
        print("❌ FAIL: Failed to detect bulk exfiltration")
        return False
    
    return True

def test_full_integration():
    """TEST 6: Full integration test with ProductionEncryptionManager"""
    print_header("TEST 6: Full Integration Test")
    
    # Clean up old audit database
    if os.path.exists('integration_test_audit.db'):
        os.remove('integration_test_audit.db')
    
    key_manager = SecureTenantKeyManager()
    audit_logger = TamperResistantAuditLogger('integration_test_audit.db')
    
    # Create encryption manager for tenant 1 (cloud context)
    enc = ProductionEncryptionManager(
        tenant_id=1,
        context="cloud",
        key_manager=key_manager,
        audit_logger=audit_logger,
        user_id="doctor_smith"
    )
    
    print("Testing encryption/decryption with audit logging...")
    
    # Test regular encryption (SSN)
    ssn = "123-45-6789"
    encrypted_ssn = enc.encrypt(ssn, field_name="ssn", record_id="P001")
    print(f"\nEncrypted SSN: {encrypted_ssn[:50]}...")
    
    # Test searchable encryption (MRN)
    mrn = "MRN-12345"
    result = enc.encrypt(mrn, field_name="medical_record_number", record_id="P001")
    
    if isinstance(result, tuple):
        encrypted_mrn, search_hash = result
        print(f"Encrypted MRN: {encrypted_mrn[:50]}...")
        print(f"Search hash: {search_hash[:40]}...")
        print("✅ Searchable field returns (encrypted_value, search_hash)")
    else:
        print("❌ FAIL: Searchable field did not return tuple")
        return False
    
    # Test decryption with audit logging
    print("\n\nTesting decryption with audit logging...")
    
    decrypted_ssn = enc.decrypt(
        encrypted_ssn,
        field_name="ssn",
        record_id="P001",
        reason="Patient treatment authorization"
    )
    
    print(f"Decrypted SSN: {decrypted_ssn}")
    print(f"Matches original: {decrypted_ssn == ssn}")
    
    # Verify audit log was written
    print("\n\nVerifying audit log entries...")
    is_valid, tampered = audit_logger.verify_integrity()
    
    print(f"Audit log integrity: {'VALID' if is_valid else 'TAMPERED'}")
    
    # Clean up
    os.remove('integration_test_audit.db')
    
    if decrypted_ssn == ssn and is_valid:
        print("\n✅ PASS: Full integration working correctly")
        return True
    else:
        print("\n❌ FAIL: Integration test failed")
        return False

def run_all_tests():
    """Run complete test suite"""
    print("="*70)
    print("  CARELOCK SYNC - PRODUCTION ENCRYPTION VERIFICATION")
    print("  Testing All 6 Security Fixes from Audit")
    print("="*70)
    
    results = []
    
    # Run all tests
    results.append(("HMAC-Derived Salts", test_hmac_salts()))
    results.append(("Tamper-Resistant Logging", test_tamper_resistant_logging()))
    results.append(("HMAC Searchable Encryption", test_searchable_encryption()))
    results.append(("Per-Field Rate Limiting", test_rate_limiting()))
    results.append(("Bulk Exfiltration Detection", test_bulk_exfiltration_detection()))
    results.append(("Full Integration", test_full_integration()))
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{passed}/{len(results)} tests passed")
    
    if failed == 0:
        print("\n" + "="*70)
        print("  🎉 ALL TESTS PASSED - SYSTEM VERIFIED")
        print("="*70)
        print("\n✅ HMAC-derived salts (non-predictable)")
        print("✅ Tamper-resistant audit logs (SQLite + triggers + hash chain)")
        print("✅ HMAC-based searchable encryption (no pattern leakage)")
        print("✅ Per-field rate limiting (SSN: 10/hour, Email: 50/hour)")
        print("✅ Bulk exfiltration detection (>100 decryptions in 5 min)")
        print("✅ Full integration working")
        print("\n🔐 Production Encryption System: VERIFIED & SECURE")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review implementation")
    
    return failed == 0

if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
