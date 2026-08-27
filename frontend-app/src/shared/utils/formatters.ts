/**
 * shared/utils/formatters.ts
 * Date and time formatting utilities
 */

/**
 * Format ISO timestamp to localized time string
 * @param isoTimestamp ISO 8601 timestamp or null
 * @returns Formatted time string or 'Never' if timestamp is null
 */
export function formatTime(isoTimestamp: string | null | undefined): string {
  if (!isoTimestamp) return 'Never';
  try {
    return new Date(isoTimestamp).toLocaleTimeString();
  } catch {
    return 'Never';
  }
}

/**
 * Format ISO timestamp to localized date string
 * @param isoTimestamp ISO 8601 timestamp or null
 * @returns Formatted date string or 'Unknown' if timestamp is null
 */
export function formatDate(isoTimestamp: string | null | undefined): string {
  if (!isoTimestamp) return 'Unknown';
  try {
    return new Date(isoTimestamp).toLocaleDateString();
  } catch {
    return 'Unknown';
  }
}
