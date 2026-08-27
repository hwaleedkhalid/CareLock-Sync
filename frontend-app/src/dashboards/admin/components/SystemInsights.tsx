/**
 * SystemInsights.tsx — Intelligent Observability Analysis
 *
 * Analyzes REAL-TIME metrics from CDC, ETL, and adapters
 * Detects anomalies using actual trends, NOT simulated conditions
 *
 * CRITICAL RULE: ALL insights derived from real API data
 */

import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';
import type { TimeSeriesPoint } from '../../../shared/hooks';
import type { CDCAdapter } from '../../../shared/types';

export type InsightSeverity = 'success' | 'info' | 'warning' | 'critical';

export interface Insight {
  id: string;
  severity: InsightSeverity;
  title: string;
  description: string;
  metric?: string;
  actions: InsightAction[];
}

export interface InsightAction {
  label: string;
  onClick: () => void | Promise<void>;
  loading?: boolean;
}

interface SystemInsightsProps {
  latencySeries: TimeSeriesPoint[];
  throughputSeries: TimeSeriesPoint[];
  cdcLagSeries: TimeSeriesPoint[];
  cdcCaptureSeries: TimeSeriesPoint[];
  etlTimeSeries: TimeSeriesPoint[];
  adapters: CDCAdapter[];
  onRefetch?: () => Promise<void>;
}

// ── Helper Functions ──────────────────────────────────────────────────────────

/**
 * Calculate average of last N points
 */
function getAverage(series: TimeSeriesPoint[], count: number = 5): number {
  if (series.length < count) {
    if (series.length === 0) return 0;
    return series.reduce((sum, p) => sum + p.value, 0) / series.length;
  }
  const recent = series.slice(-count);
  return recent.reduce((sum, p) => sum + p.value, 0) / recent.length;
}

/**
 * Detect trend: is metric increasing/decreasing/stable?
 */
function detectTrend(series: TimeSeriesPoint[]): {
  direction: 'increasing' | 'decreasing' | 'stable';
  percentChange: number;
} {
  if (series.length < 2) return { direction: 'stable', percentChange: 0 };

  const latest = series[series.length - 1];
  const previous = series[series.length - 2];

  if (previous.value === 0) {
    return { direction: 'stable', percentChange: 0 };
  }

  const percentChange = ((latest.value - previous.value) / previous.value) * 100;

  return {
    direction: Math.abs(percentChange) < 10 ? 'stable' : percentChange > 0 ? 'increasing' : 'decreasing',
    percentChange,
  };
}

// ── Analysis Functions ────────────────────────────────────────────────────────

/**
 * Analyze CDC lag: detect increasing delays or critical thresholds
 */
function analyzeCdcLag(cdcLagSeries: TimeSeriesPoint[]): Insight[] {
  const insights: Insight[] = [];

  if (cdcLagSeries.length < 2) return insights;

  const latest = cdcLagSeries[cdcLagSeries.length - 1];
  const avgRecent = getAverage(cdcLagSeries, 5);
  const trend = detectTrend(cdcLagSeries);

  // Critical: Lag above 30 seconds
  if (latest.value > 30) {
    insights.push({
      id: 'cdc-lag-critical',
      severity: 'critical',
      title: '🔴 Critical CDC Ingestion Lag',
      description: `CDC lag is ${latest.value.toFixed(1)}s — data synchronization severely delayed. Hospital changes are not being captured in real-time.`,
      metric: `${latest.value.toFixed(1)}s lag`,
      actions: [
        {
          label: 'Inspect CDC Watermarks',
          onClick: () => console.log('View CDC watermark details'),
        },
        {
          label: 'Restart Adapters',
          onClick: () => {},
        },
      ],
    });
  }
  // Warning: Lag increasing or above 10s
  else if (trend.direction === 'increasing' && latest.value > avgRecent * 1.3) {
    insights.push({
      id: 'cdc-lag-increasing',
      severity: 'warning',
      title: '⚠️ CDC Lag Increasing',
      description: `CDC lag is trending upward (+${trend.percentChange.toFixed(0)}%) — currently ${latest.value.toFixed(1)}s. Possible queue backlog or adapter slowdown.`,
      metric: `+${trend.percentChange.toFixed(0)}% trend`,
      actions: [
        {
          label: 'Check CDC Queue',
          onClick: () => console.log('View CDC queue metrics'),
        },
      ],
    });
  } else if (latest.value > 10) {
    insights.push({
      id: 'cdc-lag-elevated',
      severity: 'warning',
      title: '⚠️ Elevated CDC Lag',
      description: `CDC lag is ${latest.value.toFixed(1)}s — above ideal threshold of <5s. Investigate adapter performance.`,
      metric: `${latest.value.toFixed(1)}s lag`,
      actions: [
        {
          label: 'View Adapter Metrics',
          onClick: () => console.log('View adapter details'),
        },
      ],
    });
  }

  return insights;
}

/**
 * Analyze adapter health: detect failures and connection issues
 */
function analyzeAdapters(adapters: CDCAdapter[]): Insight[] {
  const insights: Insight[] = [];

  const failed = adapters.filter(a => a.status === 'error');
  const disconnected = adapters.filter(a => a.status === 'disconnected');

  // Critical: Any adapter errors
  failed.forEach(adapter => {
    insights.push({
      id: `adapter-error-${adapter.id}`,
      severity: 'critical',
      title: `❌ Adapter Error: ${adapter.name}`,
      description: `${adapter.database_type.toUpperCase()} adapter is in error state${
        adapter.error ? `: ${adapter.error}` : ''
      }. Hospital data source is unreachable.`,
      metric: adapter.database_type,
      actions: [
        {
          label: 'Reconnect',
          onClick: () => console.log(`Reconnect adapter ${adapter.id}`),
        },
        {
          label: 'View Logs',
          onClick: () => console.log(`View logs for ${adapter.id}`),
        },
      ],
    });
  });

  // Warning: Disconnected adapters
  disconnected.forEach(adapter => {
    insights.push({
      id: `adapter-disconnected-${adapter.id}`,
      severity: 'warning',
      title: `⚠️ Adapter Disconnected: ${adapter.name}`,
      description: `${adapter.database_type.toUpperCase()} adapter lost connection. CDC changes may not be captured until reconnected.`,
      metric: adapter.database_type,
      actions: [
        {
          label: 'Retry Connection',
          onClick: () => console.log(`Retry adapter ${adapter.id}`),
        },
      ],
    });
  });

  // Info: High-lag adapters (only if lag data available)
  adapters.forEach(adapter => {
    if (adapter.status === 'connected' && adapter.cdc_lag_seconds !== null && adapter.cdc_lag_seconds > 20) {
      insights.push({
        id: `adapter-lag-${adapter.id}`,
        severity: 'info',
        title: `ℹ️ Adapter Lag: ${adapter.name}`,
        description: `${adapter.database_type} adapter has ${adapter.cdc_lag_seconds}s lag. Monitor for escalation.`,
        metric: `${adapter.cdc_lag_seconds}s lag`,
        actions: [],
      });
    }
  });

  return insights;
}

/**
 * Analyze throughput: detect significant drops indicating bottlenecks
 */
function analyzeThroughput(throughputSeries: TimeSeriesPoint[]): Insight[] {
  const insights: Insight[] = [];

  if (throughputSeries.length < 5) return insights;

  const latest = throughputSeries[throughputSeries.length - 1];
  const avgRecent = getAverage(throughputSeries, 10);
  const trend = detectTrend(throughputSeries);

  if (avgRecent > 0) {
    // Critical: Dropped to near-zero
    if (latest.value < avgRecent * 0.1) {
      insights.push({
        id: 'throughput-critical',
        severity: 'critical',
        title: '🔴 ETL Throughput Collapsed',
        description: `ETL processing has nearly stopped: ${latest.value.toFixed(0)} rec/sec (was ${avgRecent.toFixed(0)}). Possible system failure or queue deadlock.`,
        metric: `${latest.value.toFixed(0)} rec/sec`,
        actions: [
          {
            label: 'Check System Health',
            onClick: () => console.log('View system health'),
          },
          {
            label: 'View Error Logs',
            onClick: () => console.log('View error logs'),
          },
        ],
      });
    }
    // Warning: Significant drop
    else if (latest.value < avgRecent * 0.6) {
      insights.push({
        id: 'throughput-drop',
        severity: 'warning',
        title: '⚠️ Throughput Declining',
        description: `ETL throughput dropped ${((1 - latest.value / avgRecent) * 100).toFixed(0)}% — currently ${latest.value.toFixed(0)} rec/sec. Possible ETL bottleneck or resource contention.`,
        metric: `${latest.value.toFixed(0)} rec/sec`,
        actions: [
          {
            label: 'Check ETL Queue',
            onClick: () => console.log('View ETL metrics'),
          },
        ],
      });
    }
    // Info: Trending down
    else if (trend.direction === 'decreasing' && trend.percentChange < -15) {
      insights.push({
        id: 'throughput-trend',
        severity: 'info',
        title: 'ℹ️ Throughput Declining',
        description: `ETL throughput is declining (${trend.percentChange.toFixed(0)}%). Monitor for further degradation.`,
        metric: `${trend.percentChange.toFixed(0)}% trend`,
        actions: [],
      });
    }
  }

  return insights;
}

/**
 * Analyze latency: detect performance degradation
 */
function analyzeLatency(latencySeries: TimeSeriesPoint[]): Insight[] {
  const insights: Insight[] = [];

  if (latencySeries.length < 1) return insights;

  const latest = latencySeries[latencySeries.length - 1];

  // Critical: Latency above 1000ms
  if (latest.value > 1000) {
    insights.push({
      id: 'latency-critical',
      severity: 'critical',
      title: '🔴 Critical Latency',
      description: `API latency is ${latest.value.toFixed(0)}ms — system is severely unresponsive. Users may experience timeouts.`,
      metric: `${latest.value.toFixed(0)}ms`,
      actions: [
        {
          label: 'Check Database',
          onClick: () => console.log('View database metrics'),
        },
      ],
    });
  }
  // Warning: Above 500ms
  else if (latest.value > 500) {
    insights.push({
      id: 'latency-high',
      severity: 'warning',
      title: '⚠️ High API Latency',
      description: `API latency is elevated at ${latest.value.toFixed(0)}ms. Response times above 500ms can degrade user experience.`,
      metric: `${latest.value.toFixed(0)}ms`,
      actions: [
        {
          label: 'Profile Request',
          onClick: () => console.log('View request profile'),
        },
      ],
    });
  }
  // Info: Elevated
  else if (latest.value > 300) {
    insights.push({
      id: 'latency-elevated',
      severity: 'info',
      title: 'ℹ️ Elevated Latency',
      description: `API latency is ${latest.value.toFixed(0)}ms (typical: <300ms). Monitor performance.`,
      metric: `${latest.value.toFixed(0)}ms`,
      actions: [],
    });
  }

  return insights;
}

/**
 * Analyze ETL transform time: detect processing bottlenecks
 */
function analyzeEtlTime(etlTimeSeries: TimeSeriesPoint[]): Insight[] {
  const insights: Insight[] = [];

  if (etlTimeSeries.length < 2) return insights;

  const latest = etlTimeSeries[etlTimeSeries.length - 1];
  const avgRecent = getAverage(etlTimeSeries, 5);
  const trend = detectTrend(etlTimeSeries);

  // Critical: Way over average
  if (latest.value > avgRecent * 3 && latest.value > 100) {
    insights.push({
      id: 'etl-slow-critical',
      severity: 'critical',
      title: '🔴 ETL Processing Critical',
      description: `FHIR transform time is ${latest.value.toFixed(0)}ms/record — extremely slow. FHIR mapping or validation may be failing.`,
      metric: `${latest.value.toFixed(0)}ms/rec`,
      actions: [
        {
          label: 'Check Mappings',
          onClick: () => console.log('View ETL mappings'),
        },
      ],
    });
  }
  // Warning: Doubled
  else if (latest.value > avgRecent * 2 && latest.value > 50) {
    insights.push({
      id: 'etl-slow',
      severity: 'warning',
      title: '⚠️ ETL Processing Slow',
      description: `Transform time is ${latest.value.toFixed(0)}ms/record (avg: ${avgRecent.toFixed(0)}ms) — possible FHIR mapping bottleneck or network latency.`,
      metric: `${latest.value.toFixed(0)}ms/rec`,
      actions: [
        {
          label: 'View ETL Metrics',
          onClick: () => console.log('View ETL detail'),
        },
      ],
    });
  }
  // Info: Trending up
  else if (trend.direction === 'increasing' && trend.percentChange > 20) {
    insights.push({
      id: 'etl-trend',
      severity: 'info',
      title: 'ℹ️ ETL Time Increasing',
      description: `Transform time is trending upward (+${trend.percentChange.toFixed(0)}%). Monitor for degradation.`,
      metric: `+${trend.percentChange.toFixed(0)}% trend`,
      actions: [],
    });
  }

  return insights;
}

/**
 * Analyze CDC capture rate: detect sync quality issues
 */
function analyzeCdcCapture(cdcCaptureSeries: TimeSeriesPoint[]): Insight[] {
  const insights: Insight[] = [];

  if (cdcCaptureSeries.length < 1) return insights;

  const latest = cdcCaptureSeries[cdcCaptureSeries.length - 1];

  // Critical: Below 90%
  if (latest.value < 90) {
    insights.push({
      id: 'cdc-capture-low',
      severity: 'critical',
      title: `🔴 CDC Capture Rate Low`,
      description: `Only ${latest.value.toFixed(1)}% of database changes are being captured. Critical data is missing from the pipeline.`,
      metric: `${latest.value.toFixed(1)}%`,
      actions: [
        {
          label: 'Check Triggers',
          onClick: () => console.log('View CDC triggers'),
        },
      ],
    });
  }
  // Warning: Below 95%
  else if (latest.value < 95) {
    insights.push({
      id: 'cdc-capture-below-target',
      severity: 'warning',
      title: '⚠️ CDC Capture Below Target',
      description: `CDC capture rate is ${latest.value.toFixed(1)}% (target: 99%+). Some hospital changes may not sync.`,
      metric: `${latest.value.toFixed(1)}%`,
      actions: [
        {
          label: 'Review Adapters',
          onClick: () => console.log('View adapters'),
        },
      ],
    });
  }
  // Success: Healthy
  else if (latest.value >= 99) {
    insights.push({
      id: 'cdc-capture-healthy',
      severity: 'success',
      title: '✓ CDC Capture Healthy',
      description: `CDC capture rate is ${latest.value.toFixed(1)}% — all hospital changes are being synchronized.`,
      metric: `${latest.value.toFixed(1)}%`,
      actions: [],
    });
  }

  return insights;
}

// ── Main Analysis Function ────────────────────────────────────────────────────

/**
 * Combine all analysis and generate insights
 */
function analyzeMetrics(props: SystemInsightsProps): Insight[] {
  const insights: Insight[] = [];

  // CRITICAL: Data Completeness Check
  // Require minimum data points to perform meaningful analysis
  // Prevents generating fake "healthy" alerts on insufficient data
  const hasMinimumData =
    props.latencySeries.length >= 2 &&
    props.throughputSeries.length >= 2 &&
    props.cdcLagSeries.length >= 2 &&
    props.cdcCaptureSeries.length >= 2 &&
    props.adapters.length > 0;

  // If insufficient data, show baseline collection message instead of analysis
  if (!hasMinimumData) {
    insights.push({
      id: 'collecting-baseline',
      severity: 'info',
      title: 'ℹ️ Collecting Baseline Metrics',
      description: `System is collecting operational data. Insights will be available once we have: latency (${props.latencySeries.length}/2), throughput (${props.throughputSeries.length}/2), CDC lag (${props.cdcLagSeries.length}/2), capture rate (${props.cdcCaptureSeries.length}/2), and adapters (${props.adapters.length}/1+).`,
      metric: 'Baseline collection in progress',
      actions: [],
    });
    return insights;
  }

  // Data is complete — run all analysis functions
  insights.push(...analyzeCdcLag(props.cdcLagSeries));
  insights.push(...analyzeAdapters(props.adapters));
  insights.push(...analyzeThroughput(props.throughputSeries));
  insights.push(...analyzeLatency(props.latencySeries));
  insights.push(...analyzeEtlTime(props.etlTimeSeries));
  insights.push(...analyzeCdcCapture(props.cdcCaptureSeries));

  // If no issues detected, show all-clear message
  if (insights.length === 0) {
    insights.push({
      id: 'all-healthy',
      severity: 'success',
      title: '✓ All Systems Healthy',
      description: 'CDC pipeline, ETL processing, and all adapters operating normally. Healthcare data synchronization is optimal.',
      actions: [],
    });
  }

  return insights;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface SystemInsightsComponentProps extends SystemInsightsProps {
  isLoading?: boolean;
}

/**
 * System Insights & Alerts UI Component
 */
const SystemInsights: React.FC<SystemInsightsComponentProps> = ({ isLoading = false, ...props }) => {
  const insights = analyzeMetrics(props);

  const getSeverityStyle = (severity: InsightSeverity) => {
    switch (severity) {
      case 'critical':
        return {
          bg: 'rgba(239, 68, 68, 0.1)',
          border: 'rgba(239, 68, 68, 0.3)',
          textColor: '#dc2626',
        };
      case 'warning':
        return {
          bg: 'rgba(245, 158, 11, 0.1)',
          border: 'rgba(245, 158, 11, 0.3)',
          textColor: '#d97706',
        };
      case 'info':
        return {
          bg: 'rgba(59, 130, 246, 0.1)',
          border: 'rgba(59, 130, 246, 0.3)',
          textColor: '#2563eb',
        };
      case 'success':
        return {
          bg: 'rgba(16, 185, 129, 0.1)',
          border: 'rgba(16, 185, 129, 0.3)',
          textColor: '#059669',
        };
    }
  };

  // Sort: critical first, then warning, info, success
  const sortedInsights = [...insights].sort((a, b) => {
    const severityOrder = { critical: 0, warning: 1, info: 2, success: 3 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  return (
    <div className="ds-animate ds-animate-d5" style={{ marginTop: '3rem' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        marginBottom: '1.5rem',
        fontSize: '1rem',
        fontWeight: 700,
        color: 'var(--ds-text-primary)',
      }}>
        <AlertCircle style={{ width: 18, height: 18 }} />
        System Insights & Alerts
      </div>

      {isLoading && insights.length === 0 ? (
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--ds-text-muted)',
        }}>
          Analyzing metrics…
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
          gap: '1rem',
        }}>
          {sortedInsights.map(insight => {
            const style = getSeverityStyle(insight.severity);

            return (
              <div
                key={insight.id}
                style={{
                  background: style.bg,
                  border: `1px solid ${style.border}`,
                  borderRadius: '1rem',
                  padding: '1.25rem',
                  boxShadow: 'var(--ds-card-shadow)',
                }}
              >
                {/* Title & Icon */}
                <div style={{
                  display: 'flex',
                  gap: '0.75rem',
                  marginBottom: '0.75rem',
                  alignItems: 'flex-start',
                }}>
                  <div style={{ color: style.textColor, marginTop: '0.125rem', flexShrink: 0 }}>
                    {insight.severity === 'critical' && <AlertTriangle style={{ width: 18, height: 18 }} />}
                    {insight.severity === 'warning' && <AlertTriangle style={{ width: 18, height: 18 }} />}
                    {insight.severity === 'info' && <AlertCircle style={{ width: 18, height: 18 }} />}
                    {insight.severity === 'success' && <CheckCircle style={{ width: 18, height: 18 }} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: '0.875rem',
                      fontWeight: 700,
                      color: 'var(--ds-text-primary)',
                    }}>
                      {insight.title}
                    </div>
                  </div>
                </div>

                {/* Description */}
                <div style={{
                  fontSize: '0.8125rem',
                  color: 'var(--ds-text-muted)',
                  lineHeight: 1.6,
                  marginBottom: insight.actions.length > 0 ? '0.75rem' : '0',
                }}>
                  {insight.description}
                </div>

                {/* Metric Badge */}
                {insight.metric && (
                  <div style={{
                    display: 'inline-block',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: style.textColor,
                    background: 'rgba(0,0,0,0.05)',
                    padding: '0.25rem 0.5rem',
                    borderRadius: '0.375rem',
                    marginBottom: insight.actions.length > 0 ? '0.75rem' : '0',
                    marginTop: '0.5rem',
                  }}>
                    {insight.metric}
                  </div>
                )}

                {/* Actions */}
                {insight.actions.length > 0 && (
                  <div style={{
                    display: 'flex',
                    gap: '0.5rem',
                    marginTop: '0.75rem',
                    paddingTop: '0.75rem',
                    borderTop: `1px solid ${style.border}`,
                  }}>
                    {insight.actions.map((action, i) => (
                      <button
                        key={i}
                        onClick={action.onClick}
                        disabled={action.loading}
                        className="ds-btn"
                        style={{
                          fontSize: '0.75rem',
                          padding: '0.375rem 0.75rem',
                          flex: 1,
                          opacity: action.loading ? 0.6 : 1,
                          cursor: action.loading ? 'not-allowed' : 'pointer',
                          color: style.textColor,
                        }}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SystemInsights;
