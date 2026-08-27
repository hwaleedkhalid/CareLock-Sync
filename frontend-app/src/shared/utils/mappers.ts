/**
 * shared/utils/mappers.ts
 * Data transformation and mapping utilities
 */

import type { TenantInfo } from '../types';
import { formatTime, formatDate } from './formatters';

/**
 * Tenant UI type (matches TenantManagementPage.Tenant)
 */
export interface TenantUI {
  id: number;
  name: string;
  code: string;
  city: string;
  dbType: string;
  status: 'active' | 'pending' | 'error' | 'syncing';
  patients: number;
  syncRate: number;
  lastSync: string;
  onboardedAt: string;
  rlsEnabled: boolean;
  cdcActive: boolean;
}

/**
 * Map API TenantInfo response to TenantUI for display
 * @param tenantInfo Raw API response
 * @returns Transformed tenant object safe for UI binding
 */
export function mapTenant(tenantInfo: TenantInfo): TenantUI {
  // `patients` is the field name returned by GET /api/v1/tenants.
  // Fall back to the deprecated `patient_count` alias for safety.
  const patientCount = tenantInfo.patients ?? tenantInfo.patient_count ?? 0;

  // Use nullish coalescing (??) so a real 0% sync rate is not replaced with 99.5.
  // A null/undefined value means "no sync data yet" and is surfaced as 0 in the UI.
  const syncRate = tenantInfo.sync_rate ?? null;

  return {
    id: tenantInfo.id,
    name: tenantInfo.name || 'Hospital',
    code: tenantInfo.code || `TEN${tenantInfo.id}`,
    city: tenantInfo.city || 'N/A',
    dbType: tenantInfo.db_type || 'PostgreSQL',
    status: (tenantInfo.is_active ? 'active' : 'pending') as TenantUI['status'],
    patients: patientCount,
    syncRate: syncRate !== null ? Math.round(syncRate * 100 * 10) / 10 : 0,
    lastSync: formatTime(tenantInfo.last_sync),
    onboardedAt: formatDate(tenantInfo.created_at),
    rlsEnabled: tenantInfo.rls_enabled ?? true,
    cdcActive: tenantInfo.cdc_enabled ?? true,
  };
}

/**
 * Map array of TenantInfo to TenantUI[]
 */
export function mapTenants(tenantInfoList: TenantInfo[]): TenantUI[] {
  return tenantInfoList.map(mapTenant);
}
