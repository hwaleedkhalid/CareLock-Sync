"""
Pydantic schemas for API request and response models
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date, datetime


# Patient Schemas
class PatientBase(BaseModel):
    """Base patient schema"""
    medical_record_number: str = Field(..., max_length=50)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    date_of_birth: date
    gender: Optional[str] = Field(None, max_length=20)
    blood_type: Optional[str] = Field(None, max_length=10)
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)


class PatientCreate(PatientBase):
    """Schema for creating a patient"""
    pass


class PatientResponse(PatientBase):
    """Schema for patient response"""
    patient_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PatientList(BaseModel):
    """Schema for patient list response"""
    total: int
    patients: List[PatientResponse]


# Encounter Schemas
class EncounterBase(BaseModel):
    """Base encounter schema"""
    encounter_type: str = Field(..., max_length=50)
    admission_date: datetime
    discharge_date: Optional[datetime] = None
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    attending_physician: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)


class EncounterCreate(EncounterBase):
    """Schema for creating an encounter"""
    patient_id: int


class EncounterResponse(EncounterBase):
    """Schema for encounter response"""
    encounter_id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EncounterList(BaseModel):
    """Schema for encounter list response"""
    total: int
    encounters: List[EncounterResponse]


# Lab Result Schemas
class LabResultBase(BaseModel):
    """Base lab result schema"""
    test_name: str = Field(..., max_length=200)
    test_code: Optional[str] = Field(None, max_length=50)
    result_value: Optional[str] = Field(None, max_length=200)
    result_unit: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=100)
    abnormal_flag: Optional[str] = Field(None, max_length=20)
    performed_date: datetime


class LabResultCreate(LabResultBase):
    """Schema for creating a lab result"""
    patient_id: int
    encounter_id: int


class LabResultResponse(LabResultBase):
    """Schema for lab result response"""
    lab_id: int
    patient_id: int
    encounter_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class LabResultList(BaseModel):
    """Schema for lab result list response"""
    total: int
    lab_results: List[LabResultResponse]


# Medication Schemas
class MedicationBase(BaseModel):
    """Base medication schema"""
    medication_name: str = Field(..., max_length=200)
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)


class MedicationCreate(MedicationBase):
    """Schema for creating a medication"""
    patient_id: int
    encounter_id: int


class MedicationResponse(MedicationBase):
    """Schema for medication response"""
    medication_id: int
    patient_id: int
    encounter_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MedicationList(BaseModel):
    """Schema for medication list response"""
    total: int
    medications: List[MedicationResponse]


# Database Status Schemas
class DatabaseStatus(BaseModel):
    """Schema for database status"""
    database_name: str
    connected: bool
    latency_ms: Optional[float] = None       # real SELECT-1 round-trip (ms)
    total_patients: Optional[int] = None
    total_encounters: Optional[int] = None
    total_lab_results: Optional[int] = None
    total_medications: Optional[int] = None
    last_checked: datetime


class SystemStatus(BaseModel):
    """Schema for overall system status"""
    api_status: str
    uptime_seconds: Optional[float] = None   # real process uptime since start
    hospital_db: DatabaseStatus
    shared_db: DatabaseStatus
    timestamp: datetime
