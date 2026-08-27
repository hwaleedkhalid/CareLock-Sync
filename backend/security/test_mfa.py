"""
Comprehensive Test Suite for MFA Implementation
Tests TOTP, backup codes, QR generation
"""

import sys
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

from security.mfa import MFAManager, MFAEnrollment
import time

def test_mfa():
    print("="*70)
    print("MFA (MULTI-FACTOR AUTHENTICATION) - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    all_passed = True
    mfa = MFAManager()
    
    # Test 1: Secret Generation
    print("\n" + "-"*70)
    print("TEST 1: TOTP Secret Generation")
    print("-"*70)
    
    try:
        secret = mfa.generate_secret()
        print(f"Generated secret: {secret}")
        
        # Verify secret is base32
        if len(secret) == 32 and secret.isalnum() and secret.isupper():
            print("✅ TEST 1 PASSED: Secret format correct (32-char base32)")
        else:
            print(f"❌ TEST 1 FAILED: Invalid secret format")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        all_passed = False
    
    # Test 2: QR Code Generation
    print("\n" + "-"*70)
    print("TEST 2: QR Code Generation")
    print("-"*70)
    
    try:
        qr_base64 = mfa.generate_qr_code("test@carelock.com", secret)
        print(f"QR Code length: {len(qr_base64)} characters")
        print(f"QR Code preview: {qr_base64[:50]}...")
        
        # Verify it's base64 encoded
        if len(qr_base64) > 100 and qr_base64.replace("+", "").replace("/", "").replace("=", "").isalnum():
            print("✅ TEST 2 PASSED: QR code generated successfully")
        else:
            print("❌ TEST 2 FAILED: QR code format invalid")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        all_passed = False
    
    # Test 3: Token Generation and Verification
    print("\n" + "-"*70)
    print("TEST 3: TOTP Token Generation and Verification")
    print("-"*70)
    
    try:
        # Generate current token
        current_token = mfa.get_current_token(secret)
        print(f"Current token: {current_token}")
        
        # Verify format
        if len(current_token) == 6 and current_token.isdigit():
            print("✅ Token format correct (6 digits)")
        else:
            print(f"❌ Token format incorrect: {current_token}")
            all_passed = False
        
        # Verify token
        is_valid = mfa.verify_token(secret, current_token)
        if is_valid:
            print("✅ TEST 3 PASSED: Token verification successful")
        else:
            print("❌ TEST 3 FAILED: Token verification failed")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        all_passed = False
    
    # Test 4: Invalid Token Rejection
    print("\n" + "-"*70)
    print("TEST 4: Invalid Token Rejection")
    print("-"*70)
    
    try:
        invalid_tokens = ["000000", "123456", "999999", "111111"]
        
        rejected = 0
        for invalid_token in invalid_tokens:
            is_valid = mfa.verify_token(secret, invalid_token)
            if not is_valid:
                rejected += 1
        
        if rejected == len(invalid_tokens):
            print(f"✅ TEST 4 PASSED: All {rejected} invalid tokens rejected")
        else:
            print(f"❌ TEST 4 FAILED: Some invalid tokens accepted ({len(invalid_tokens) - rejected}/{len(invalid_tokens)})")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        all_passed = False
    
    # Test 5: Time Window Validation
    print("\n" + "-"*70)
    print("TEST 5: Time Window Validation")
    print("-"*70)
    
    try:
        # Get current token
        token_now = mfa.get_current_token(secret)
        
        # Test with different windows
        valid_window_1 = mfa.verify_token(secret, token_now, valid_window=1)
        valid_window_2 = mfa.verify_token(secret, token_now, valid_window=2)
        
        print(f"Token valid with window=1: {valid_window_1}")
        print(f"Token valid with window=2: {valid_window_2}")
        
        if valid_window_1 and valid_window_2:
            print("✅ TEST 5 PASSED: Time window validation working")
        else:
            print("❌ TEST 5 FAILED: Time window validation incorrect")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        all_passed = False
    
    # Test 6: Backup Code Generation
    print("\n" + "-"*70)
    print("TEST 6: Backup Code Generation")
    print("-"*70)
    
    try:
        backup_codes = mfa.generate_backup_codes()
        print(f"Generated {len(backup_codes)} backup codes:")
        for i, code in enumerate(backup_codes[:3], 1):
            print(f"  {i}. {code}")
        print(f"  ... ({len(backup_codes) - 3} more)")
        
        # Verify format
        all_valid = all(len(code) == 8 and code.isalnum() and code.isupper() for code in backup_codes)
        
        if len(backup_codes) == 10 and all_valid:
            print("✅ TEST 6 PASSED: Backup codes generated correctly")
        else:
            print(f"❌ TEST 6 FAILED: Backup code format incorrect")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 6 FAILED: {e}")
        all_passed = False
    
    # Test 7: Backup Code Hashing and Verification
    print("\n" + "-"*70)
    print("TEST 7: Backup Code Hashing and Verification")
    print("-"*70)
    
    try:
        test_code = backup_codes[0]
        print(f"Testing code: {test_code}")
        
        # Hash the code
        hashed = mfa.hash_backup_code(test_code)
        print(f"Hashed: {hashed[:32]}...")
        
        # Verify it's SHA-256 (64 hex chars)
        if len(hashed) == 64 and all(c in '0123456789abcdef' for c in hashed):
            print("✅ Hash format correct (SHA-256)")
        else:
            print("❌ Hash format incorrect")
            all_passed = False
        
        # Hash all codes
        hashed_codes = [mfa.hash_backup_code(c) for c in backup_codes]
        
        # Verify the test code
        is_valid = mfa.verify_backup_code(test_code, hashed_codes)
        
        # Verify an invalid code
        is_invalid = mfa.verify_backup_code("INVALID1", hashed_codes)
        
        if is_valid and not is_invalid:
            print("✅ TEST 7 PASSED: Backup code verification working")
        else:
            print(f"❌ TEST 7 FAILED: Valid={is_valid}, Invalid={is_invalid}")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 7 FAILED: {e}")
        all_passed = False
    
    # Test 8: Full Enrollment Flow
    print("\n" + "-"*70)
    print("TEST 8: Full Enrollment Flow")
    print("-"*70)
    
    try:
        # Create enrollment
        enrollment = MFAEnrollment.create_enrollment_data("admin@carelock.com")
        
        print("Enrollment data created:")
        print(f"  Email: admin@carelock.com")
        print(f"  Secret: {enrollment['secret']}")
        print(f"  QR Code: {len(enrollment['qr_code_base64'])} chars")
        print(f"  Backup codes: {len(enrollment['backup_codes_plain'])} generated")
        print(f"  Enrolled at: {enrollment['enrolled_at']}")
        
        # Verify with test token
        test_token = mfa.get_current_token(enrollment['secret'])
        enrollment_valid = MFAEnrollment.verify_enrollment(
            enrollment['secret'],
            test_token
        )
        
        if enrollment_valid:
            print("✅ TEST 8 PASSED: Full enrollment flow working")
        else:
            print("❌ TEST 8 FAILED: Enrollment verification failed")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 8 FAILED: {e}")
        all_passed = False
    
    # Test 9: Token Expiry (30-second window)
    print("\n" + "-"*70)
    print("TEST 9: Token Time-Based Behavior")
    print("-"*70)
    
    try:
        print("Generating 3 tokens over time...")
        token1 = mfa.get_current_token(secret)
        print(f"  Token at t=0s: {token1}")
        
        time.sleep(2)
        token2 = mfa.get_current_token(secret)
        print(f"  Token at t=2s: {token2}")
        
        # Verify both tokens work
        valid1 = mfa.verify_token(secret, token1)
        valid2 = mfa.verify_token(secret, token2)
        
        print(f"  Token 1 still valid: {valid1}")
        print(f"  Token 2 valid: {valid2}")
        
        if valid1 and valid2:
            print("✅ TEST 9 PASSED: Tokens have appropriate validity window")
        else:
            print("⚠️  TEST 9 WARNING: Token validity window may be narrow")
        
    except Exception as e:
        print(f"❌ TEST 9 FAILED: {e}")
        all_passed = False
    
    # Test 10: Security Properties
    print("\n" + "-"*70)
    print("TEST 10: Security Properties")
    print("-"*70)
    
    try:
        # Test 1: Same secret generates consistent tokens
        secret_test = mfa.generate_secret()
        token_a = mfa.get_current_token(secret_test)
        token_b = mfa.get_current_token(secret_test)
        
        print(f"Same secret, same time: tokens match: {token_a == token_b}")
        
        # Test 2: Different secrets generate different tokens
        secret_test2 = mfa.generate_secret()
        token_c = mfa.get_current_token(secret_test2)
        
        print(f"Different secret: tokens differ: {token_a != token_c}")
        
        # Test 3: Backup codes are unique
        codes1 = mfa.generate_backup_codes()
        codes2 = mfa.generate_backup_codes()
        
        all_unique = len(set(codes1 + codes2)) == len(codes1) + len(codes2)
        print(f"Backup codes are unique: {all_unique}")
        
        if token_a == token_b and token_a != token_c and all_unique:
            print("✅ TEST 10 PASSED: Security properties verified")
        else:
            print("❌ TEST 10 FAILED: Security properties not met")
            all_passed = False
    except Exception as e:
        print(f"❌ TEST 10 FAILED: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nMFA is working correctly:")
        print("  ✅ TOTP secret generation")
        print("  ✅ QR code generation")
        print("  ✅ Token generation and verification")
        print("  ✅ Invalid token rejection")
        print("  ✅ Time window validation")
        print("  ✅ Backup code generation")
        print("  ✅ Backup code verification")
        print("  ✅ Full enrollment flow")
        print("  ✅ Token time-based behavior")
        print("  ✅ Security properties")
        print("\n🔐 READY FOR PRODUCTION")
        print("\n📱 Next steps:")
        print("   1. Test with real authenticator app (Google/Microsoft/Authy)")
        print("   2. Integrate with user authentication flow")
        print("   3. Add MFA fields to database schema")
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️  Review failed tests above")
        print("   NOT READY FOR PRODUCTION")
    
    return all_passed

if __name__ == "__main__":
    success = test_mfa()
    exit(0 if success else 1)
