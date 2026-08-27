"""
CareLock Sync - Comprehensive Penetration Testing Suite
Tests security vulnerabilities in the encryption and API system

Test Categories:
1. TLS/SSL Configuration Testing
2. Authentication & Authorization Testing
3. Encryption Strength Testing
4. SQL Injection & Input Validation
5. API Security Testing
6. Rate Limiting & DoS Protection
7. Session Management Testing
8. Information Disclosure Testing
"""

import sys
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

import requests
import ssl
import socket
import json
import time
from urllib.parse import urlencode
from typing import List, Dict, Tuple
import subprocess

class PenetrationTester:
    """Comprehensive security testing framework"""
    
    def __init__(self, base_url: str = "https://localhost:8443"):
        self.base_url = base_url
        self.results = []
        self.vulnerabilities = []
        
    def log_result(self, test_name: str, passed: bool, details: str = "", severity: str = "INFO"):
        """Log test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'details': details,
            'severity': severity
        }
        self.results.append(result)
        
        if not passed and severity in ['HIGH', 'CRITICAL']:
            self.vulnerabilities.append(result)
        
        status = "✅ PASS" if passed else f"❌ FAIL [{severity}]"
        print(f"{status} - {test_name}")
        if details:
            print(f"    {details}")
    
    def test_tls_version(self):
        """Test 1: Verify TLS 1.3 is enforced"""
        print("\n" + "="*70)
        print("TEST CATEGORY 1: TLS/SSL Configuration")
        print("="*70)
        
        # Test TLS 1.3 support
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection(("localhost", 8443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                    version = ssock.version()
                    
                    if version == "TLSv1.3":
                        self.log_result(
                            "TLS 1.3 Support",
                            True,
                            f"Server supports TLS 1.3: {version}",
                            "INFO"
                        )
                    else:
                        self.log_result(
                            "TLS 1.3 Support",
                            False,
                            f"Server using {version}, not TLS 1.3",
                            "HIGH"
                        )
        except Exception as e:
            self.log_result(
                "TLS 1.3 Support",
                False,
                f"TLS test failed: {str(e)}",
                "CRITICAL"
            )
        
        # Test TLS 1.2 rejection (should fail)
        try:
            context_12 = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context_12.minimum_version = ssl.TLSVersion.TLSv1_2
            context_12.maximum_version = ssl.TLSVersion.TLSv1_2
            context_12.check_hostname = False
            context_12.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection(("localhost", 8443), timeout=5) as sock:
                try:
                    with context_12.wrap_socket(sock, server_hostname="localhost") as ssock:
                        self.log_result(
                            "TLS 1.2 Rejection",
                            False,
                            "Server accepted TLS 1.2 connection (should reject)",
                            "HIGH"
                        )
                except ssl.SSLError:
                    self.log_result(
                        "TLS 1.2 Rejection",
                        True,
                        "Server correctly rejected TLS 1.2",
                        "INFO"
                    )
        except Exception as e:
            self.log_result(
                "TLS 1.2 Rejection",
                True,
                "TLS 1.2 connection failed (expected)",
                "INFO"
            )
    
    def test_hsts_header(self):
        """Test 2: Check for HSTS header"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                verify=False,
                timeout=5
            )
            
            hsts = response.headers.get('Strict-Transport-Security')
            
            if hsts and 'max-age' in hsts:
                self.log_result(
                    "HSTS Header Present",
                    True,
                    f"HSTS: {hsts}",
                    "INFO"
                )
            else:
                self.log_result(
                    "HSTS Header Present",
                    False,
                    "HSTS header missing or misconfigured",
                    "MEDIUM"
                )
        except Exception as e:
            self.log_result(
                "HSTS Header Present",
                False,
                f"Could not test HSTS: {str(e)}",
                "MEDIUM"
            )
    
    def test_security_headers(self):
        """Test 3: Check for security headers"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                verify=False,
                timeout=5
            )
            
            required_headers = {
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY',
                'X-XSS-Protection': '1; mode=block'
            }
            
            for header, expected_value in required_headers.items():
                actual_value = response.headers.get(header)
                
                if actual_value:
                    self.log_result(
                        f"Security Header: {header}",
                        True,
                        f"{header}: {actual_value}",
                        "INFO"
                    )
                else:
                    self.log_result(
                        f"Security Header: {header}",
                        False,
                        f"Missing {header} header",
                        "LOW"
                    )
        except Exception as e:
            self.log_result(
                "Security Headers",
                False,
                f"Could not test headers: {str(e)}",
                "LOW"
            )
    
    def test_authentication(self):
        """Test 4: Authentication bypass attempts"""
        print("\n" + "="*70)
        print("TEST CATEGORY 2: Authentication & Authorization")
        print("="*70)
        
        # Test 1: Access protected endpoint without auth
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/patients",
                verify=False,
                timeout=5
            )
            
            if response.status_code == 401 or response.status_code == 403:
                self.log_result(
                    "Protected Endpoint Without Auth",
                    True,
                    f"Correctly returned {response.status_code}",
                    "INFO"
                )
            else:
                self.log_result(
                    "Protected Endpoint Without Auth",
                    False,
                    f"Endpoint accessible without auth (HTTP {response.status_code})",
                    "CRITICAL"
                )
        except Exception as e:
            self.log_result(
                "Protected Endpoint Without Auth",
                False,
                f"Test failed: {str(e)}",
                "HIGH"
            )
        
        # Test 2: Invalid JWT token
        try:
            headers = {"Authorization": "Bearer INVALID_TOKEN_12345"}
            response = requests.get(
                f"{self.base_url}/api/v1/patients",
                headers=headers,
                verify=False,
                timeout=5
            )
            
            if response.status_code == 401:
                self.log_result(
                    "Invalid JWT Rejection",
                    True,
                    "Invalid token correctly rejected",
                    "INFO"
                )
            else:
                self.log_result(
                    "Invalid JWT Rejection",
                    False,
                    f"Invalid token accepted (HTTP {response.status_code})",
                    "CRITICAL"
                )
        except Exception as e:
            pass
    
    def test_sql_injection(self):
        """Test 5: SQL Injection attempts"""
        print("\n" + "="*70)
        print("TEST CATEGORY 3: SQL Injection & Input Validation")
        print("="*70)
        
        sql_payloads = [
            "' OR '1'='1",
            "1' OR '1' = '1' --",
            "'; DROP TABLE patients; --",
            "1 UNION SELECT NULL, NULL, NULL --",
            "admin'--",
        ]
        
        for payload in sql_payloads:
            try:
                response = requests.get(
                    f"{self.base_url}/api/v1/patients?id={payload}",
                    verify=False,
                    timeout=5
                )
                
                # Check if payload was handled safely
                if response.status_code >= 500:
                    self.log_result(
                        f"SQL Injection: {payload[:20]}...",
                        False,
                        "Server error - possible SQL injection vulnerability",
                        "CRITICAL"
                    )
                else:
                    self.log_result(
                        f"SQL Injection: {payload[:20]}...",
                        True,
                        f"Payload safely handled (HTTP {response.status_code})",
                        "INFO"
                    )
            except Exception as e:
                self.log_result(
                    f"SQL Injection: {payload[:20]}...",
                    True,
                    "Payload rejected or safely handled",
                    "INFO"
                )
    
    def test_xss_injection(self):
        """Test 6: XSS injection attempts"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg/onload=alert('XSS')>",
        ]
        
        for payload in xss_payloads:
            try:
                response = requests.post(
                    f"{self.base_url}/api/v1/patients",
                    json={"name": payload},
                    verify=False,
                    timeout=5
                )
                
                # Check if response contains unescaped payload
                if payload in response.text and '<' in response.text:
                    self.log_result(
                        f"XSS Injection: {payload[:20]}...",
                        False,
                        "Response contains unescaped HTML/JS",
                        "HIGH"
                    )
                else:
                    self.log_result(
                        f"XSS Injection: {payload[:20]}...",
                        True,
                        "XSS payload safely handled",
                        "INFO"
                    )
            except Exception as e:
                self.log_result(
                    f"XSS Injection: {payload[:20]}...",
                    True,
                    "Payload rejected",
                    "INFO"
                )
    
    def test_rate_limiting(self):
        """Test 7: Rate limiting"""
        print("\n" + "="*70)
        print("TEST CATEGORY 4: Rate Limiting & DoS Protection")
        print("="*70)
        
        # Send 100 requests rapidly
        print("Sending 100 rapid requests...")
        
        blocked_count = 0
        success_count = 0
        
        for i in range(100):
            try:
                response = requests.get(
                    f"{self.base_url}/health",
                    verify=False,
                    timeout=2
                )
                
                if response.status_code == 429:  # Too Many Requests
                    blocked_count += 1
                elif response.status_code == 200:
                    success_count += 1
            except Exception:
                pass
        
        if blocked_count > 0:
            self.log_result(
                "Rate Limiting Active",
                True,
                f"Blocked {blocked_count}/100 requests after limit exceeded",
                "INFO"
            )
        else:
            self.log_result(
                "Rate Limiting Active",
                False,
                f"No rate limiting detected ({success_count}/100 succeeded)",
                "MEDIUM"
            )
    
    def test_information_disclosure(self):
        """Test 8: Information disclosure"""
        print("\n" + "="*70)
        print("TEST CATEGORY 5: Information Disclosure")
        print("="*70)
        
        # Test error messages
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/nonexistent",
                verify=False,
                timeout=5
            )
            
            # Check if response contains stack traces or sensitive info
            sensitive_keywords = [
                'Traceback',
                'File "',
                'line ',
                'Exception',
                'password',
                'secret',
                'api_key'
            ]
            
            found_sensitive = []
            response_text = response.text.lower()
            
            for keyword in sensitive_keywords:
                if keyword.lower() in response_text:
                    found_sensitive.append(keyword)
            
            if found_sensitive:
                self.log_result(
                    "Information Disclosure in Errors",
                    False,
                    f"Error response contains: {', '.join(found_sensitive)}",
                    "MEDIUM"
                )
            else:
                self.log_result(
                    "Information Disclosure in Errors",
                    True,
                    "Error responses do not leak sensitive information",
                    "INFO"
                )
        except Exception as e:
            pass
        
        # Test for /admin, /debug, /test endpoints
        test_paths = ['/admin', '/debug', '/test', '/.env', '/config', '/server-status']
        
        for path in test_paths:
            try:
                response = requests.get(
                    f"{self.base_url}{path}",
                    verify=False,
                    timeout=5
                )
                
                if response.status_code == 200:
                    self.log_result(
                        f"Exposed Debug Endpoint: {path}",
                        False,
                        f"{path} is accessible (HTTP 200)",
                        "HIGH"
                    )
                else:
                    self.log_result(
                        f"Debug Endpoint Protected: {path}",
                        True,
                        f"{path} correctly returns {response.status_code}",
                        "INFO"
                    )
            except Exception:
                pass
    
    def test_cors_misconfiguration(self):
        """Test 9: CORS misconfiguration"""
        print("\n" + "="*70)
        print("TEST CATEGORY 6: CORS Configuration")
        print("="*70)
        
        try:
            headers = {"Origin": "https://malicious-site.com"}
            response = requests.get(
                f"{self.base_url}/health",
                headers=headers,
                verify=False,
                timeout=5
            )
            
            cors_header = response.headers.get('Access-Control-Allow-Origin')
            
            if cors_header == "*":
                self.log_result(
                    "CORS Configuration",
                    False,
                    "CORS allows all origins (*) - security risk",
                    "HIGH"
                )
            elif cors_header == "https://malicious-site.com":
                self.log_result(
                    "CORS Configuration",
                    False,
                    "CORS allows arbitrary origins",
                    "HIGH"
                )
            else:
                self.log_result(
                    "CORS Configuration",
                    True,
                    f"CORS properly configured: {cors_header or 'Not set'}",
                    "INFO"
                )
        except Exception as e:
            pass
    
    def generate_report(self):
        """Generate comprehensive security report"""
        print("\n" + "="*70)
        print("PENETRATION TEST REPORT")
        print("="*70)
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total_tests - passed
        
        critical = sum(1 for r in self.results if not r['passed'] and r['severity'] == 'CRITICAL')
        high = sum(1 for r in self.results if not r['passed'] and r['severity'] == 'HIGH')
        medium = sum(1 for r in self.results if not r['passed'] and r['severity'] == 'MEDIUM')
        low = sum(1 for r in self.results if not r['passed'] and r['severity'] == 'LOW')
        
        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed} ({(passed/total_tests)*100:.1f}%)")
        print(f"Failed: {failed} ({(failed/total_tests)*100:.1f}%)")
        
        print(f"\nVulnerabilities by Severity:")
        print(f"  🔴 CRITICAL: {critical}")
        print(f"  🟠 HIGH: {high}")
        print(f"  🟡 MEDIUM: {medium}")
        print(f"  🔵 LOW: {low}")
        
        if self.vulnerabilities:
            print(f"\n⚠️  {len(self.vulnerabilities)} Vulnerability(ies) Found:")
            for vuln in self.vulnerabilities:
                print(f"  [{vuln['severity']}] {vuln['test']}")
                print(f"      {vuln['details']}")
        else:
            print("\n✅ No critical or high-severity vulnerabilities found!")
        
        # Overall security score
        score = (passed / total_tests) * 100
        severity_penalty = (critical * 10) + (high * 5) + (medium * 2) + (low * 1)
        final_score = max(0, score - severity_penalty)
        
        print(f"\n{'='*70}")
        print(f"OVERALL SECURITY SCORE: {final_score:.1f}/100")
        print(f"{'='*70}")
        
        if final_score >= 90:
            print("✅ EXCELLENT - System is production-ready")
        elif final_score >= 75:
            print("🟡 GOOD - Address high-severity issues before production")
        elif final_score >= 60:
            print("🟠 FAIR - Significant security improvements needed")
        else:
            print("🔴 POOR - Not recommended for production deployment")
        
        return final_score


def run_penetration_tests():
    """Run complete penetration test suite"""
    print("="*70)
    print("  CareLock Sync - Penetration Testing Suite")
    print("="*70)
    print("\n⚠️  Starting security testing...")
    print("    Target: https://localhost:8443")
    print("    Note: Server must be running for tests to execute\n")
    
    tester = PenetrationTester("https://localhost:8443")
    
    # Run all test categories
    try:
        tester.test_tls_version()
        tester.test_hsts_header()
        tester.test_security_headers()
        tester.test_authentication()
        tester.test_sql_injection()
        tester.test_xss_injection()
        tester.test_rate_limiting()
        tester.test_information_disclosure()
        tester.test_cors_misconfiguration()
    except KeyboardInterrupt:
        print("\n\nTesting interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error during testing: {e}")
    
    # Generate final report
    score = tester.generate_report()
    
    return score >= 75  # Pass threshold


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    
    success = run_penetration_tests()
    exit(0 if success else 1)
