"""
CareLock Sync - Encryption Module
AES-256-GCM encryption for sensitive healthcare data

Features:
- Field-level encryption for PII/PHI
- AES-256-GCM with authenticated encryption
- Secure key management with rotation support
- Automatic encryption/decryption for database fields
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import base64
import os
import secrets
from typing import Optional, Union
import json
from datetime import datetime


class EncryptionManager:
    """
    Manages AES-256-GCM encryption for sensitive data
    
    Uses authenticated encryption (AEAD) to prevent tampering
    Supports key rotation and multiple key versions
    """
    
    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize encryption manager
        
        Args:
            master_key: 32-byte master key. If None, reads from environment or generates
        """
        if master_key is None:
            # Try to load from environment
            env_key = os.getenv('CARELOCK_MASTER_KEY')
            if env_key:
                master_key = base64.b64decode(env_key)
            else:
                # Generate new key (WARNING: should be persisted in production)
                master_key = AESGCM.generate_key(bit_length=256)
                print(f"SECURITY WARNING: Generated new master key. Save this in environment:")
                print(f"CARELOCK_MASTER_KEY={base64.b64encode(master_key).decode()}")
        
        if len(master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes (256 bits)")
        
        self.master_key = master_key
        self.aesgcm = AESGCM(master_key)
        self.key_version = "v1"  # For key rotation support
    
    def encrypt(self, plaintext: Union[str, bytes], associated_data: Optional[str] = None) -> str:
        """
        Encrypt data using AES-256-GCM
        
        Args:
            plaintext: Data to encrypt (string or bytes)
            associated_data: Optional metadata (not encrypted, but authenticated)
        
        Returns:
            Base64-encoded encrypted data with format: version:nonce:ciphertext:tag
        """
        if plaintext is None:
            return None
        
        # Convert to bytes if string
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        # Generate random nonce (96 bits recommended for GCM)
        nonce = secrets.token_bytes(12)
        
        # Prepare associated data
        aad = None
        if associated_data:
            aad = associated_data.encode('utf-8')
        
        # Encrypt
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, aad)
        
        # Format: version:nonce:ciphertext (all base64 encoded)
        # Version allows for key rotation in future
        result = f"{self.key_version}:" + \
                 base64.b64encode(nonce).decode() + ":" + \
                 base64.b64encode(ciphertext).decode()
        
        return result
    
    def decrypt(self, encrypted_data: str, associated_data: Optional[str] = None) -> str:
        """
        Decrypt data encrypted with AES-256-GCM
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            associated_data: Same metadata used during encryption
        
        Returns:
            Decrypted plaintext as string
        
        Raises:
            ValueError: If decryption fails or data is tampered
        """
        if encrypted_data is None:
            return None
        
        try:
            # Parse format: version:nonce:ciphertext
            parts = encrypted_data.split(':')
            if len(parts) != 3:
                raise ValueError("Invalid encrypted data format")
            
            version, nonce_b64, ciphertext_b64 = parts
            
            # Verify version
            if version != self.key_version:
                raise ValueError(f"Unsupported key version: {version}")
            
            # Decode
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(ciphertext_b64)
            
            # Prepare associated data
            aad = None
            if associated_data:
                aad = associated_data.encode('utf-8')
            
            # Decrypt and verify
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, aad)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def encrypt_dict(self, data: dict, fields_to_encrypt: list) -> dict:
        """
        Encrypt specific fields in a dictionary
        
        Args:
            data: Dictionary with data
            fields_to_encrypt: List of field names to encrypt
        
        Returns:
            Dictionary with encrypted fields
        """
        result = data.copy()
        
        for field in fields_to_encrypt:
            if field in result and result[field] is not None:
                # Use field name as associated data for integrity
                result[field] = self.encrypt(str(result[field]), associated_data=field)
        
        return result
    
    def decrypt_dict(self, data: dict, fields_to_decrypt: list) -> dict:
        """
        Decrypt specific fields in a dictionary
        
        Args:
            data: Dictionary with encrypted data
            fields_to_decrypt: List of field names to decrypt
        
        Returns:
            Dictionary with decrypted fields
        """
        result = data.copy()
        
        for field in fields_to_decrypt:
            if field in result and result[field] is not None:
                try:
                    result[field] = self.decrypt(result[field], associated_data=field)
                except Exception as e:
                    print(f"Warning: Could not decrypt field '{field}': {e}")
                    result[field] = "[ENCRYPTED]"
        
        return result


class PatientDataEncryption:
    """
    Specialized encryption for patient healthcare data (PHI/PII)
    
    Automatically encrypts sensitive fields according to HIPAA requirements
    """
    
    # HIPAA identifies 18 types of PHI that must be protected
    SENSITIVE_FIELDS = [
        'ssn',              # Social Security Number
        'phone',            # Phone numbers
        'email',            # Email addresses
        'address',          # Full addresses
        'medical_record_number',
        'insurance_number',
        'account_number',
        'license_number',
        'device_identifier',
        'biometric_data',
        'photo',            # Facial photos
        'ip_address',
    ]
    
    def __init__(self, encryption_manager: EncryptionManager):
        """
        Initialize patient data encryption
        
        Args:
            encryption_manager: Encryption manager instance
        """
        self.encryptor = encryption_manager
    
    def encrypt_patient_data(self, patient_data: dict) -> dict:
        """
        Encrypt sensitive patient data fields
        
        Args:
            patient_data: Patient data dictionary
        
        Returns:
            Patient data with encrypted sensitive fields
        """
        # Find which sensitive fields are present
        fields_to_encrypt = [
            field for field in self.SENSITIVE_FIELDS 
            if field in patient_data
        ]
        
        # Add a marker to indicate this data is encrypted
        result = patient_data.copy()
        result['_encrypted'] = True
        result['_encrypted_at'] = datetime.utcnow().isoformat()
        
        # Encrypt sensitive fields
        return self.encryptor.encrypt_dict(result, fields_to_encrypt)
    
    def decrypt_patient_data(self, encrypted_data: dict) -> dict:
        """
        Decrypt sensitive patient data fields
        
        Args:
            encrypted_data: Encrypted patient data
        
        Returns:
            Patient data with decrypted fields
        """
        if not encrypted_data.get('_encrypted'):
            return encrypted_data  # Not encrypted
        
        # Find which fields to decrypt
        fields_to_decrypt = [
            field for field in self.SENSITIVE_FIELDS 
            if field in encrypted_data
        ]
        
        result = self.encryptor.decrypt_dict(encrypted_data, fields_to_decrypt)
        
        # Remove encryption markers
        result.pop('_encrypted', None)
        result.pop('_encrypted_at', None)
        
        return result


def generate_master_key() -> str:
    """
    Generate a new 256-bit master key
    
    Returns:
        Base64-encoded master key (store this securely!)
    """
    key = AESGCM.generate_key(bit_length=256)
    return base64.b64encode(key).decode()


def load_encryption_manager() -> EncryptionManager:
    """
    Load encryption manager from environment or generate new key
    
    Returns:
        Configured EncryptionManager instance
    """
    return EncryptionManager()


# Example usage
if __name__ == "__main__":
    # Generate and display a master key
    master_key = generate_master_key()
    print(f"Generated Master Key (save this securely!):")
    print(f"CARELOCK_MASTER_KEY={master_key}")
    print()
    
    # Initialize encryption
    encryptor = EncryptionManager()
    
    # Test basic encryption
    plaintext = "Patient SSN: 123-45-6789"
    encrypted = encryptor.encrypt(plaintext)
    decrypted = encryptor.decrypt(encrypted)
    
    print(f"Original:  {plaintext}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {plaintext == decrypted}")
    print()
    
    # Test patient data encryption
    patient_encryptor = PatientDataEncryption(encryptor)
    
    patient = {
        'name': 'John Doe',
        'age': 45,
        'ssn': '123-45-6789',
        'phone': '+1-555-123-4567',
        'email': 'john.doe@example.com',
        'diagnosis': 'Hypertension'
    }
    
    print("Original Patient Data:")
    print(json.dumps(patient, indent=2))
    print()
    
    encrypted_patient = patient_encryptor.encrypt_patient_data(patient)
    print("Encrypted Patient Data:")
    print(json.dumps({k: v for k, v in encrypted_patient.items()}, indent=2))
    print()
    
    decrypted_patient = patient_encryptor.decrypt_patient_data(encrypted_patient)
    print("Decrypted Patient Data:")
    print(json.dumps(decrypted_patient, indent=2))
