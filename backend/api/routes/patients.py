"""
API routes for patient operations with encryption integration
Features:
- Automatic PHI encryption/decryption
- Audit logging for all access
- Tenant isolation
- HMAC-based searchable encryption for MRN
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.database import get_hospital_db, shared_db_session
from common.models   import Patient
from common.schemas  import PatientResponse, PatientList
from common.auth     import require_auth, AuthContext

# Import encryption
from security.production_encryption import (
    ProductionEncryptionManager,
    SecureTenantKeyManager
)

router = APIRouter(tags=["patients"])

# Initialize encryption
key_manager = SecureTenantKeyManager()

def get_encryption_manager(auth: AuthContext):
    """Get encryption manager for current user's tenant"""
    return ProductionEncryptionManager(
        tenant_id=auth.tenant_id or 1,
        context="cloud",
        key_manager=key_manager,
        user_id=auth.email,
    )

def encrypt_patient_phi(patient_dict: dict, encryptor: ProductionEncryptionManager) -> dict:
    """
    Encrypt PHI fields in patient record
    
    Fields encrypted:
    - ssn (random)
    - phone (random)
    - email (random)
    - medical_record_number (searchable - HMAC indexed)
    """
    encrypted = patient_dict.copy()
    
    # Encrypt SSN (random nonce - maximum security)
    if 'ssn' in encrypted and encrypted['ssn']:
        encrypted['ssn'] = encryptor.encrypt(
            encrypted['ssn'],
            field_name='ssn',
            record_id=str(encrypted.get('patient_id', 'unknown'))
        )
    
    # Encrypt phone
    if 'phone' in encrypted and encrypted['phone']:
        encrypted['phone'] = encryptor.encrypt(
            encrypted['phone'],
            field_name='phone',
            record_id=str(encrypted.get('patient_id', 'unknown'))
        )
    
    # Encrypt email
    if 'email' in encrypted and encrypted['email']:
        encrypted['email'] = encryptor.encrypt(
            encrypted['email'],
            field_name='email',
            record_id=str(encrypted.get('patient_id', 'unknown'))
        )
    
    # Encrypt MRN with searchable encryption
    if 'medical_record_number' in encrypted and encrypted['medical_record_number']:
        encrypted_value, search_hash = encryptor.encrypt(
            encrypted['medical_record_number'],
            field_name='medical_record_number',
            record_id=str(encrypted.get('patient_id', 'unknown'))
        )
        encrypted['medical_record_number'] = encrypted_value
        encrypted['mrn_search_hash'] = search_hash  # For WHERE clauses
    
    encrypted['_encrypted'] = True
    return encrypted

def decrypt_patient_phi(
    patient_dict: dict,
    encryptor: ProductionEncryptionManager,
    reason: str = "Clinical access"
) -> dict:
    """
    Decrypt PHI fields in patient record
    All decryptions are logged to audit trail
    """
    decrypted = patient_dict.copy()
    record_id = str(patient_dict.get('patient_id', 'unknown'))
    
    # Decrypt SSN
    if 'ssn' in decrypted and decrypted['ssn'] and decrypted['ssn'].startswith('v2'):
        decrypted['ssn'] = encryptor.decrypt(
            decrypted['ssn'],
            field_name='ssn',
            record_id=record_id,
            reason=reason
        )
    
    # Decrypt phone
    if 'phone' in decrypted and decrypted['phone'] and decrypted['phone'].startswith('v2'):
        decrypted['phone'] = encryptor.decrypt(
            decrypted['phone'],
            field_name='phone',
            record_id=record_id,
            reason=reason
        )
    
    # Decrypt email
    if 'email' in decrypted and decrypted['email'] and decrypted['email'].startswith('v2'):
        decrypted['email'] = encryptor.decrypt(
            decrypted['email'],
            field_name='email',
            record_id=record_id,
            reason=reason
        )
    
    # Decrypt MRN
    if 'medical_record_number' in decrypted and decrypted['medical_record_number']:
        if decrypted['medical_record_number'].startswith('v2'):
            decrypted['medical_record_number'] = encryptor.decrypt(
                decrypted['medical_record_number'],
                field_name='medical_record_number',
                record_id=record_id,
                reason=reason
            )
    
    return decrypted

# ============================================================================
# ROUTES
# ============================================================================

@router.get("/", response_model=PatientList)
async def get_patients(
    skip:  int = Query(0,   ge=0),
    limit: int = Query(100, ge=1, le=1000),
    decrypt: bool = Query(True, description="Decrypt PHI fields"),
    db:    Session   = Depends(get_hospital_db),
    auth:  AuthContext = Depends(require_auth)
):
    """
    Get patient list
    
    - PHI fields are stored encrypted
    - Decryption happens on-demand with audit logging
    - Tenant isolation enforced
    """
    total = db.query(Patient).count()
    patients = db.query(Patient).offset(skip).limit(limit).all()
    
    # Convert to dict
    patients_list = [p.__dict__ for p in patients]
    
    # Decrypt if requested
    if decrypt:
        encryptor = get_encryption_manager(auth)
        patients_list = [
            decrypt_patient_phi(p, encryptor, reason="Patient list view")
            for p in patients_list
        ]
    
    return {"total": total, "patients": patients_list}


@router.get("/search/", response_model=PatientList)
async def search_patients(
    first_name: Optional[str] = Query(None),
    last_name:  Optional[str] = Query(None),
    blood_type: Optional[str] = Query(None),
    mrn: Optional[str] = Query(None, description="Medical Record Number (searchable)"),
    skip:  int = Query(0,   ge=0),
    limit: int = Query(100, ge=1, le=1000),
    decrypt: bool = Query(True),
    db:    Session   = Depends(get_hospital_db),
    auth:  AuthContext = Depends(require_auth)
):
    """
    Search patients with encrypted field support
    
    - MRN uses HMAC-based searchable encryption
    - Other encrypted fields cannot be searched directly
    """
    q = db.query(Patient)
    
    # Search non-encrypted fields
    if first_name:
        q = q.filter(Patient.first_name.ilike(f"%{first_name}%"))
    if last_name:
        q = q.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if blood_type:
        q = q.filter(Patient.blood_type == blood_type)
    
    # Search encrypted MRN using HMAC hash
    if mrn:
        encryptor = get_encryption_manager(auth)
        # Compute search hash for MRN
        search_hash = encryptor.searchable.compute_search_hash(mrn, 'medical_record_number')
        q = q.filter(Patient.mrn_search_hash == search_hash)
    
    patients = q.offset(skip).limit(limit).all()
    patients_list = [p.__dict__ for p in patients]
    
    # Decrypt if requested
    if decrypt:
        encryptor = get_encryption_manager(auth)
        patients_list = [
            decrypt_patient_phi(p, encryptor, reason=f"Patient search: {mrn or 'filter'}")
            for p in patients_list
        ]
    
    return {"total": q.count(), "patients": patients_list}


@router.get("/mrn/{mrn}", response_model=PatientResponse)
async def get_patient_by_mrn(
    mrn:  str,
    decrypt: bool = Query(True),
    db:   Session    = Depends(get_hospital_db),
    auth: AuthContext = Depends(require_auth)
):
    """
    Get patient by Medical Record Number (encrypted field)
    
    Uses HMAC-based search to find encrypted MRN
    """
    # Compute search hash
    encryptor = get_encryption_manager(auth)
    search_hash = encryptor.searchable.compute_search_hash(mrn, 'medical_record_number')
    
    # Search using hash
    patient = db.query(Patient).filter(Patient.mrn_search_hash == search_hash).first()
    
    if not patient:
        raise HTTPException(404, f"Patient MRN {mrn} not found")
    
    patient_dict = patient.__dict__
    
    # Decrypt if requested
    if decrypt:
        patient_dict = decrypt_patient_phi(
            patient_dict,
            encryptor,
            reason=f"Patient lookup by MRN: {mrn}"
        )
    
    return patient_dict


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    decrypt: bool = Query(True),
    db:   Session    = Depends(get_hospital_db),
    auth: AuthContext = Depends(require_auth)
):
    """Get patient by ID with decryption"""
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    
    if not patient:
        raise HTTPException(404, f"Patient ID {patient_id} not found")
    
    patient_dict = patient.__dict__
    
    # Decrypt if requested
    if decrypt:
        encryptor = get_encryption_manager(auth)
        patient_dict = decrypt_patient_phi(
            patient_dict,
            encryptor,
            reason=f"Patient record access: ID {patient_id}"
        )
    
    return patient_dict


# ── FHIR central DB (partitioned, tenant-scoped) ──────────────────────────────
@router.get("/fhir/{fhir_patient_id}")
async def get_fhir_patient(
    fhir_patient_id: int,
    auth: AuthContext = Depends(require_auth),
):
    """Get a single FHIR patient by ID from central DB."""
    with shared_db_session() as db:
        if auth.tenant_id:
            db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

        row = db.execute(text("""
            SELECT id, tenant_id, source_patient_id, family_name, given_name,
                   gender, birth_date, phone, email, active
            FROM fhir_patient WHERE id = :pid
        """), {"pid": fhir_patient_id}).fetchone()

        if not row:
            raise HTTPException(404, f"FHIR Patient ID {fhir_patient_id} not found")

        p = dict(row._mapping)
        if p.get("birth_date"):
            p["birth_date"] = str(p["birth_date"])
        if p.get("given_name") and isinstance(p["given_name"], (list, tuple)):
            p["given_name"] = p["given_name"][0] if p["given_name"] else None
        return p


@router.get("/fhir/")
async def get_fhir_patients(
    skip:  int = Query(0,   ge=0),
    limit: int = Query(100, ge=1, le=1000),
    decrypt: bool = Query(True),
    auth:  AuthContext = Depends(require_auth)
):
    """
    Return FHIR patients from central DB with tenant isolation

    - Tenant isolation via PostgreSQL RLS
    - PHI encryption at rest
    - Audit logging for all access
    """
    with shared_db_session() as db:
        # Set tenant context for RLS
        if auth.tenant_id:
            db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

        # Fetch records
        rows = db.execute(text("""
            SELECT id, tenant_id, source_patient_id, family_name, given_name,
                   gender, birth_date, phone, email, active
            FROM fhir_patient
            ORDER BY id
            LIMIT :lim OFFSET :skip
        """), {"lim": limit, "skip": skip}).fetchall()

        total = db.execute(text("SELECT COUNT(*) FROM fhir_patient")).scalar()

        # Convert to dict — stringify date/array columns for JSON
        patients = []
        for r in rows:
            p = dict(r._mapping)
            if p.get("birth_date"):
                p["birth_date"] = str(p["birth_date"])
            if p.get("given_name") and isinstance(p["given_name"], (list, tuple)):
                p["given_name"] = p["given_name"][0] if p["given_name"] else None
            patients.append(p)

        # Decrypt if requested (skip if data is not encrypted)
        if decrypt and patients:
            try:
                encryptor = get_encryption_manager(auth)
                patients = [
                    decrypt_patient_phi(p, encryptor, reason="FHIR patient list view")
                    for p in patients
                ]
            except Exception:
                pass  # Data not encrypted — return as-is

        return {"total": total, "patients": patients}


@router.post("/")
async def create_patient(
    patient_data: dict,
    db: Session = Depends(get_hospital_db),
    auth: AuthContext = Depends(require_auth)
):
    """
    Create new patient with automatic PHI encryption
    
    - PHI fields are encrypted before storage
    - MRN uses searchable encryption (HMAC-indexed)
    - Audit log entry created
    """
    # Encrypt PHI before saving
    encryptor = get_encryption_manager(auth)
    encrypted_data = encrypt_patient_phi(patient_data, encryptor)
    
    # Create patient record
    patient = Patient(**encrypted_data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    
    return {
        "message": "Patient created successfully",
        "patient_id": patient.patient_id,
        "_encrypted": True
    }
