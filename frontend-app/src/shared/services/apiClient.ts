/**
 * shared/services/apiClient.ts
 * Centralized API client with auth, error handling, retries, and health monitoring
 * Single source of truth for all backend communication
 */

import axios from 'axios';
import type {
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';

// ── Error Type Definition ────────────────────────────────────────────────────
export type ApiErrorType =
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'SERVER_ERROR'
  | 'UNKNOWN';

export interface ApiError extends Error {
  type: ApiErrorType;
  status?: number;
  path?: string;
  timestamp: string;
  requestId: string;
  originalError?: Error;
  isRetryable: boolean;
  shouldShowToUser: boolean;
  userMessage: string;
}

// ── Health Check State ───────────────────────────────────────────────────────
interface HealthCheckState {
  isHealthy: boolean | null;
  lastChecked: number;
  failureCount: number; // Consecutive failures
  successCount: number; // Consecutive successes after failure
}

// ── Event Listeners ──────────────────────────────────────────────────────────
type EventListener = (...args: any[]) => void;

interface EventMap {
  'error': (error: ApiError) => void;
  'backend-offline': () => void;
  'backend-online': () => void;
  'health-check': (healthy: boolean) => void;
  'auth-expired': () => void;
}

// ── Retry Configuration ──────────────────────────────────────────────────────
export interface RetryConfig {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  retryableStatuses: number[];
  timeoutMs: number;
}

// ── API Client Class ─────────────────────────────────────────────────────────
class ApiClientImpl {
  private axiosInstance: AxiosInstance;
  private token: string | null = null;
  private eventListeners: Map<keyof EventMap, EventListener[]> = new Map();
  private healthCheck: HealthCheckState = {
    isHealthy: null,
    lastChecked: 0,
    failureCount: 0,
    successCount: 0,
  };
  private healthCheckInterval: ReturnType<typeof setInterval> | null = null;
  private requestIdCounter = 0;

  private retryConfig: RetryConfig = {
    maxAttempts: 3,
    baseDelayMs: 100,
    maxDelayMs: 5000,
    retryableStatuses: [408, 429, 503, 504],
    timeoutMs: 5000,
  };

  private readonly HEALTH_CHECK_INTERVAL_MS = 30000; // 30s
  private readonly HEALTH_CHECK_TIMEOUT_MS = 2000; // 2s
  private readonly MULTI_FAILURE_THRESHOLD = 2; // Mark offline after 2 failures
  private readonly MULTI_SUCCESS_THRESHOLD = 2; // Mark online after 2 successes

  constructor(baseURL: string = import.meta.env.VITE_API_URL || '') {
    this.axiosInstance = axios.create({
      baseURL,
      timeout: this.retryConfig.timeoutMs,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // ── Request Interceptor: Add Auth + Request ID ──
    this.axiosInstance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
      // Add Bearer token if available
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }

      // Add unique request ID for tracing
      config.headers['X-Request-ID'] = this.generateRequestId();

      return config;
    });

    // ── Response Interceptor: Error Handling ──
    this.axiosInstance.interceptors.response.use(
      response => response,
      error => Promise.reject(error)
    );

    // Start periodic health checks
    this.startHealthCheck();
  }

  // ── Public API ───────────────────────────────────────────────────────────

  /**
   * Set authentication token for all requests
   */
  public setToken(token: string | null): void {
    this.token = token;
    if (token) {
      this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete this.axiosInstance.defaults.headers.common['Authorization'];
    }
  }

  /**
   * Generic GET request with type safety
   */
  public async get<T = any>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
    return this.requestWithRetry<T>('GET', endpoint, undefined, config);
  }

  /**
   * Generic POST request with type safety
   */
  public async post<T = any>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.requestWithRetry<T>('POST', endpoint, data, config);
  }

  /**
   * Generic PUT request with type safety
   */
  public async put<T = any>(endpoint: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.requestWithRetry<T>('PUT', endpoint, data, config);
  }

  /**
   * Generic DELETE request with type safety
   */
  public async delete<T = any>(endpoint: string, config?: AxiosRequestConfig): Promise<T> {
    return this.requestWithRetry<T>('DELETE', endpoint, undefined, config);
  }

  /**
   * Check if backend is currently healthy (cached, 30s)
   */
  public async isBackendHealthy(): Promise<boolean> {
    // Return cached result if recent
    const now = Date.now();
    if (
      this.healthCheck.isHealthy !== null &&
      now - this.healthCheck.lastChecked < 5000
    ) {
      return this.healthCheck.isHealthy;
    }

    try {
      await this.axiosInstance.get('/health', {
        timeout: this.HEALTH_CHECK_TIMEOUT_MS,
        headers: { 'X-Skip-Retry': 'true' }, // Don't retry health checks
      });

      this.recordHealthSuccess();
      return true;
    } catch {
      this.recordHealthFailure();
      return false;
    }
  }

  /**
   * Register event listener
   */
  public on<K extends keyof EventMap>(event: K, handler: EventMap[K]): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(handler);
  }

  /**
   * Unregister event listener
   */
  public off<K extends keyof EventMap>(event: K, handler: EventMap[K]): void {
    const listeners = this.eventListeners.get(event);
    if (!listeners) return;
    const index = listeners.indexOf(handler);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  }

  /**
   * Get current health status
   */
  public getHealthStatus(): boolean | null {
    return this.healthCheck.isHealthy;
  }

  /**
   * Manually check health (bypass cache)
   */
  public async refreshHealthCheck(): Promise<boolean> {
    this.healthCheck.lastChecked = 0; // Clear cache
    return this.isBackendHealthy();
  }

  /**
   * Set retry configuration
   */
  public setRetryConfig(config: Partial<RetryConfig>): void {
    this.retryConfig = { ...this.retryConfig, ...config };
    this.axiosInstance.defaults.timeout = this.retryConfig.timeoutMs;
  }

  /**
   * Stop periodic health checks (cleanup)
   */
  public stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  // ── Private Methods ──────────────────────────────────────────────────────

  /**
   * Execute request with retry logic
   * IMPORTANT: Only GET requests can be retried. POST/PUT/DELETE/PATCH are not idempotent and must never retry.
   */
  private async requestWithRetry<T>(
    method: string,
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    let lastError: ApiError | null = null;

    for (let attempt = 0; attempt < this.retryConfig.maxAttempts; attempt++) {
      try {
        const response = await this.executeRequest<T>(method, endpoint, data, config);
        return response;
      } catch (error) {
        lastError = this.normalizeError(error, endpoint);

        // CRITICAL: Only retry idempotent GET requests
        // POST/PUT/DELETE/PATCH must NEVER retry (causes duplicate operations)
        const isIdempotent = method.toUpperCase() === 'GET';
        const shouldRetry = isIdempotent && lastError.isRetryable;

        // Check if we should retry
        if (!shouldRetry || attempt === this.retryConfig.maxAttempts - 1) {
          this.emit('error', lastError);
          throw lastError;
        }

        // Exponential backoff with jitter
        const delayMs = Math.min(
          this.retryConfig.baseDelayMs * Math.pow(2, attempt),
          this.retryConfig.maxDelayMs
        );
        await this.sleep(delayMs);
      }
    }

    throw lastError;
  }

  /**
   * Execute single request
   */
  private async executeRequest<T>(
    method: string,
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.axiosInstance.request<T>({
      method,
      url: endpoint,
      data,
      ...config,
    });
    return response.data;
  }

  /**
   * Normalize various error types to ApiError
   */
  private normalizeError(error: any, endpoint: string): ApiError {
    const requestId = this.extractRequestId(error);
    const timestamp = new Date().toISOString();

    // Network error (no response)
    if (!error.response) {
      if (error.code === 'ECONNABORTED') {
        return {
          name: 'ApiError',
          message: 'Request timed out. Backend may be slow or offline.',
          type: 'TIMEOUT',
          timestamp,
          requestId,
          path: endpoint,
          isRetryable: true,
          shouldShowToUser: true,
          userMessage: 'Request timed out. Please try again.',
          originalError: error,
        };
      }

      return {
        name: 'ApiError',
        message: `Network error: ${error.message}`,
        type: 'NETWORK_ERROR',
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: true,
        shouldShowToUser: true,
        userMessage: 'Network error. Please check your connection and try again.',
        originalError: error,
      };
    }

    const status = error.response?.status;
    const data = error.response?.data;

    // 401 Unauthorized
    if (status === 401) {
      // Clear token and emit auth-expired event
      this.token = null;
      delete this.axiosInstance.defaults.headers.common['Authorization'];
      this.emit('auth-expired');

      return {
        name: 'ApiError',
        message: 'Authentication failed',
        type: 'UNAUTHORIZED',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: false,
        shouldShowToUser: true,
        userMessage: 'Session expired. Please log in again.',
        originalError: error,
      };
    }

    // 403 Forbidden
    if (status === 403) {
      // Surface the backend's role-mismatch detail when available
      const detail = data?.detail || 'You do not have permission to perform this action.';
      return {
        name: 'ApiError',
        message: 'Access denied',
        type: 'FORBIDDEN',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: false,
        shouldShowToUser: true,
        userMessage: detail,
        originalError: error,
      };
    }

    // 404 Not Found
    if (status === 404) {
      const detail = data?.detail || 'The requested resource was not found.';
      return {
        name: 'ApiError',
        message: 'Resource not found',
        type: 'NOT_FOUND',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: false,
        shouldShowToUser: false,
        userMessage: detail,
        originalError: error,
      };
    }

    // 409 Conflict — e.g. a sync run is already queued/running
    if (status === 409) {
      const detail = data?.detail || 'A conflicting operation is already in progress.';
      return {
        name: 'ApiError',
        message: detail,
        type: 'VALIDATION_ERROR',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: false,
        shouldShowToUser: true,
        userMessage: detail,
        originalError: error,
      };
    }

    // 422 Validation Error
    if (status === 422) {
      const detail = data?.detail || 'Invalid input';
      return {
        name: 'ApiError',
        message: typeof detail === 'string' ? detail : JSON.stringify(detail),
        type: 'VALIDATION_ERROR',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: false,
        shouldShowToUser: true,
        userMessage: typeof detail === 'string' ? detail : 'Invalid request payload.',
        originalError: error,
      };
    }

    // 5xx Server Error — include backend detail when available
    if (status && status >= 500) {
      const detail = data?.detail || data?.message;
      return {
        name: 'ApiError',
        message: `Server error: ${status}`,
        type: 'SERVER_ERROR',
        status,
        timestamp,
        requestId,
        path: endpoint,
        isRetryable: this.retryConfig.retryableStatuses.includes(status),
        shouldShowToUser: true,
        userMessage: detail
          ? String(detail).slice(0, 200)
          : 'Server error. Please try again in a moment.',
        originalError: error,
      };
    }

    // Generic HTTP error — try to surface backend detail
    const fallbackDetail = data?.detail || data?.error || data?.message || error.message;
    return {
      name: 'ApiError',
      message: fallbackDetail,
      type: 'UNKNOWN',
      status,
      timestamp,
      requestId,
      path: endpoint,
      isRetryable: this.retryConfig.retryableStatuses.includes(status),
      shouldShowToUser: true,
      userMessage: fallbackDetail
        ? String(fallbackDetail).slice(0, 200)
        : 'An error occurred. Please try again.',
      originalError: error,
    };
  }

  /**
   * Start periodic health checks
   */
  private startHealthCheck(): void {
    // Initial check
    this.isBackendHealthy().catch(() => {});

    // Periodic checks
    this.healthCheckInterval = setInterval(() => {
      this.isBackendHealthy().catch(() => {});
    }, this.HEALTH_CHECK_INTERVAL_MS);
  }

  /**
   * Record successful health check
   */
  private recordHealthSuccess(): void {
    this.healthCheck.lastChecked = Date.now();
    this.healthCheck.failureCount = 0;
    this.healthCheck.successCount += 1;

    // Transition from offline to online
    if (this.healthCheck.isHealthy === false &&
        this.healthCheck.successCount >= this.MULTI_SUCCESS_THRESHOLD) {
      this.healthCheck.isHealthy = true;
      this.emit('backend-online');
    } else if (this.healthCheck.isHealthy === null) {
      this.healthCheck.isHealthy = true;
    }
  }

  /**
   * Record failed health check
   */
  private recordHealthFailure(): void {
    this.healthCheck.lastChecked = Date.now();
    this.healthCheck.successCount = 0;
    this.healthCheck.failureCount += 1;

    // Transition from online to offline
    if ((this.healthCheck.isHealthy === true || this.healthCheck.isHealthy === null) &&
        this.healthCheck.failureCount >= this.MULTI_FAILURE_THRESHOLD) {
      this.healthCheck.isHealthy = false;
      this.emit('backend-offline');
    }
  }

  /**
   * Emit event to all listeners
   */
  private emit<K extends keyof EventMap>(event: K, ...args: Parameters<EventMap[K]>): void {
    const listeners = this.eventListeners.get(event) || [];
    listeners.forEach(listener => {
      try {
        (listener as any)(...args);
      } catch (err) {
        console.error(`Error in event listener for '${String(event)}':`, err);
      }
    });
  }

  /**
   * Generate unique request ID
   */
  private generateRequestId(): string {
    return `req-${Date.now()}-${++this.requestIdCounter}`;
  }

  /**
   * Extract request ID from error
   */
  private extractRequestId(error: any): string {
    return error.config?.headers?.['X-Request-ID'] || 'unknown';
  }

  /**
   * Sleep utility for retries
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ── Singleton Instance ───────────────────────────────────────────────────────
export const apiClient = new ApiClientImpl();

export default apiClient;
