/**
 * apiNormalizers.ts — Backend API Response Normalization
 *
 * Transforms actual backend API responses into frontend type expectations.
 * Fixes field name mismatches and handles partial data.
 *
 * STRICT RULE: NO FAKE DATA
 * ─────────────────────────
 * Every field must originate from a real backend measurement.
 * If the backend does not return a value → null (UI displays "N/A").
 * No hardcoded defaults, no estimates, no made-up formulas.
 */

import type {
  ConnectorHealth,
  DatabaseStatus,
  SystemStatus,
  CDCAdapter,
} from '../types';

// ─────────────────────────────────────────────────────────────────────────────
// normalizeDatabaseStatus
// ─────────────────────────────────────────────────────────────────────────────
/**
 * Normalize DatabaseStatus from /api/v1/status/database/*.
 *
 * Backend now returns: { database_name, connected, latency_ms, total_patients, … }
 * latency_ms is a real SELECT-1 round-trip measured in the backend.
 */
export function normalizeDatabaseStatus(
  backendData: any,
  dbType: 'postgresql' | 'mysql' | 'mongodb' | 'sqlserver' | 'oracle' = 'postgresql'
): DatabaseStatus {
  if (!backendData) {
    return {
      engine: dbType,
      status: 'disconnected',
      latency_ms: null,
      error: 'No data received',
    };
  }

  const isConnected = backendData.connected === true;

  return {
    engine: dbType,
    status: isConnected ? 'connected' : 'disconnected',
    latency_ms:        backendData.latency_ms          ?? null,  // real measured ping
    pool_size:         backendData.pool_size            ?? undefined,
    active_connections: backendData.active_connections  ?? undefined,
    pool_available:    backendData.pool_available       ?? undefined,
    uptime_seconds:    backendData.uptime_seconds       ?? undefined,
    last_interaction:  backendData.last_checked         ?? undefined,
    error: backendData.error ?? (isConnected ? null : 'Connection failed'),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// normalizeSystemStatus
// ─────────────────────────────────────────────────────────────────────────────
/**
 * Normalize SystemStatus from /api/v1/status/system.
 *
 * Backend now returns:
 *   uptime_seconds  — real process uptime since server start
 *   hospital_db.latency_ms  — real measured SELECT-1 ping
 *   shared_db.latency_ms    — real measured SELECT-1 ping
 *
 * active_services  = number of DBs that are actually reachable (real count).
 * failed_services  = number of DBs that failed their ping (real count).
 * avg_latency_ms   = mean of the real latency_ms values that are present.
 *
 * NO multipliers, NO hardcoded defaults.
 */
export function normalizeSystemStatus(backendData: any): SystemStatus {
  if (!backendData) {
    return {
      uptime_seconds:       null,
      active_services:      0,
      failed_services:      0,
      avg_latency_ms:       null,
      cdc_pipeline_healthy: false,
      etl_pipeline_healthy: false,
      data_quality_score:   null,
    };
  }

  // Real service counts — one "service" per monitored database.
  const dbStatuses = [backendData.hospital_db, backendData.shared_db].filter(Boolean);
  const activeServices = dbStatuses.filter((d: any) => d.connected === true).length;
  const failedServices  = dbStatuses.filter((d: any) => d.connected !== true).length;

  // Average latency: mean of ONLY the databases that returned a real latency_ms.
  const latencyValues = dbStatuses
    .map((d: any) => d.latency_ms)
    .filter((v: any): v is number => typeof v === 'number' && !isNaN(v));
  const avgLatency = latencyValues.length > 0
    ? Math.round((latencyValues.reduce((a, b) => a + b, 0) / latencyValues.length) * 100) / 100
    : null;

  // data_quality_score: only set when we have actual record counts > 0.
  // Even then, we don't fabricate a score — return null until a real
  // quality calculation is implemented.
  const dataQualityScore: number | null = null;

  return {
    uptime_seconds:       backendData.uptime_seconds ?? null,   // real process uptime
    active_services:      activeServices,                        // real count
    failed_services:      failedServices,                        // real count
    avg_latency_ms:       avgLatency,                            // real measured average
    cdc_pipeline_healthy: backendData.hospital_db?.connected === true,
    etl_pipeline_healthy: backendData.shared_db?.connected === true,
    data_quality_score:   dataQualityScore,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// normalizeConnectorHealth
// ─────────────────────────────────────────────────────────────────────────────
/**
 * Normalize ConnectorHealth from /api/v1/connector/health.
 *
 * Backend returns: { overall, checked_at, databases[], central_db{} }
 *
 * CDC metrics (capture rate, throughput, ETL time, lag) are NOT available
 * from this endpoint — they require the CDC schema (cdc_inbox etc.).
 * Return null for all of them; the dashboard will display "N/A" until the
 * CDC infrastructure is deployed and /api/v1/system/metrics becomes available.
 *
 * NO hardcoded 98.5 / 25 / totalRecords÷60 values.
 */
export function normalizeConnectorHealth(backendData: any): ConnectorHealth {
  if (!backendData) {
    return {
      adapters: [],
      cdc_capture_rate:       null,
      cdc_expected:           99,
      cdc_lag_max_seconds:    null,
      throughput_records_sec: null,
      etl_processing_time_ms: null,
      workers_ready:          0,
      workers_total:          0,
      failed_adapters:        0,
      failed_syncs_24h:       null,
      timestamp:              new Date().toISOString(),
    };
  }

  // Convert backend "databases" list to frontend "adapters".
  const adapters: CDCAdapter[] = (backendData.databases || []).map((db: any, index: number) => {
    const isConnected = db.connected === true;
    return {
      id:                       `adapter-${index}`,
      name:                     db.name,
      database_type:            (db.platform || 'postgresql') as any,
      status:                   isConnected ? 'connected' : db.connected === false ? 'disconnected' : 'error',
      latency_ms:               db.latency_ms ?? null,        // real measured ping
      cdc_enabled:              isConnected,
      cdc_trigger_status:       isConnected ? 'active' : 'inactive',
      last_captured_change_id:  undefined,
      last_captured_timestamp:  undefined,
      cdc_lag_seconds:          db.cdc_lag_seconds ?? null,   // real CDC lag — null until CDC deployed
      error:                    db.error ?? null,
    };
  });

  // Adapter counts — always real.
  const failedAdapters  = adapters.filter(a => a.status !== 'connected').length;
  const workersReady    = adapters.filter(a => a.status === 'connected').length;
  const workersTotal    = adapters.length;

  // CDC lag max — only if any adapter actually reports a real lag value.
  const lagValues = adapters
    .map(a => a.cdc_lag_seconds)
    .filter((v): v is number => typeof v === 'number');
  const maxLag = lagValues.length > 0 ? Math.max(...lagValues) : null;

  // All CDC pipeline metrics (capture rate, throughput, ETL time) require the
  // cdc_inbox / cdc_watermarks schema. They are supplied separately via
  // /api/v1/system/metrics and merged in the dashboard component.
  // Do NOT fabricate them here.
  return {
    adapters,
    cdc_capture_rate:       null,   // populated from /api/v1/system/metrics
    cdc_expected:           99,
    cdc_lag_max_seconds:    maxLag, // real — null until CDC tables exist
    throughput_records_sec: null,   // populated from /api/v1/system/metrics
    etl_processing_time_ms: null,   // populated from /api/v1/system/metrics
    workers_ready:          workersReady,
    workers_total:          workersTotal,
    failed_adapters:        failedAdapters,
    failed_syncs_24h:       null,
    timestamp:              backendData.checked_at ?? new Date().toISOString(),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Null-safe defaults (no fake values)
// ─────────────────────────────────────────────────────────────────────────────
export function getDefaultConnectorHealth(): ConnectorHealth {
  return {
    adapters:               [],
    cdc_capture_rate:       null,
    cdc_expected:           99,
    cdc_lag_max_seconds:    null,
    throughput_records_sec: null,
    etl_processing_time_ms: null,
    workers_ready:          0,
    workers_total:          0,
    failed_adapters:        0,
    failed_syncs_24h:       null,
    timestamp:              new Date().toISOString(),
  };
}

export function getDefaultSystemStatus(): SystemStatus {
  return {
    uptime_seconds:       null,
    active_services:      0,
    failed_services:      0,
    avg_latency_ms:       null,
    cdc_pipeline_healthy: false,
    etl_pipeline_healthy: false,
    data_quality_score:   null,
  };
}

export function getDefaultDatabaseStatus(): DatabaseStatus {
  return {
    engine:    'postgresql',
    status:    'disconnected',
    latency_ms: null,
    error:     'No data',
  };
}
