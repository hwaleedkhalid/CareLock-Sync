"""
Data Transformation Engine
Transforms hospital database records to FHIR resources
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import re


class DataTransformer:
    """
    Transforms data from hospital schema to FHIR format
    """
    
    @staticmethod
    def to_string(value: Any) -> str:
        """Convert any value to string"""
        if value is None:
            return None
        return str(value)
    
    @staticmethod
    def to_decimal(value: Any) -> Optional[float]:
        """Convert value to decimal/float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def format_date(value: Any) -> Optional[str]:
        """Format date to FHIR date format (YYYY-MM-DD)"""
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        elif isinstance(value, date):
            return value.strftime('%Y-%m-%d')
        elif isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        
        return str(value)
    
    @staticmethod
    def format_datetime(value: Any) -> Optional[str]:
        """Format datetime to FHIR dateTime format (YYYY-MM-DDTHH:MM:SS)"""
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        elif isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%S')
        
        return str(value)
    
    @staticmethod
    def normalize_gender(value: Any) -> Optional[str]:
        """Normalize gender to FHIR codes: male, female, other, unknown"""
        if value is None:
            return "unknown"
        
        gender_str = str(value).lower().strip()
        
        if gender_str in ['m', 'male', 'man']:
            return "male"
        elif gender_str in ['f', 'female', 'woman']:
            return "female"
        elif gender_str in ['o', 'other']:
            return "other"
        else:
            return "unknown"
    
    @staticmethod
    def patient_reference(patient_id: Any) -> str:
        """Create FHIR patient reference"""
        return f"Patient/{patient_id}"
    
    @staticmethod
    def encounter_reference(encounter_id: Any) -> str:
        """Create FHIR encounter reference"""
        if encounter_id is None:
            return None
        return f"Encounter/{encounter_id}"
    
    @staticmethod
    def map_encounter_class(encounter_type: str) -> str:
        """Map encounter type to FHIR encounter class codes"""
        if encounter_type is None:
            return "AMB"  # Ambulatory (default)
        
        type_str = str(encounter_type).lower()
        
        mapping = {
            'inpatient': 'IMP',      # Inpatient
            'outpatient': 'AMB',     # Ambulatory
            'emergency': 'EMER',     # Emergency
            'home': 'HH',            # Home Health
            'virtual': 'VR'          # Virtual
        }
        
        return mapping.get(type_str, 'AMB')
    
    @staticmethod
    def map_encounter_status(status: str) -> str:
        """Map encounter status to FHIR status codes"""
        if status is None:
            return "unknown"
        
        status_str = str(status).lower()
        
        mapping = {
            'active': 'in-progress',
            'discharged': 'finished',
            'cancelled': 'cancelled',
            'transferred': 'in-progress',
            'planned': 'planned'
        }
        
        return mapping.get(status_str, 'unknown')
    
    @staticmethod
    def map_abnormal_flag(flag: str) -> str:
        """Map abnormal flag to FHIR interpretation codes"""
        if flag is None:
            return None
        
        flag_str = str(flag).lower()
        
        mapping = {
            'normal': 'N',           # Normal
            'high': 'H',             # High
            'low': 'L',              # Low
            'critical': 'HH',        # Critical high
            'abnormal': 'A'          # Abnormal
        }
        
        return mapping.get(flag_str, 'N')
    
    @staticmethod
    def map_medication_status(status: str) -> str:
        """Map medication status to FHIR status codes"""
        if status is None:
            return "unknown"
        
        status_str = str(status).lower()
        
        mapping = {
            'active': 'active',
            'completed': 'completed',
            'discontinued': 'stopped',
            'cancelled': 'cancelled',
            'on-hold': 'on-hold'
        }
        
        return mapping.get(status_str, 'unknown')
    
    @staticmethod
    def extract_dosage_value(dosage_str: str) -> Optional[str]:
        """Extract numeric value from dosage string (e.g., '10mg' -> '10')"""
        if dosage_str is None:
            return None
        
        # Extract first number from string
        match = re.search(r'(\d+\.?\d*)', str(dosage_str))
        if match:
            return match.group(1)
        
        return None
    
    @classmethod
    def apply_transformation(cls, value: Any, transformation: str) -> Any:
        """Apply a transformation function by name"""
        if transformation is None or value is None:
            return value
        
        # Get transformation method
        transform_method = getattr(cls, transformation, None)
        
        if transform_method and callable(transform_method):
            return transform_method(value)
        
        # If no transformation found, return original value
        return value


class FHIRMapper:
    """
    Maps hospital database records to FHIR resources
    """
    
    def __init__(self, mapping_config: Dict):
        """
        Initialize mapper with configuration
        
        Args:
            mapping_config: Mapping configuration dictionary
        """
        self.mapping_config = mapping_config
        self.transformer = DataTransformer()
    
    def set_nested_value(self, obj: Dict, path: str, value: Any):
        """
        Set a value in a nested dictionary using dot/bracket notation
        
        Args:
            obj: Target dictionary
            path: Path like 'name[0].given[0]' or 'address.city'
            value: Value to set
        """
        if value is None:
            return
        
        # Parse path with arrays
        parts = re.findall(r'(\w+)|\[(\d+)\]', path)
        
        current = obj
        for i, (key, index) in enumerate(parts[:-1]):
            if key:
                # Object key
                if key not in current:
                    # Look ahead to see if next is array
                    next_part = parts[i + 1]
                    if next_part[1]:  # Next is array index
                        current[key] = []
                    else:
                        current[key] = {}
                current = current[key]
            elif index:
                # Array index
                idx = int(index)
                # Ensure array is large enough
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
        
        # Set final value
        last_key, last_index = parts[-1]
        if last_key:
            current[last_key] = value
        elif last_index:
            idx = int(last_index)
            while len(current) <= idx:
                current.append(None)
            current[idx] = value
    
    def map_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a single database record to FHIR resource
        
        Args:
            record: Database record dictionary
            
        Returns:
            FHIR resource dictionary
        """
        fhir_resource = {
            "resourceType": self.mapping_config["target_resource"]
        }
        
        # Apply each field mapping
        for field_mapping in self.mapping_config["field_mappings"]:
            source_field = field_mapping["source_field"]
            target_path = field_mapping["target_path"]
            transformation = field_mapping.get("transformation")
            
            # Get source value
            source_value = record.get(source_field)
            
            # Apply transformation
            transformed_value = self.transformer.apply_transformation(
                source_value, 
                transformation
            )
            
            # Set in target
            self.set_nested_value(fhir_resource, target_path, transformed_value)
        
        return fhir_resource
    
    def map_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Map multiple database records to FHIR resources
        
        Args:
            records: List of database record dictionaries
            
        Returns:
            List of FHIR resource dictionaries
        """
        return [self.map_record(record) for record in records]


if __name__ == "__main__":
    # Test data transformation
    print("=" * 60)
    print("Testing Data Transformation")
    print("=" * 60)
    
    transformer = DataTransformer()
    
    # Test transformations
    print("\nDate Formatting:")
    print(f"  Date: {transformer.format_date(date(2024, 1, 15))}")
    print(f"  DateTime: {transformer.format_datetime(datetime(2024, 1, 15, 14, 30))}")
    
    print("\nGender Normalization:")
    print(f"  'Male' -> {transformer.normalize_gender('Male')}")
    print(f"  'F' -> {transformer.normalize_gender('F')}")
    
    print("\nReferences:")
    print(f"  Patient: {transformer.patient_reference(123)}")
    print(f"  Encounter: {transformer.encounter_reference(456)}")
    
    print("\nEncounter Class Mapping:")
    print(f"  'inpatient' -> {transformer.map_encounter_class('inpatient')}")
    print(f"  'emergency' -> {transformer.map_encounter_class('emergency')}")
    
    print("\nDosage Extraction:")
    print(f"  '10mg' -> {transformer.extract_dosage_value('10mg')}")
    print(f"  '250mg' -> {transformer.extract_dosage_value('250mg')}")
    
    print("\n[OK] Data transformation tests complete")
