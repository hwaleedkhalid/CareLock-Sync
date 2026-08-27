// ── Shared Types — used across all modules ────────────────────────────────
export type UserRole = 'admin' | 'hospital' | 'doctor' | 'analyst';

export interface AuthUser {
  email:         string;
  display_name:  string;
  role:          UserRole;
  access_token:  string;   // HS256 JWT — stored in localStorage, sent as Bearer
  tenant_id:     number | null;
  hospital_name: string;
  logged_in_at:  string;
}

// FHIR Patient from central DB
export interface FHIRPatient {
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

// Hospital DB Patient
export interface Patient {
  patient_id: number;
  medical_record_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender?: string;
  blood_type?: string;
  phone_number?: string;
  email?: string;
  created_at?: string;
}

export interface Encounter {
  id?: number;
  encounter_id: string;
  patient_id: number;
  tenant_id?: number;
  encounter_type: string;
  start_date?: string;
  end_date?: string;
  status: string;
}

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

export interface SyncStatus {
  is_syncing: boolean;
  last_sync_time: string | null;
  last_sync_stats: Record<string, number> | null;
  total_syncs: number;
  // Extended fields used by SyncStatusPanel and AdminActions
  status?: 'idle' | 'running' | 'completed' | 'failed';
  progress?: number;
  current_step?: string;
  mode?: 'full' | 'incremental';
  sync_id?: string;
  duration_s?: number;
  records_processed?: number;
  error?: string;
  is_stale?: boolean;
  last_heartbeat_at?: string;
  stale_threshold_seconds?: number;
}

export interface MappingSuggestion {
  source_field: string;
  source_type: string;
  target_path: string;
  fhir_resource: string;
  confidence: number;
  transformation: string;
  status?: 'pending' | 'approved' | 'rejected';
  reasoning?: string;
  model?: string;
  ms?: number;
}

export interface TenantInfo {
  id: number;
  name: string;
  code: string;
  city?: string;
  db_type?: string;
  is_active: boolean;
  /**
   * `patients` matches the field name returned by GET /api/v1/tenants.
   * The old name `patient_count` is kept as an optional alias so any
   * existing code that referenced it still compiles without error.
   */
  patients?: number;
  /** @deprecated Use `patients` — kept for backwards compatibility only */
  patient_count?: number;
  sync_rate?: number;
  last_sync?: string;
  created_at?: string;
  rls_enabled?: boolean;
  cdc_enabled?: boolean;
}

export interface SystemMetrics {
  api_requests: number;
  avg_latency: number;
  error_rate: number;
  cdc_operations: number;
  etl_syncs: number;
  // Extended fields used by SystemHealthPanel
  throughput_per_min?: number;
  ingestion_lag_seconds?: number;
  queue_depth: number;       // required — component calls .toLocaleString() unconditionally
  dead_letter_count: number; // required — component uses in template string unconditionally
  available?: boolean;       // false when CDC pipeline schema not yet applied
}

export interface CDCAgentStatus {
  running: boolean;
  tenant_id: number;
  poll_interval: number;
  changes_sent: number;
  errors: number;
  cycles: number;
  last_push_at: string | null;
  watermarks: Record<string, number>;
}

// ── Healthcare Data Pipeline + CDC ──────────────────────────────────────────

// CDC + ETL Adapter (represents a hospital data source)
export interface CDCAdapter {
  id: string;
  name: string;
  database_type: 'postgresql' | 'mysql' | 'mongodb' | 'sqlserver' | 'oracle';
  status: 'connected' | 'disconnected' | 'error' | 'syncing';
  latency_ms: number | null;
  cdc_enabled: boolean;
  cdc_trigger_status: 'active' | 'inactive' | 'failed';
  last_captured_change_id?: string;
  last_captured_timestamp?: string;
  cdc_lag_seconds: number | null;
  error?: string;
}

// CDC + Connector Health (ETL pipeline metrics)
export interface ConnectorHealth {
  adapters: CDCAdapter[];
  cdc_capture_rate: number | null;  // % of changes captured (null if no data)
  cdc_expected: number;      // % expected (SLA)
  cdc_lag_max_seconds: number | null;  // Maximum lag across all adapters (null if no data)
  throughput_records_sec: number | null;  // Records processed/sec (null if no data)
  etl_processing_time_ms: number | null;  // Avg ETL transform time (null if no data)
  workers_ready: number;     // Active CDC workers
  workers_total: number;     // Total workers available
  failed_adapters: number;
  failed_syncs_24h: number | null;
  timestamp: string;
}

// Database Status (represents a data source connection)
export interface DatabaseStatus {
  engine: 'postgresql' | 'mysql' | 'mongodb' | 'sqlserver' | 'oracle';
  status: 'connected' | 'disconnected' | 'error';
  latency_ms: number | null;
  pool_size?: number | null;
  active_connections?: number | null;
  pool_available?: number | null;
  uptime_seconds?: number | null;
  last_interaction?: string | null;
  error?: string | null;
}

// System Health (infrastructure metrics)
export interface SystemStatus {
  uptime_seconds: number | null;
  active_services: number;  // CDC workers, ETL tasks, API servers
  failed_services: number;  // Failed or unhealthy services
  avg_latency_ms: number | null;
  cdc_pipeline_healthy: boolean;
  etl_pipeline_healthy: boolean;
  data_quality_score: number | null;  // % of valid records (null if insufficient data)
}

// Pipeline Error/Failure (for error visibility)
export interface PipelineError {
  id: string;
  source_adapter_id: string;
  error_type: 'cdc_failed' | 'etl_failed' | 'network_timeout' | 'validation_error';
  message: string;
  timestamp: string;
  recovery_status: 'pending' | 'retrying' | 'resolved' | 'failed';
}
