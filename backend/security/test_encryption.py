"""
Comprehensive Tests for CareLock Encryption System
"""

import sys
import os
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

from security.encryption import (
    EncryptionManager,
    PatientDataEncryption,
    generate_master_key
)
import base64
import time
import json


class TestEncryption:
    """Test suite for encryption functionality"""
    
    def __init__(self):
        self.test_results = []
        self.master_key = base64.b64decode(generate_master_key())
        self.encryptor = EncryptionManager(self.master_key)
        
    def run_test(self, test_name, test_func):
        """Run a single test and record results"""
        print(f"\n{'='*70}")
        print(f"TEST: {test_name}")
        print('='*70)
        
        try:
            start_time = time.time()
            result = test_func()
            elapsed = time.time() - start_time
            
            if result:
                print(f"PASSED (Time: {elapsed*1000:.2f}ms)")
                self.test_results.append({
                    'test': test_name,
                    'status': 'PASSED',
                    'time_ms': elapsed * 1000
                })
                return True
            else:
                print(f"FAILED")
                self.test_results.append({
                    'test': test_name,
                    'status': 'FAILED',
                    'time_ms': elapsed * 1000
                })
                return False
                
        except Exception as e:
            print(f"FAILED with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            self.test_results.append({
                'test': test_name,
                'status': 'FAILED',
                'error': str(e)
            })
            return False
    
    def test_basic_encryption_decryption(self):
        """Test 1: Basic string encryption and decryption"""
        plaintext = "Sensitive patient data: SSN 123-45-6789"
        
        print(f"Original: {plaintext}")
        
        encrypted = self.encryptor.encrypt(plaintext)
        print(f"Encrypted: {encrypted[:50]}...")
        
        assert encrypted != plaintext
        
        decrypted = self.encryptor.decrypt(encrypted)
        print(f"Decrypted: {decrypted}")
        
        assert decrypted == plaintext
        
        return True
    
    def test_authenticated_encryption(self):
        """Test 2: Authenticated encryption with associated data"""
        plaintext = "Patient record ID: 12345"
        associated_data = "patient_id_field"
        
        encrypted = self.encryptor.encrypt(plaintext, associated_data=associated_data)
        print(f"Encrypted with AAD: {encrypted[:60]}...")
        
        decrypted = self.encryptor.decrypt(encrypted, associated_data=associated_data)
        assert decrypted == plaintext
        
        try:
            self.encryptor.decrypt(encrypted, associated_data="wrong_field")
            return False
        except ValueError as e:
            print(f"Correctly rejected wrong AAD: {e}")
        
        return True
    
    def test_tampering_detection(self):
        """Test 3: Detect tampered ciphertext"""
        plaintext = "Critical medical data"
        encrypted = self.encryptor.encrypt(plaintext)
        
        parts = encrypted.split(':')
        tampered_ciphertext = parts[2][:-10] + "TAMPERED=="
        tampered = f"{parts[0]}:{parts[1]}:{tampered_ciphertext}"
        
        try:
            self.encryptor.decrypt(tampered)
            return False
        except ValueError as e:
            print(f"Tampering detected: {e}")
        
        return True
    
    def test_patient_data_encryption(self):
        """Test 4: Full patient data encryption"""
        patient_data = {
            'patient_id': 'P12345',
            'name': 'John Doe',
            'age': 45,
            'ssn': '123-45-6789',
            'phone': '+1-555-123-4567',
            'email': 'john.doe@hospital.com',
            'diagnosis': 'Hypertension',
        }
        
        print("\nOriginal Patient Data:")
        print(json.dumps(patient_data, indent=2))
        
        patient_encryptor = PatientDataEncryption(self.encryptor)
        encrypted_data = patient_encryptor.encrypt_patient_data(patient_data)
        
        print("\nEncrypted (sensitive fields only):")
        for key in ['ssn', 'phone', 'email']:
            print(f"  {key}: {encrypted_data[key][:40]}...")
        
        assert encrypted_data['ssn'] != patient_data['ssn']
        assert encrypted_data['phone'] != patient_data['phone']
        assert encrypted_data['name'] == patient_data['name']
        
        decrypted_data = patient_encryptor.decrypt_patient_data(encrypted_data)
        
        for key in ['ssn', 'phone', 'email']:
            assert decrypted_data[key] == patient_data[key]
        
        return True
    
    def test_large_data_encryption(self):
        """Test 5: Encrypt large data blocks"""
        sizes = [1024, 10240, 102400]
        
        print("\nPerformance:")
        for size in sizes:
            data = "X" * size
            
            start = time.time()
            encrypted = self.encryptor.encrypt(data)
            encrypt_time = (time.time() - start) * 1000
            
            start = time.time()
            decrypted = self.encryptor.decrypt(encrypted)
            decrypt_time = (time.time() - start) * 1000
            
            print(f"  {size:>6} bytes: Encrypt={encrypt_time:>6.2f}ms, Decrypt={decrypt_time:>6.2f}ms")
            
            if decrypted != data:
                return False
        
        return True
    
    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*70)
        print("TEST REPORT")
        print("="*70)
        
        passed = sum(1 for r in self.test_results if r['status'] == 'PASSED')
        total = len(self.test_results)
        
        print(f"\nPassed: {passed}/{total} ({(passed/total)*100:.1f}%)")
        
        for result in self.test_results:
            status = "PASS" if result['status'] == 'PASSED' else "FAIL"
            print(f"{status} {result['test']}")
        
        return passed == total


def main():
    tester = TestEncryption()
    
    tests = [
        ("Basic Encryption/Decryption", tester.test_basic_encryption_decryption),
        ("Authenticated Encryption", tester.test_authenticated_encryption),
        ("Tampering Detection", tester.test_tampering_detection),
        ("Patient Data Encryption", tester.test_patient_data_encryption),
        ("Large Data Performance", tester.test_large_data_encryption),
    ]
    
    for test_name, test_func in tests:
        tester.run_test(test_name, test_func)
    
    return 0 if tester.generate_report() else 1


if __name__ == "__main__":
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    exit(main())
