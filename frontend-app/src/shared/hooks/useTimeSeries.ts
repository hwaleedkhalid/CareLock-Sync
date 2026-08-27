/**
 * shared/hooks/useTimeSeries.ts
 * Hook for accumulating real API data into time-series for charting
 *
 * Usage:
 *   const timeSeries = useTimeSeries(apiData, (data) => data.avg_latency_ms, 50);
 *   // Returns: { timestamp: '14:30:45', value: 245 } for each new API response
 */

import { useState, useEffect } from 'react';

export interface TimeSeriesPoint {
  timestamp: string;  // HH:MM:SS format
  value: number;
}

export interface UseTimeSeriesOptions {
  maxPoints?: number;  // Maximum data points to keep (rolling window)
  enabled?: boolean;   // Enable/disable accumulation
}

/**
 * Accumulate real API data into time-series for charting
 *
 * @param apiData - Current API response data
 * @param extractor - Function to extract numeric value from API data (e.g., data => data.avg_latency_ms)
 * @param maxPoints - Maximum number of historical points to keep (default 50)
 * @returns Array of time-series points with timestamp and value
 *
 * @example
 *   const latencySeries = useTimeSeries(systemData.data, d => d.avg_latency_ms, 30);
 *   // Automatically appends new latency values as systemData updates
 */
export function useTimeSeries<T>(
  apiData: T | null,
  extractor: (data: T) => number | null | undefined,
  maxPoints: number = 50
): TimeSeriesPoint[] {
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);

  // Append new data point whenever apiData changes
  useEffect(() => {
    if (!apiData) return;

    const value = extractor(apiData);
    if (value === null || value === undefined || !isFinite(value)) {
      // Skip invalid values (don't add to series)
      return;
    }

    // Create new point with current timestamp
    const now = new Date();
    const timestamp = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    setSeries((prevSeries) => {
      // Add new point
      const newSeries = [
        ...prevSeries,
        { timestamp, value: Math.round(value * 100) / 100 }, // Round to 2 decimals
      ];

      // Keep only last N points (rolling window)
      return newSeries.slice(Math.max(0, newSeries.length - maxPoints));
    });
  }, [apiData, extractor, maxPoints]);

  return series;
}

export default useTimeSeries;
