"""
Google Gemini API Client
"""
import os
from typing import List, Dict, Any, Optional
import json
import re


class GeminiClient:
    """Wrapper for Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            import google.generativeai as genai
            self.genai = genai
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")
        
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required")
        
        self.genai.configure(api_key=self.api_key)
        # Use Gemini 2.5 Flash (free tier, latest available)
        self.model = self.genai.GenerativeModel('gemini-2.5-flash')
    
    def generate_mapping_suggestion(
        self,
        source_field: Dict[str, Any],
        similar_mappings: List[Dict],
        fhir_resource: str = "Patient"
    ) -> Dict[str, Any]:
        prompt = self._build_mapping_prompt(source_field, similar_mappings, fhir_resource)
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_mapping_response(response.text)
        except Exception as e:
            return {
                'target_path': 'unknown',
                'confidence': 0.0,
                'reasoning': f'Error: {str(e)}',
                'transformation': 'none'
            }
    
    def _build_mapping_prompt(self, source_field: Dict, similar_mappings: List[Dict], fhir_resource: str) -> str:
        field_name = source_field.get('name', 'unknown')
        field_type = source_field.get('type', 'unknown')
        sample_values = source_field.get('sample_values', [])
        
        prompt = f"""You are a healthcare data expert. Suggest FHIR R4 mapping.

Source Field: {field_name} ({field_type})
Sample Values: {sample_values if sample_values else 'N/A'}
Target Resource: {fhir_resource}

Similar mappings:
"""
        for i, mapping in enumerate(similar_mappings[:3], 1):
            prompt += f"{i}. {mapping.get('source_field')} -> {mapping.get('target_path')}\n"
        
        if not similar_mappings:
            prompt += "None\n"
        
        fhir_fields = self._get_common_fhir_fields(fhir_resource)
        prompt += f"\nCommon {fhir_resource} fields:\n"
        prompt += "\n".join(f"- {field}" for field in fhir_fields[:8])
        
        prompt += """\n\nProvide JSON response only:
{
  "target_path": "Patient.birthDate",
  "confidence": 0.95,
  "reasoning": "Brief explanation",
  "transformation": "format_date or none"
}"""
        return prompt
    
    def _get_common_fhir_fields(self, resource_type: str) -> List[str]:
        fhir_fields = {
            'Patient': [
                'id', 'identifier[].value', 'name[].family', 'name[].given[]',
                'birthDate', 'gender', 'address[].line[]', 'telecom[].value'
            ],
            'Encounter': [
                'id', 'status', 'class.code', 'subject.reference',
                'period.start', 'period.end'
            ]
        }
        return fhir_fields.get(resource_type, ['id'])
    
    def _parse_mapping_response(self, response_text: str) -> Dict:
        try:
            cleaned = response_text.strip()
            cleaned = re.sub(r'```json\s*', '', cleaned)
            cleaned = re.sub(r'```\s*$', '', cleaned)
            
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
            
            if json_match:
                parsed = json.loads(json_match.group())
                required = ['target_path', 'confidence', 'reasoning', 'transformation']
                for field in required:
                    if field not in parsed:
                        parsed[field] = 'unknown' if field != 'confidence' else 0.0
                parsed['confidence'] = max(0.0, min(1.0, float(parsed['confidence'])))
                return parsed
        except Exception:
            pass
        
        return {
            'target_path': 'unknown',
            'confidence': 0.0,
            'reasoning': 'Failed to parse',
            'transformation': 'none'
        }
