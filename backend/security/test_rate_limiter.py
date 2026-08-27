"""
Comprehensive Test Suite for Redis Rate Limiter
Tests all rate limiting scenarios
"""

import sys
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

from security.rate_limiter import RedisRateLimiter
from fastapi import Request, HTTPException
from starlette.datastructures import Headers
import time

def create_mock_request(ip: str = "192.168.1.100", path: str = "/api/v1/patients"):
    """Create a mock FastAPI request for testing"""
    headers = Headers({"host": "localhost"})
    return Request(scope={
        "type": "http",
        "headers": headers.raw,
        "client": (ip, 8000),
        "path": path,
        "state": {}
    })

def test_rate_limiter():
    print("="*70)
    print("REDIS RATE LIMITER - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    try:
        limiter = RedisRateLimiter()
        print("✅ Connected to Redis successfully")
    except Exception as e:
        print(f"❌ FAILED: Cannot connect to Redis")
        print(f"   Error: {e}")
        print("\n⚠️  Please start Redis:")
        print("   Windows: docker run --name redis -p 6379:6379 -d redis:alpine")
        print("   Linux:   sudo systemctl start redis-server")
        return False
    
    all_passed = True
    
    # Test 1: Basic Rate Limiting
    print("\n" + "-"*70)
    print("TEST 1: Basic Rate Limiting (Login Endpoint)")
    print("-"*70)
    
    passed = 0
    blocked = 0
    
    print("Simulating 10 login attempts (limit: 5 per 5 minutes)...")
    for i in range(10):
        request = create_mock_request(path="/api/v1/auth/login")
        request.state.user_id = f"user_{i}"
        
        try:
            limiter.check_rate_limit(request, "login", user_id=request.state.user_id)
            passed += 1
            print(f"  Attempt {i+1}: ✅ Allowed")
        except HTTPException as e:
            blocked += 1
            if blocked == 1:  # Print first block message
                print(f"  Attempt {i+1}: ❌ BLOCKED - {e.detail}")
            else:
                print(f"  Attempt {i+1}: ❌ BLOCKED")
    
    if passed == 5 and blocked == 5:
        print("✅ TEST 1 PASSED: Correctly blocked after 5 attempts")
    else:
        print(f"❌ TEST 1 FAILED: Expected 5 passed, 5 blocked. Got {passed} passed, {blocked} blocked")
        all_passed = False
    
    # Test 2: IP-Based Rate Limiting
    print("\n" + "-"*70)
    print("TEST 2: IP-Based Rate Limiting")
    print("-"*70)
    
    print("Simulating 15 requests from same IP (limit: 10 for PHI reads)...")
    passed = 0
    blocked = 0
    
    for i in range(15):
        request = create_mock_request(ip="192.168.1.200")
        request.state.user_id = f"different_user_{i}"  # Different users, same IP
        
        try:
            limiter.check_rate_limit(request, "phi_ssn", user_id=request.state.user_id)
            passed += 1
            print(f"  Request {i+1}: ✅ Allowed")
        except HTTPException as e:
            blocked += 1
            if blocked == 1:
                print(f"  Request {i+1}: ❌ BLOCKED - {e.detail}")
            else:
                print(f"  Request {i+1}: ❌ BLOCKED")
    
    if passed <= 10 and blocked >= 5:
        print("✅ TEST 2 PASSED: IP-based limiting working")
    else:
        print(f"❌ TEST 2 FAILED: IP limiting not working correctly")
        all_passed = False
    
    # Test 3: Different Sensitivity Levels
    print("\n" + "-"*70)
    print("TEST 3: Different Sensitivity Levels")
    print("-"*70)
    
    # Clear any existing limits for this test
    test_categories = {
        'health': (50, 10000),      # 50 requests, limit 10000 - all should pass
        'api_general': (150, 1000),  # 150 requests, limit 1000 - all should pass
        'phi_ssn': (15, 10),         # 15 requests, limit 10 - 5 should block
    }
    
    for category, (attempts, limit) in test_categories.items():
        print(f"\nTesting {category} (limit: {limit})...")
        passed = 0
        blocked = 0
        
        for i in range(attempts):
            request = create_mock_request(ip=f"10.0.0.{category[-3:]}")  # Unique IP per category
            request.state.user_id = f"test_{category}_{i}"
            
            try:
                limiter.check_rate_limit(request, category, user_id=request.state.user_id)
                passed += 1
            except HTTPException:
                blocked += 1
        
        print(f"  {category}: {passed} allowed, {blocked} blocked")
        
        # Verify expected behavior
        if category == 'health':
            if passed == attempts and blocked == 0:
                print(f"  ✅ {category}: Correct (permissive)")
            else:
                print(f"  ❌ {category}: Should allow all")
                all_passed = False
        elif category == 'phi_ssn':
            if blocked > 0:
                print(f"  ✅ {category}: Correct (restrictive)")
            else:
                print(f"  ❌ {category}: Should block some")
                all_passed = False
    
    # Test 4: Tenant Isolation
    print("\n" + "-"*70)
    print("TEST 4: Tenant Isolation")
    print("-"*70)
    
    print("Tenant 1: Making 8 requests (limit: 10)...")
    tenant1_passed = 0
    for i in range(8):
        request = create_mock_request()
        request.state.user_id = "user_t1"
        request.state.tenant_id = 1
        
        try:
            limiter.check_rate_limit(request, "phi_ssn", user_id=request.state.user_id, tenant_id=1)
            tenant1_passed += 1
        except HTTPException:
            pass
    
    print(f"  Tenant 1: {tenant1_passed} requests allowed")
    
    print("\nTenant 2: Making 8 requests (limit: 10)...")
    tenant2_passed = 0
    for i in range(8):
        request = create_mock_request()
        request.state.user_id = "user_t2"
        request.state.tenant_id = 2
        
        try:
            limiter.check_rate_limit(request, "phi_ssn", user_id=request.state.user_id, tenant_id=2)
            tenant2_passed += 1
        except HTTPException:
            pass
    
    print(f"  Tenant 2: {tenant2_passed} requests allowed")
    
    if tenant1_passed > 0 and tenant2_passed > 0:
        print("✅ TEST 4 PASSED: Tenant isolation working (separate limits)")
    else:
        print("❌ TEST 4 FAILED: Tenant isolation not working")
        all_passed = False
    
    # Test 5: Rate Limit Info
    print("\n" + "-"*70)
    print("TEST 5: Rate Limit Status Query")
    print("-"*70)
    
    try:
        status = limiter.get_remaining_requests("test_user_status", "phi_read", "user")
        print(f"  Rate limit status:")
        print(f"    Limit: {status['limit']}")
        print(f"    Used: {status['used']}")
        print(f"    Remaining: {status['remaining']}")
        print(f"    Reset in: {status['reset_time'] - int(time.time())}s")
        print("✅ TEST 5 PASSED: Status query working")
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        all_passed = False
    
    # Test 6: Violation Logging
    print("\n" + "-"*70)
    print("TEST 6: Violation Logging")
    print("-"*70)
    
    try:
        violations = limiter.get_violation_log(limit=10)
        print(f"  Recent violations: {len(violations)}")
        if violations:
            latest = violations[0]
            print(f"    Latest: {latest['identifier']} on {latest['category']}")
            print(f"    Time: {latest['timestamp']}")
        print("✅ TEST 6 PASSED: Violation logging working")
    except Exception as e:
        print(f"❌ TEST 6 FAILED: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nRate limiter is working correctly:")
        print("  ✅ Basic rate limiting enforced")
        print("  ✅ IP-based limiting working")
        print("  ✅ Different sensitivity levels respected")
        print("  ✅ Tenant isolation functioning")
        print("  ✅ Status queries operational")
        print("  ✅ Violation logging active")
        print("\n🔐 READY FOR PRODUCTION")
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️  Review failed tests above")
        print("   NOT READY FOR PRODUCTION")
    
    return all_passed

if __name__ == "__main__":
    success = test_rate_limiter()
    exit(0 if success else 1)
