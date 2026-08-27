/**
 * shared/constants/routes.ts
 * Centralized route definitions — single source of truth
 * Prevents routing mismatches and hardcoding scattered paths
 */

export const PUBLIC_ROUTES = {
  HOME: '/',
  ONBOARDING: '/onboarding',
  ROLE_SELECTOR: '/auth/role',
  LOGIN: '/auth/login',
} as const;

export const ADMIN_ROUTES = {
  HOME: '/admin',
  SYSTEM_HEALTH: '/admin/system-health',
  SYNC_ANALYTICS: '/admin/sync-analytics',
  TENANTS: '/admin/tenants',
  MAPPING: '/admin/mapping',
  SECURITY: '/admin/security',
  BENCHMARK: '/admin/benchmark',
} as const;

export const HOSPITAL_ROUTES = {
  HOME: '/hospital',
  DASHBOARD: '/hospital/dashboard',
  DATA_SOURCES: '/hospital/data-sources',
  SYNC_REPORT: '/hospital/sync-report',
  MAPPING: '/hospital/mapping',
  PATIENTS: '/hospital/patients',
  ENCOUNTERS: '/hospital/encounters',
  MONITORING: '/hospital/monitoring',
} as const;

export const DOCTOR_ROUTES = {
  HOME: '/doctor',
  DASHBOARD: '/doctor/dashboard',
  PATIENTS: '/doctor/patients',
  ENCOUNTERS: '/doctor/encounters',
  CHAT: '/doctor/chat',
} as const;

export const ANALYST_ROUTES = {
  HOME: '/analyst',
  DASHBOARD: '/analyst/dashboard',
  DATA_QUALITY: '/analyst/data-quality',
  RESEARCH: '/analyst/research',
  CHAT: '/analyst/chat',
} as const;

/**
 * Role-based dashboard redirect routes
 * Used after successful login to navigate user to their dashboard
 */
export const ROLE_DASHBOARD_ROUTES = {
  admin: ADMIN_ROUTES.SYSTEM_HEALTH,
  hospital: HOSPITAL_ROUTES.DASHBOARD,
  doctor: DOCTOR_ROUTES.DASHBOARD,
  analyst: ANALYST_ROUTES.DASHBOARD,
} as const;

/**
 * Navigation constants for public site buttons
 */
export const NAV_BUTTONS = {
  // "Start Demo" / "Get Started" button → hospital onboarding wizard
  DEMO_START: PUBLIC_ROUTES.ONBOARDING,
  // "Sign In" button → login (requires role pre-selection OR allows direct login)
  LOGIN: PUBLIC_ROUTES.LOGIN,
} as const;
