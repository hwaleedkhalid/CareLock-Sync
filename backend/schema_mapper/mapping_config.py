"""
FHIR Resource Mapping Configuration
Defines mappings from hospital database schema to FHIR R4 resources
"""
from typing import Dict, List, Optional, Any
from enum import Enum
import json


class FHIRResourceType(Enum):
    """FHIR R4 Resource Types"""
    PATIENT = "Patient"
    ENCOUNTER = "Encounter"
    OBSERVATION = "Observation"
    MEDICATION_REQUEST = "MedicationRequest"
    CONDITION = "Condition"
    PROCEDURE = "Procedure"
    DIAGNOSTIC_REPORT = "DiagnosticReport"


class DataType(Enum):
    """Data type mappings"""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "dateTime"
    BOOLEAN = "boolean"
    CODE = "code"
    CODING = "coding"
    IDENTIFIER = "identifier"


class MappingConfig:
    """
    Configuration for mapping hospital schema to FHIR resources
    """
    
    # Patient Resource Mapping
    PATIENT_MAPPING = {
        "source_table": "patients",
        "target_resource": FHIRResourceType.PATIENT.value,
        "field_mappings": [
            {
                "source_field": "patient_id",
                "target_path": "id",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "to_string"
            },
            {
                "source_field": "medical_record_number",
                "target_path": "identifier[0].value",
                "data_type": DataType.STRING.value,
                "required": True,
                "transformation": None
            },
            {
                "source_field": "first_name",
                "target_path": "name[0].given[0]",
                "data_type": DataType.STRING.value,
                "required": True,
                "transformation": None
            },
            {
                "source_field": "last_name",
                "target_path": "name[0].family",
                "data_type": DataType.STRING.value,
                "required": True,
                "transformation": None
            },
            {
                "source_field": "date_of_birth",
                "target_path": "birthDate",
                "data_type": DataType.DATE.value,
                "required": True,
                "transformation": "format_date"
            },
            {
                "source_field": "gender",
                "target_path": "gender",
                "data_type": DataType.CODE.value,
                "required": False,
                "transformation": "normalize_gender"
            },
            {
                "source_field": "phone_number",
                "target_path": "telecom[0].value",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "email",
                "target_path": "telecom[1].value",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "address_line1",
                "target_path": "address[0].line[0]",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "city",
                "target_path": "address[0].city",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "state",
                "target_path": "address[0].state",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "zip_code",
                "target_path": "address[0].postalCode",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            }
        ]
    }
    
    # Encounter Resource Mapping
    ENCOUNTER_MAPPING = {
        "source_table": "encounters",
        "target_resource": FHIRResourceType.ENCOUNTER.value,
        "field_mappings": [
            {
                "source_field": "encounter_id",
                "target_path": "id",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "to_string"
            },
            {
                "source_field": "patient_id",
                "target_path": "subject.reference",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "patient_reference"
            },
            {
                "source_field": "encounter_type",
                "target_path": "class.code",
                "data_type": DataType.CODE.value,
                "required": True,
                "transformation": "map_encounter_class"
            },
            {
                "source_field": "admission_date",
                "target_path": "period.start",
                "data_type": DataType.DATETIME.value,
                "required": True,
                "transformation": "format_datetime"
            },
            {
                "source_field": "discharge_date",
                "target_path": "period.end",
                "data_type": DataType.DATETIME.value,
                "required": False,
                "transformation": "format_datetime"
            },
            {
                "source_field": "status",
                "target_path": "status",
                "data_type": DataType.CODE.value,
                "required": True,
                "transformation": "map_encounter_status"
            },
            {
                "source_field": "chief_complaint",
                "target_path": "reasonCode[0].text",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "diagnosis",
                "target_path": "diagnosis[0].condition.display",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "attending_physician",
                "target_path": "participant[0].individual.display",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "department",
                "target_path": "serviceType.text",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            }
        ]
    }
    
    # Observation Resource Mapping (Lab Results)
    OBSERVATION_MAPPING = {
        "source_table": "lab_results",
        "target_resource": FHIRResourceType.OBSERVATION.value,
        "field_mappings": [
            {
                "source_field": "lab_result_id",   # actual PK column
                "target_path": "id",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "to_string"
            },
            {
                "source_field": "patient_id",
                "target_path": "subject.reference",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "patient_reference"
            },
            {
                "source_field": "encounter_id",
                "target_path": "encounter.reference",
                "data_type": DataType.INTEGER.value,
                "required": False,
                "transformation": "encounter_reference"
            },
            {
                "source_field": "test_name",
                "target_path": "code.text",
                "data_type": DataType.STRING.value,
                "required": True,
                "transformation": None
            },
            {
                "source_field": "result_value",
                "target_path": "valueQuantity.value",
                "data_type": DataType.DECIMAL.value,
                "required": False,
                "transformation": "to_decimal"
            },
            {
                "source_field": "unit",             # actual column (was result_unit)
                "target_path": "valueQuantity.unit",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "reference_range",
                "target_path": "referenceRange[0].text",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "status",           # actual column (was abnormal_flag)
                "target_path": "status",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "performed_date",
                "target_path": "effectiveDateTime",
                "data_type": DataType.DATETIME.value,
                "required": True,
                "transformation": "format_datetime"
            }
        ]
    }
    
    # MedicationRequest Resource Mapping
    MEDICATION_REQUEST_MAPPING = {
        "source_table": "medications",
        "target_resource": FHIRResourceType.MEDICATION_REQUEST.value,
        "field_mappings": [
            {
                "source_field": "medication_id",
                "target_path": "id",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "to_string"
            },
            {
                "source_field": "patient_id",
                "target_path": "subject.reference",
                "data_type": DataType.INTEGER.value,
                "required": True,
                "transformation": "patient_reference"
            },
            {
                "source_field": "encounter_id",
                "target_path": "encounter.reference",
                "data_type": DataType.INTEGER.value,
                "required": False,
                "transformation": "encounter_reference"
            },
            {
                "source_field": "medication_name",
                "target_path": "medicationCodeableConcept.text",
                "data_type": DataType.STRING.value,
                "required": True,
                "transformation": None
            },
            {
                "source_field": "dosage",
                "target_path": "dosageInstruction[0].doseAndRate[0].doseQuantity.value",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": "extract_dosage_value"
            },
            {
                "source_field": "frequency",
                "target_path": "dosageInstruction[0].timing.code.text",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "route",
                "target_path": "dosageInstruction[0].route.text",
                "data_type": DataType.STRING.value,
                "required": False,
                "transformation": None
            },
            {
                "source_field": "start_date",
                "target_path": "authoredOn",
                "data_type": DataType.DATE.value,
                "required": True,
                "transformation": "format_date"
            },
            {
                "source_field": "status",
                "target_path": "status",
                "data_type": DataType.CODE.value,
                "required": True,
                "transformation": "map_medication_status"
            }
        ]
    }
    
    @classmethod
    def get_all_mappings(cls) -> Dict[str, Dict]:
        """Get all mapping configurations"""
        return {
            "patient": cls.PATIENT_MAPPING,
            "encounter": cls.ENCOUNTER_MAPPING,
            "observation": cls.OBSERVATION_MAPPING,
            "medication_request": cls.MEDICATION_REQUEST_MAPPING
        }
    
    @classmethod
    def get_mapping_by_table(cls, table_name: str) -> Optional[Dict]:
        """Get mapping configuration for a specific table"""
        mappings = cls.get_all_mappings()
        for key, mapping in mappings.items():
            if mapping["source_table"] == table_name:
                return mapping
        return None
    
    @classmethod
    def export_mappings_to_json(cls, output_file: str):
        """Export all mappings to JSON file"""
        mappings = cls.get_all_mappings()
        with open(output_file, 'w') as f:
            json.dump(mappings, f, indent=2)
        print(f"Mappings exported to {output_file}")


if __name__ == "__main__":
    # Test mapping configuration
    print("=" * 60)
    print("FHIR Mapping Configuration")
    print("=" * 60)
    
    mappings = MappingConfig.get_all_mappings()
    
    for key, mapping in mappings.items():
        print(f"\n{key.upper()}:")
        print(f"  Source Table: {mapping['source_table']}")
        print(f"  Target Resource: {mapping['target_resource']}")
        print(f"  Field Mappings: {len(mapping['field_mappings'])}")
    
    # Export to JSON
    MappingConfig.export_mappings_to_json("fhir_mappings.json")
    print("\n[OK] Mapping configuration ready")
