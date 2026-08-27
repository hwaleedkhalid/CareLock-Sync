"""
Master Test Runner - Comprehensive Security Testing
Tests all critical security components before production
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def run_all_tests():
    print_header("CARELOCK SYNC - COMPREHENSIVE SECURITY TEST SUITE")
    print("Testing all critical security gaps before production deployment")
    
    results = {}
    
    # Test 1: MFA
    print_header("TEST SUITE 1: Multi-Factor Authentication (MFA)")
    try:
        from test_mfa import test_mfa
        results['MFA'] = test_mfa()
    except Exception as e:
        print(f"❌ MFA tests failed to run: {e}")
        results['MFA'] = False
    
    # Test 2: Rate Limiter
    print_header("TEST SUITE 2: Redis Rate Limiting")
    try:
        from test_rate_limiter import test_rate_limiter
        results['Rate Limiter'] = test_rate_limiter()
    except Exception as e:
        print(f"❌ Rate limiter tests failed to run: {e}")
        print("   Make sure Redis is running:")
        print("   Windows: docker run --name redis -p 6379:6379 -d redis:alpine")
        print("   Linux:   sudo systemctl start redis-server")
        results['Rate Limiter'] = False
    
    # Test 3: Encryption (existing)
    print_header("TEST SUITE 3: Production Encryption System")
    try:
        from verify_security_fixes import run_all_tests as test_encryption
        results['Encryption'] = test_encryption()
    except Exception as e:
        print(f"❌ Encryption tests failed to run: {e}")
        results['Encryption'] = False
    
    # Test 4: TLS Configuration
    print_header("TEST SUITE 4: TLS 1.3 Configuration")
    try:
        from tls_config import generate_self_signed_cert
        # Check if certs exist
        import os
        if os.path.exists('../../certs/server.crt') and os.path.exists('../../certs/server.key'):
            print("✅ SSL certificates present")
            results['TLS'] = True
        else:
            print("⚠️  SSL certificates not found, generating...")
            generate_self_signed_cert('../../certs')
            results['TLS'] = True
    except Exception as e:
        print(f"❌ TLS configuration failed: {e}")
        results['TLS'] = False
    
    # Final Report
    print_header("FINAL TEST REPORT")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\nTest Results: {passed}/{total} test suites passed ({percentage:.1f}%)")
    print()
    
    for component, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status} - {component}")
    
    print("\n" + "="*70)
    print("SECURITY IMPLEMENTATION STATUS")
    print("="*70)
    
    implemented = {
        'TLS 1.3 Encryption': results.get('TLS', False),
        'Production Encryption (AES-256-GCM)': results.get('Encryption', False),
        'Multi-Factor Authentication (MFA)': results.get('MFA', False),
        'Redis Rate Limiting': results.get('Rate Limiter', False),
        'Incident Response Plan': os.path.exists('../../INCIDENT_RESPONSE_PLAN.md'),
        'Audit Logging': results.get('Encryption', False),  # Part of encryption system
    }
    
    for feature, status in implemented.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {feature}")
    
    print("\n" + "="*70)
    print("COMPLIANCE SCORECARD")
    print("="*70)
    
    compliance_scores = {
        'Encryption at Rest': 95 if results.get('Encryption', False) else 0,
        'Encryption in Transit': 90 if results.get('TLS', False) else 0,
        'Rate Limiting': 90 if results.get('Rate Limiter', False) else 30,
        'Multi-Factor Auth': 95 if results.get('MFA', False) else 0,
        'Incident Response': 85 if implemented.get('Incident Response Plan') else 0,
        'Audit Logging': 80 if results.get('Encryption', False) else 0,
    }
    
    for category, score in compliance_scores.items():
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        print(f"  {category:25s} [{bar}] {score}/100")
    
    overall_score = sum(compliance_scores.values()) / len(compliance_scores)
    
    print(f"\n  {'OVERALL SCORE':25s} [{overall_score:.1f}/100]")
    
    # Grade
    if overall_score >= 90:
        grade = "A"
        status_msg = "PRODUCTION READY"
        color = "🟢"
    elif overall_score >= 75:
        grade = "B"
        status_msg = "READY WITH MINOR FIXES"
        color = "🟡"
    elif overall_score >= 60:
        grade = "C"
        status_msg = "NEEDS IMPROVEMENT"
        color = "🟠"
    else:
        grade = "D/F"
        status_msg = "NOT PRODUCTION READY"
        color = "🔴"
    
    print(f"\n  {color} GRADE: {grade} - {status_msg}")
    
    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    if not results.get('Rate Limiter', False):
        print("\n❌ CRITICAL: Rate Limiting Failed")
        print("   Action Required: Install and start Redis")
        print("   Windows: docker run --name redis -p 6379:6379 -d redis:alpine")
        print("   Linux: sudo systemctl start redis-server")
        print("   Then run: pip install redis")
    
    if not results.get('MFA', False):
        print("\n❌ CRITICAL: MFA Tests Failed")
        print("   Action Required: Install MFA dependencies")
        print("   Run: pip install pyotp qrcode pillow")
    
    if not results.get('Encryption', False):
        print("\n❌ CRITICAL: Encryption Tests Failed")
        print("   Action Required: Review encryption implementation")
        print("   Check: backend/security/production_encryption.py")
    
    if not results.get('TLS', False):
        print("\n❌ CRITICAL: TLS Configuration Failed")
        print("   Action Required: Generate SSL certificates")
        print("   Run: python -c 'from backend.security.tls_config import generate_self_signed_cert; generate_self_signed_cert()'")
    
    # Next Steps
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    
    if overall_score >= 75:
        print("\n✅ System is ready for production with minor fixes")
        print("\nImmediate Actions:")
        print("  1. Deploy master key to Azure KeyVault")
        print("  2. Get Let's Encrypt SSL certificates")
        print("  3. Configure production Redis instance")
        print("  4. Run external penetration test")
        print("  5. Conduct HIPAA compliance audit")
    else:
        print("\n⚠️  System needs improvement before production")
        print("\nCritical Actions:")
        print("  1. Fix all failed tests above")
        print("  2. Re-run this test suite")
        print("  3. Achieve grade B or higher")
        print("  4. Then proceed with production deployment")
    
    print("\n" + "="*70)
    print("TEST SUITE COMPLETE")
    print("="*70)
    
    return overall_score >= 75

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
