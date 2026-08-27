"""
SQLAlchemy ORM models for Hospital Database with Multi-Tenancy Support
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, DECIMAL, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Tenant(Base):
    """Tenant model - represents individual hospitals/organizations"""
    __tablename__ = 'tenants'
    
    tenant_id = Column(Integer, primary_key=True, index=True)
    tenant_name = Column(String(255), nullable=False, unique=True)
    tenant_code = Column(String(50), nullable=False, unique=True, index=True)
    hospital_name = Column(String(255))
    address = Column(Text)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    is_active = Column(Boolean, default=True, index=True)
    onboarded_at = Column(DateTime, default=datetime.utcnow)
    offboarded_at = Column(DateTime)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patients = relationship("Patient", back_populates="tenant")
    encounters = relationship("Encounter", back_populates="tenant")
    
    def __repr__(self):
        return f"<Tenant(id={self.tenant_id}, code={self.tenant_code}, name={self.tenant_name})>"


class Patient(Base):
    """Patient model - represents patient demographic information"""
    __tablename__ = 'patients'
    
    patient_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.tenant_id'), nullable=False, index=True)
    medical_record_number = Column(String(50), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, index=True)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20))
    blood_type = Column(String(10))
    phone_number = Column(String(20))
    email = Column(String(100))
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(100))
    state = Column(String(50))
    zip_code = Column(String(20))
    emergency_contact_name = Column(String(200))
    emergency_contact_phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="patients")
    encounters = relationship("Encounter", back_populates="patient")
    
    def __repr__(self):
        return f"<Patient(id={self.patient_id}, tenant_id={self.tenant_id}, mrn={self.medical_record_number})>"


class Encounter(Base):
    """Encounter model - represents hospital visits"""
    __tablename__ = 'encounters'
    
    encounter_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.tenant_id'), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey('patients.patient_id'), nullable=False, index=True)
    encounter_type = Column(String(50), nullable=False)
    admission_date = Column(DateTime, nullable=False, index=True)
    discharge_date = Column(DateTime)
    chief_complaint = Column(Text)
    diagnosis = Column(Text)
    attending_physician = Column(String(200))
    department = Column(String(100))
    room_number = Column(String(20))
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="encounters")
    patient = relationship("Patient", back_populates="encounters")
    
    def __repr__(self):
        return f"<Encounter(id={self.encounter_id}, tenant_id={self.tenant_id}, patient_id={self.patient_id})>"


class LabResult(Base):
    """LabResult model - laboratory test results"""
    __tablename__ = 'lab_results'
    
    lab_result_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.tenant_id'), nullable=False, index=True)
    encounter_id = Column(Integer, ForeignKey('encounters.encounter_id'), index=True)
    patient_id = Column(Integer, ForeignKey('patients.patient_id'), nullable=False, index=True)
    test_name = Column(String(200))
    result_value = Column(String(200))
    unit = Column(String(50))
    reference_range = Column(String(100))
    status = Column(String(50))
    performed_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<LabResult(id={self.lab_result_id}, tenant_id={self.tenant_id}, test={self.test_name})>"


class Medication(Base):
    """Medication model - patient medications"""
    __tablename__ = 'medications'
    
    medication_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.tenant_id'), nullable=False, index=True)
    encounter_id = Column(Integer, ForeignKey('encounters.encounter_id'), index=True)
    patient_id = Column(Integer, ForeignKey('patients.patient_id'), nullable=False, index=True)
    medication_name = Column(String(200))
    dosage = Column(String(100))
    frequency = Column(String(100))
    route = Column(String(50))
    start_date = Column(Date)
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Medication(id={self.medication_id}, tenant_id={self.tenant_id}, name={self.medication_name})>"


class TenantAuditLog(Base):
    """Audit log for tenant operations"""
    __tablename__ = 'tenant_audit_log'
    
    audit_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.tenant_id'), index=True)
    action = Column(String(50), nullable=False, index=True)
    table_name = Column(String(100))
    record_id = Column(Integer)
    user_id = Column(Integer)
    changes = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<TenantAuditLog(id={self.audit_id}, tenant_id={self.tenant_id}, action={self.action})>"
