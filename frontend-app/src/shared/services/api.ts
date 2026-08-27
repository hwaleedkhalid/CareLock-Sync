/**
 * Shared API Service
 * Thin domain wrappers around the centralised apiClient singleton.
 *
 * All HTTP transport (auth headers, retry, error normalisation, health
 * monitoring) is handled by apiClient.ts.  This file only maps domain
 * operations to typed endpoint calls — it contains NO axios instance and
 * NO duplicate auth logic.
 *
 * Auth flow (unchanged):
 *   1. POST /api/v1/auth/login  →  { access_token, ... }
 *   2. AuthContext stores the full AuthUser in localStorage ('carelock_auth')
 *      and calls apiClient.setToken(access_token).
 *   3. Every request in apiClient automatically attaches:
 *        Authorization: Bearer <access_token>
 *   4. 401 response → apiClient emits 'auth-expired' → AuthContext logs out
 *      → ProtectedRoute redirects to /auth/login.
 */
import { apiClient } from './apiClient';

// ── Auth ───────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string, role?: string) =>
    apiClient.post('/api/v1/auth/login', { email, password, role }),

  logout: () =>
    apiClient.post('/api/v1/auth/logout'),

  demoAccounts: () =>
    apiClient.get('/api/v1/auth/demo-accounts'),
};

// ── Dashboard ─────────────────────────────────────────────────────────────
export const dashboardApi = {
  getStats:         () => apiClient.get('/api/v1/stats'),
  getSystemMetrics: () => apiClient.get('/api/v1/system/metrics'),
  getDataQuality:   () => apiClient.get('/api/v1/metrics'),
};

// ── Patients ──────────────────────────────────────────────────────────────
export const patientsApi = {
  list:     (page = 1, limit = 20) =>
              apiClient.get(`/api/v1/patients?page=${page}&limit=${limit}`),
  get:      (id: number) => apiClient.get(`/api/v1/patients/${id}`),
  fhirList: (skip = 0, limit = 50) =>
              apiClient.get(`/api/v1/patients/fhir/?skip=${skip}&limit=${limit}`),
  fhirGet:  (id: number) => apiClient.get(`/api/v1/patients/fhir/${id}`),
};

// ── Encounters ────────────────────────────────────────────────────────────
export const encountersApi = {
  list: (patientId?: number) => {
    const url = patientId
      ? `/api/v1/encounters?patient_id=${patientId}`
      : '/api/v1/encounters';
    return apiClient.get(url);
  },
};

// ── Observations ──────────────────────────────────────────────────────────
export const observationsApi = {
  list: (patientId?: number) => {
    const url = patientId
      ? `/api/v1/observations?patient_id=${patientId}`
      : '/api/v1/observations';
    return apiClient.get(url);
  },
};

// ── Medications ───────────────────────────────────────────────────────────
export const medicationsApi = {
  list: (patientId?: number) => {
    const url = patientId
      ? `/api/v1/medications?patient_id=${patientId}`
      : '/api/v1/medications';
    return apiClient.get(url);
  },
};

// ── Sync ──────────────────────────────────────────────────────────────────
export const syncApi = {
  status:             (params?: { sync_id?: string }) =>
                        apiClient.get('/api/v1/sync/status', { params }),
  history:            (limit = 10) =>
                        apiClient.get(`/api/v1/sync/history?limit=${limit}`),
  statistics:         () => apiClient.get('/api/v1/sync/statistics'),
  trigger:            () => apiClient.post('/api/v1/sync/trigger'),
  triggerFull:        (tenant_id = 1) =>
                        apiClient.post('/api/v1/sync/full', { tenant_id }),
  triggerIncremental: (tenant_id = 1) =>
                        apiClient.post('/api/v1/sync/incremental', { tenant_id }),
};

// ── RAG / AI Mapping ──────────────────────────────────────────────────────
export const ragApi = {
  status:         () => apiClient.get('/api/v1/rag/status'),
  knowledgeStats: () => apiClient.get('/api/v1/rag/knowledge/stats'),
  chat:           (question: string, context?: string) =>
                    apiClient.post('/api/v1/rag/chat', { question, context }),
  suggestSchema:  (tableName: string, columns: { name: string; type: string }[], fhirResource = 'Patient') =>
                    apiClient.post('/api/v1/rag/suggest/schema', {
                      table_name: tableName, columns, fhir_resource: fhirResource,
                    }),
  suggestField:   (fieldName: string, fieldType: string, fhirResource = 'Patient') =>
                    apiClient.post('/api/v1/rag/suggest/field', {
                      field_name: fieldName, field_type: fieldType, fhir_resource: fhirResource,
                    }),
  confirmBatch:   (mappings: unknown[], confirmedFields: string[]) =>
                    apiClient.post('/api/v1/rag/mappings/confirm-batch', {
                      mappings, confirmed_fields: confirmedFields,
                    }),
};

// ── Status / health ───────────────────────────────────────────────────────
export const statusApi = {
  health:     () => apiClient.get('/health'),
  hospitalDb: () => apiClient.get('/api/v1/status/database/hospital'),
  sharedDb:   () => apiClient.get('/api/v1/status/database/shared'),
  system:     () => apiClient.get('/api/v1/status/system'),
};

// ── Tenant ────────────────────────────────────────────────────────────────
export const tenantApi = {
  info:   () => apiClient.get('/api/v1/tenant/info'),
  stats:  () => apiClient.get('/api/v1/tenant/stats'),
  list:   () => apiClient.get('/api/v1/tenants'),
  create: (payload: {
    hospital_name: string;
    hospital_code: string;
    city?: string;
    db_type: string;
    db_host: string;
    db_port: number;
    db_name: string;
    db_user: string;
    db_password: string;
  }) => apiClient.post('/api/v1/tenants', payload),
};

// ── Connector / Schema ────────────────────────────────────────────────────
export const connectorApi = {
  schema: () => apiClient.get('/api/v1/connector/schema'),
  health: () => apiClient.get('/api/v1/connector/health'),
};

// ── System events ─────────────────────────────────────────────────────────
export const systemApi = {
  events: (limit = 100) =>
    apiClient.get(`/api/v1/system/events?limit=${limit}`),
};

// Re-export the singleton as the default so any file that
// does `import api from './api'` still compiles.
export default apiClient;
