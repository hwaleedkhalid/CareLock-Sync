"""
Schema Mapping Service
Orchestrates the mapping from hospital schema to FHIR resources
"""
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
import sys
import os

# Fix imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from common.database import get_hospital_db, hospital_db_session
from common.models import Patient, Encounter, LabResult, Medication

# Import from same directory
from mapping_config import MappingConfig
from data_transformer import FHIRMapper


class MappingService:
    """
    Service for mapping hospital data to FHIR resources
    """
    
    def __init__(self):
        """Initialize mapping service"""
        self.mappings = MappingConfig.get_all_mappings()
    
    def _model_to_dict(self, model_instance) -> Dict:
        """Convert SQLAlchemy model to dictionary.

        Uses the Python attribute name (mapper key) as the dict key so that
        field_mappings in fhir_mappings.json can reference the Python name
        (e.g. 'medical_record_number') rather than the DB column name ('mrn').
        """
        result = {}
        for attr in model_instance.__mapper__.column_attrs:
            result[attr.key] = getattr(model_instance, attr.key)
        return result
    
    def map_patient_to_fhir(self, patient: Patient) -> Dict:
        """
        Map a patient record to FHIR Patient resource
        
        Args:
            patient: Patient SQLAlchemy model
            
        Returns:
            FHIR Patient resource dictionary
        """
        mapper = FHIRMapper(self.mappings['patient'])
        patient_dict = self._model_to_dict(patient)
        return mapper.map_record(patient_dict)
    
    def map_encounter_to_fhir(self, encounter: Encounter) -> Dict:
        """
        Map an encounter record to FHIR Encounter resource
        
        Args:
            encounter: Encounter SQLAlchemy model
            
        Returns:
            FHIR Encounter resource dictionary
        """
        mapper = FHIRMapper(self.mappings['encounter'])
        encounter_dict = self._model_to_dict(encounter)
        return mapper.map_record(encounter_dict)
    
    def map_lab_result_to_fhir(self, lab_result: LabResult) -> Dict:
        """
        Map a lab result to FHIR Observation resource
        
        Args:
            lab_result: LabResult SQLAlchemy model
            
        Returns:
            FHIR Observation resource dictionary
        """
        mapper = FHIRMapper(self.mappings['observation'])
        lab_dict = self._model_to_dict(lab_result)
        return mapper.map_record(lab_dict)
    
    def map_medication_to_fhir(self, medication: Medication) -> Dict:
        """
        Map a medication to FHIR MedicationRequest resource
        
        Args:
            medication: Medication SQLAlchemy model
            
        Returns:
            FHIR MedicationRequest resource dictionary
        """
        mapper = FHIRMapper(self.mappings['medication_request'])
        med_dict = self._model_to_dict(medication)
        return mapper.map_record(med_dict)
    
    def map_patients_batch(self, db: Session, limit: int = 100) -> List[Dict]:
        """
        Map multiple patients to FHIR in batch
        
        Args:
            db: Database session
            limit: Number of records to process
            
        Returns:
            List of FHIR Patient resources
        """
        patients = db.query(Patient).limit(limit).all()
        return [self.map_patient_to_fhir(p) for p in patients]
    
    def map_encounters_batch(self, db: Session, limit: int = 100) -> List[Dict]:
        """
        Map multiple encounters to FHIR in batch
        
        Args:
            db: Database session
            limit: Number of records to process
            
        Returns:
            List of FHIR Encounter resources
        """
        encounters = db.query(Encounter).limit(limit).all()
        return [self.map_encounter_to_fhir(e) for e in encounters]
    
    def get_patient_bundle(self, db: Session, patient_id: int) -> Dict:
        """
        Get a complete FHIR Bundle for a patient including all related resources
        
        Args:
            db: Database session
            patient_id: Patient ID
            
        Returns:
            FHIR Bundle containing patient and related resources
        """
        # Get patient
        patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
        if not patient:
            return None
        
        bundle_entries = []
        
        # Add patient resource
        patient_resource = self.map_patient_to_fhir(patient)
        bundle_entries.append({
            "resource": patient_resource,
            "fullUrl": f"Patient/{patient_id}"
        })
        
        # Add encounters
        encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).all()
        for encounter in encounters:
            encounter_resource = self.map_encounter_to_fhir(encounter)
            bundle_entries.append({
                "resource": encounter_resource,
                "fullUrl": f"Encounter/{encounter.encounter_id}"
            })
        
        # Add lab results
        lab_results = db.query(LabResult).filter(LabResult.patient_id == patient_id).all()
        for lab in lab_results:
            lab_resource = self.map_lab_result_to_fhir(lab)
            bundle_entries.append({
                "resource": lab_resource,
                "fullUrl": f"Observation/{lab.lab_id}"
            })
        
        # Add medications
        medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        for med in medications:
            med_resource = self.map_medication_to_fhir(med)
            bundle_entries.append({
                "resource": med_resource,
                "fullUrl": f"MedicationRequest/{med.medication_id}"
            })
        
        # Create FHIR Bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "total": len(bundle_entries),
            "entry": bundle_entries
        }
        
        return bundle


if __name__ == "__main__":
    # Test mapping service
    print("=" * 60)
    print("Testing Mapping Service")
    print("=" * 60)
    
    service = MappingService()
    
    with hospital_db_session() as db:
        # Test patient mapping
        print("\n[1/4] Testing Patient Mapping...")
        patient = db.query(Patient).first()
        if patient:
            fhir_patient = service.map_patient_to_fhir(patient)
            print(f"  Patient ID: {fhir_patient.get('id')}")
            print(f"  Name: {fhir_patient.get('name', [{}])[0].get('given', ['N/A'])[0]} " +
                  f"{fhir_patient.get('name', [{}])[0].get('family', 'N/A')}")
            print(f"  Birth Date: {fhir_patient.get('birthDate')}")
            print(f"  Gender: {fhir_patient.get('gender')}")
        
        # Test encounter mapping
        print("\n[2/4] Testing Encounter Mapping...")
        encounter = db.query(Encounter).first()
        if encounter:
            fhir_encounter = service.map_encounter_to_fhir(encounter)
            print(f"  Encounter ID: {fhir_encounter.get('id')}")
            print(f"  Class: {fhir_encounter.get('class', {}).get('code')}")
            print(f"  Status: {fhir_encounter.get('status')}")
            print(f"  Period Start: {fhir_encounter.get('period', {}).get('start')}")
        
        # Test lab result mapping
        print("\n[3/4] Testing Lab Result Mapping...")
        lab = db.query(LabResult).first()
        if lab:
            fhir_obs = service.map_lab_result_to_fhir(lab)
            print(f"  Observation ID: {fhir_obs.get('id')}")
            print(f"  Test: {fhir_obs.get('code', {}).get('text')}")
            value_qty = fhir_obs.get('valueQuantity', {})
            print(f"  Value: {value_qty.get('value')} {value_qty.get('unit', '')}")
        
        # Test medication mapping
        print("\n[4/4] Testing Medication Mapping...")
        med = db.query(Medication).first()
        if med:
            fhir_med = service.map_medication_to_fhir(med)
            print(f"  MedicationRequest ID: {fhir_med.get('id')}")
            print(f"  Medication: {fhir_med.get('medicationCodeableConcept', {}).get('text')}")
            print(f"  Status: {fhir_med.get('status')}")
        
        # Test patient bundle
        print("\n[5/5] Testing Patient Bundle...")
        if patient:
            bundle = service.get_patient_bundle(db, patient.patient_id)
            print(f"  Bundle Type: {bundle.get('type')}")
            print(f"  Total Resources: {bundle.get('total')}")
            print(f"  Resource Types: ", end="")
            resource_types = [entry['resource']['resourceType'] 
                            for entry in bundle.get('entry', [])]
            print(", ".join(set(resource_types)))
    
    print("\n[OK] Mapping service tests complete")
