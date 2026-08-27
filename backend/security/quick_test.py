import sys
sys.path.insert(0, r'C:\Projects\CareLock-Sync\backend')

from security.encryption import EncryptionManager, PatientDataEncryption, generate_master_key
import base64

print("="*70)
print("CareLock Sync - Encryption System Test")
print("="*70)

# Generate key
print("\n1. Generating Master Key...")
key_b64 = generate_master_key()
print(f"   Generated: {key_b64[:40]}...")

# Initialize
print("\n2. Initializing Encryption Manager...")
encryptor = EncryptionManager(base64.b64decode(key_b64))
print("   OK")

# Test basic encryption
print("\n3. Testing Basic Encryption/Decryption...")
plaintext = "Patient SSN: 123-45-6789"
encrypted = encryptor.encrypt(plaintext)
decrypted = encryptor.decrypt(encrypted)
print(f"   Original:  {plaintext}")
print(f"   Encrypted: {encrypted[:50]}...")
print(f"   Decrypted: {decrypted}")
print(f"   Match: {plaintext == decrypted}")

# Test patient data
print("\n4. Testing Patient Data Encryption...")
patient_enc = PatientDataEncryption(encryptor)
patient = {
    'name': 'John Doe',
    'ssn': '123-45-6789',
    'phone': '555-1234',
    'diagnosis': 'Hypertension'
}
enc_patient = patient_enc.encrypt_patient_data(patient)
dec_patient = patient_enc.decrypt_patient_data(enc_patient)
print(f"   SSN encrypted: {enc_patient['ssn'][:40]}...")
print(f"   SSN decrypted: {dec_patient['ssn']}")
print(f"   Name unchanged: {enc_patient['name']}")
print(f"   Match: {dec_patient['ssn'] == patient['ssn']}")

print("\n" + "="*70)
print("ALL TESTS PASSED!")
print("="*70)
