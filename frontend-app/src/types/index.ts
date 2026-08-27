// User and Authentication Types
export interface User {
  user_id: number;
  username: string;
  email: string;
  hospital_id: number;
  hospital_name?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface DecodedToken {
  user_id: number;
  username: string;
  hospital_id: number;
  email: string;
  exp: number;
}

// FHIR Resource Types
export interface Patient {
  id: number;
  tenant_id: number;
  source_patient_id: string;
  family_name: string;
  given_name?: string;
  birth_date?: string;
  gender?: string;
  active: boolean;
  created_at?: string;
}

export interface Encounter {
  id: number;
  tenant_id: number;
  patient_id: number;
  encounter_id: string;
  encounter_type?: string;
  start_date?: string;
  end_date?: string;
  status: string;
}

export interface Observation {
  id: number;
  tenant_id: number;
  patient_id: number;
  observation_code?: string;
  value_quantity?: number;
  value_string?: string;
  recorded_date?: string;
}

export interface MedicationRequest {
  id: number;
  tenant_id: number;
  patient_id: number;
  medication_name?: string;
  dosage?: string;
  status: string;
}

// Statistics and Metrics
export interface DashboardStats {
  total_patients: number;
  total_encounters: number;
  total_observations: number;
  total_medications: number;
  recent_sync?: string;
}

export interface DataQualityMetrics {
  completeness_score: number;
  sync_success_rate: number;
  mapping_accuracy: number;
  error_rate: number;
}

// RAG Mapping Types
export interface MappingSuggestion {
  source_field: string;
  target_path: string;
  confidence: number;
  explanation?: string;
}

export interface TenantInfo {
  hospital_id: number;
  hospital_name: string;
  hospital_code: string;
  is_active: boolean;
  created_at?: string;
}

export interface SystemMetrics {
  api_requests: number;
  avg_latency: number;
  error_rate: number;
  cdc_operations: number;
  etl_syncs: number;
}
