/**
 * context/AuthContext.tsx
 * Legacy compatibility shim — delegates to the shared AuthContext.
 * Existing pages that import from '../context/AuthContext' continue to work
 * without modification. New code should import from '../shared/context/AuthContext'.
 */
export { AuthProvider, useAuth } from '../shared/context/AuthContext';
export type { } from '../shared/context/AuthContext';
