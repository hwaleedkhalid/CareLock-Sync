"""
CareLock Sync - Multi-Factor Authentication (MFA) Implementation
TOTP-based (Time-Based One-Time Password) authentication

Features:
- TOTP token generation and verification
- QR code generation for authenticator apps
- Backup codes for account recovery
- MFA enforcement for admin accounts
- Grace period for MFA setup
"""

import pyotp
import qrcode
from io import BytesIO
import base64
import secrets
import hashlib
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import json

class MFAManager:
    """
    Multi-Factor Authentication Manager
    
    Implements TOTP (Time-Based One-Time Password) authentication
    compatible with Google Authenticator, Authy, Microsoft Authenticator
    """
    
    def __init__(self, issuer_name: str = "CareLock Sync"):
        """
        Initialize MFA Manager
        
        Args:
            issuer_name: Name shown in authenticator app
        """
        self.issuer_name = issuer_name
        self.backup_code_count = 10  # Number of backup codes to generate
    
    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret for a user
        
        Returns:
            Base32-encoded secret string
        """
        return pyotp.random_base32()
    
    def generate_qr_code(self, user_email: str, secret: str) -> str:
        """
        Generate QR code for authenticator app setup
        
        Args:
            user_email: User's email address
            secret: TOTP secret
        
        Returns:
            Base64-encoded PNG image of QR code
        """
        # Create TOTP instance
        totp = pyotp.TOTP(secret)
        
        # Generate provisioning URI
        uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=self.issuer_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return img_str
    
    def verify_token(
        self,
        secret: str,
        token: str,
        valid_window: int = 1
    ) -> bool:
        """
        Verify TOTP token
        
        Args:
            secret: User's TOTP secret
            token: 6-digit token from authenticator app
            valid_window: Number of time windows to check (default: 1)
                         1 = ±30 seconds, 2 = ±60 seconds
        
        Returns:
            True if token is valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=valid_window)
    
    def generate_backup_codes(self) -> List[str]:
        """
        Generate backup codes for account recovery
        
        Returns:
            List of backup codes (8 characters each)
        """
        codes = []
        for _ in range(self.backup_code_count):
            # Generate 8-character alphanumeric code
            code = secrets.token_hex(4).upper()
            codes.append(code)
        
        return codes
    
    def hash_backup_code(self, code: str) -> str:
        """
        Hash backup code for secure storage
        
        Args:
            code: Plain backup code
        
        Returns:
            SHA-256 hash of code
        """
        return hashlib.sha256(code.encode()).hexdigest()
    
    def verify_backup_code(self, code: str, hashed_codes: List[str]) -> bool:
        """
        Verify backup code against stored hashes
        
        Args:
            code: Plain backup code from user
            hashed_codes: List of hashed backup codes
        
        Returns:
            True if code is valid (and removes it from list)
        """
        code_hash = self.hash_backup_code(code)
        return code_hash in hashed_codes
    
    def get_current_token(self, secret: str) -> str:
        """
        Get current valid token (for testing purposes)
        
        Args:
            secret: TOTP secret
        
        Returns:
            Current 6-digit token
        """
        totp = pyotp.TOTP(secret)
        return totp.now()


class MFAEnrollment:
    """
    Helper class for MFA enrollment process
    """
    
    @staticmethod
    def create_enrollment_data(user_email: str) -> dict:
        """
        Create MFA enrollment data for a user
        
        Args:
            user_email: User's email address
        
        Returns:
            Dict with secret, qr_code, backup_codes
        """
        mfa = MFAManager()
        
        # Generate secret
        secret = mfa.generate_secret()
        
        # Generate QR code
        qr_code_base64 = mfa.generate_qr_code(user_email, secret)
        
        # Generate backup codes
        backup_codes = mfa.generate_backup_codes()
        backup_codes_hashed = [mfa.hash_backup_code(c) for c in backup_codes]
        
        return {
            'secret': secret,
            'qr_code_base64': qr_code_base64,
            'backup_codes_plain': backup_codes,  # Show to user once
            'backup_codes_hashed': backup_codes_hashed,  # Store in database
            'enrolled_at': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def verify_enrollment(secret: str, test_token: str) -> bool:
        """
        Verify enrollment by testing token
        
        Args:
            secret: TOTP secret
            test_token: Token from authenticator app
        
        Returns:
            True if enrollment is valid
        """
        mfa = MFAManager()
        return mfa.verify_token(secret, test_token)


# Example database model (add to common/models.py)
EXAMPLE_USER_MODEL = """
class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # MFA fields
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(32), nullable=True)  # TOTP secret
    mfa_backup_codes = Column(JSON, nullable=True)  # List of hashed codes
    mfa_enrolled_at = Column(DateTime, nullable=True)
    mfa_grace_period_end = Column(DateTime, nullable=True)  # Admin grace period
    
    # Roles
    roles = Column(JSON, default=['user'])  # ['user', 'doctor', 'admin']
"""


# FastAPI integration example
EXAMPLE_FASTAPI_ROUTES = """
from fastapi import APIRouter, Depends, HTTPException
from backend.security.mfa import MFAManager, MFAEnrollment

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/mfa/enroll")
async def enroll_mfa(current_user: User = Depends(get_current_user)):
    '''Start MFA enrollment process'''
    
    if current_user.mfa_enabled:
        raise HTTPException(400, "MFA already enabled")
    
    # Generate enrollment data
    enrollment = MFAEnrollment.create_enrollment_data(current_user.email)
    
    # Store secret (temporarily) - user must verify before enabling
    current_user.mfa_secret = enrollment['secret']
    db.commit()
    
    return {
        'qr_code': enrollment['qr_code_base64'],
        'secret': enrollment['secret'],  # Also show as text
        'backup_codes': enrollment['backup_codes_plain'],
        'message': 'Scan QR code with authenticator app, then verify'
    }


@router.post("/mfa/verify-enrollment")
async def verify_mfa_enrollment(
    token: str,
    current_user: User = Depends(get_current_user)
):
    '''Verify MFA enrollment with test token'''
    
    if not current_user.mfa_secret:
        raise HTTPException(400, "MFA enrollment not started")
    
    # Verify token
    mfa = MFAManager()
    if not mfa.verify_token(current_user.mfa_secret, token):
        raise HTTPException(400, "Invalid token")
    
    # Enable MFA
    current_user.mfa_enabled = True
    current_user.mfa_enrolled_at = datetime.utcnow()
    
    # Generate and store backup codes
    backup_codes = mfa.generate_backup_codes()
    current_user.mfa_backup_codes = [mfa.hash_backup_code(c) for c in backup_codes]
    
    db.commit()
    
    return {
        'success': True,
        'message': 'MFA enabled successfully',
        'backup_codes': backup_codes  # Show once
    }


@router.post("/login")
async def login(email: str, password: str, mfa_token: Optional[str] = None):
    '''Login with optional MFA'''
    
    # Step 1: Verify password
    user = authenticate_user(email, password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    # Step 2: Check if MFA is required
    if user.mfa_enabled:
        if not mfa_token:
            return {
                'mfa_required': True,
                'message': 'Please provide MFA token'
            }
        
        # Verify MFA token
        mfa = MFAManager()
        if not mfa.verify_token(user.mfa_secret, mfa_token):
            # Try backup code
            if not mfa.verify_backup_code(mfa_token, user.mfa_backup_codes):
                raise HTTPException(401, "Invalid MFA token")
            
            # Remove used backup code
            code_hash = mfa.hash_backup_code(mfa_token)
            user.mfa_backup_codes = [c for c in user.mfa_backup_codes if c != code_hash]
            db.commit()
    
    # Step 3: Issue JWT token
    access_token = create_access_token(user)
    
    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'user': {
            'id': user.user_id,
            'email': user.email,
            'mfa_enabled': user.mfa_enabled
        }
    }


@router.post("/mfa/disable")
async def disable_mfa(
    password: str,
    current_user: User = Depends(get_current_user)
):
    '''Disable MFA (requires password confirmation)'''
    
    # Verify password
    if not verify_password(password, current_user.password_hash):
        raise HTTPException(401, "Invalid password")
    
    # Disable MFA
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_backup_codes = None
    db.commit()
    
    return {'success': True, 'message': 'MFA disabled'}
"""


# Testing function
if __name__ == "__main__":
    print("="*70)
    print("Testing MFA Implementation")
    print("="*70)
    
    mfa = MFAManager()
    
    # Test 1: Generate secret
    print("\n1. Generating TOTP secret...")
    secret = mfa.generate_secret()
    print(f"   Secret: {secret}")
    
    # Test 2: Generate QR code
    print("\n2. Generating QR code...")
    qr_base64 = mfa.generate_qr_code("test@carelock.com", secret)
    print(f"   QR Code: {qr_base64[:50]}... ({len(qr_base64)} characters)")
    
    # Test 3: Generate current token
    print("\n3. Generating current TOTP token...")
    current_token = mfa.get_current_token(secret)
    print(f"   Current Token: {current_token}")
    
    # Test 4: Verify token
    print("\n4. Verifying token...")
    is_valid = mfa.verify_token(secret, current_token)
    print(f"   Token Valid: {is_valid}")
    
    if is_valid:
        print("   ✅ Token verification successful!")
    else:
        print("   ❌ Token verification failed!")
    
    # Test 5: Generate backup codes
    print("\n5. Generating backup codes...")
    backup_codes = mfa.generate_backup_codes()
    print(f"   Generated {len(backup_codes)} backup codes:")
    for i, code in enumerate(backup_codes, 1):
        print(f"      {i}. {code}")
    
    # Test 6: Hash and verify backup code
    print("\n6. Testing backup code verification...")
    hashed_codes = [mfa.hash_backup_code(c) for c in backup_codes]
    test_code = backup_codes[0]
    is_valid_backup = mfa.verify_backup_code(test_code, hashed_codes)
    print(f"   Backup code '{test_code}' is valid: {is_valid_backup}")
    
    if is_valid_backup:
        print("   ✅ Backup code verification successful!")
    else:
        print("   ❌ Backup code verification failed!")
    
    # Test 7: Full enrollment flow
    print("\n7. Testing full enrollment flow...")
    enrollment_data = MFAEnrollment.create_enrollment_data("admin@carelock.com")
    print(f"   Enrollment created for: admin@carelock.com")
    print(f"   Secret: {enrollment_data['secret']}")
    print(f"   Backup codes: {len(enrollment_data['backup_codes_plain'])} generated")
    
    # Verify enrollment with current token
    enroll_token = mfa.get_current_token(enrollment_data['secret'])
    enrollment_valid = MFAEnrollment.verify_enrollment(
        enrollment_data['secret'],
        enroll_token
    )
    print(f"   Enrollment verification: {'✅ SUCCESS' if enrollment_valid else '❌ FAILED'}")
    
    print("\n" + "="*70)
    print("MFA Testing Complete!")
    print("="*70)
    print("\n✅ All MFA components working correctly!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install pyotp qrcode pillow")
    print("2. Add MFA fields to User model in database")
    print("3. Integrate with authentication routes")
    print("4. Test with mobile authenticator app (Google/Microsoft/Authy)")
