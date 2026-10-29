import {
  BackendHealthResponse,
  ForecastResponse,
  MapResponse,
  ModelHealthResponse,
  ValidationResponse
} from '../types';

// Centralized API configuration
// Supports NEXT_PUBLIC_API_BASE_URL (per Step 2 specification) and VITE_API_BASE_URL
const getBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const customUrl = localStorage.getItem('strata_api_base_url');
    if (customUrl) return customUrl.replace(/\/+$/, '');
  }

  const envUrl =
    (import.meta.env as any).NEXT_PUBLIC_API_BASE_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    'http://localhost:8000';

  return envUrl.replace(/\/+$/, '');
};

export const API_BASE_URL = getBaseUrl();

export interface ApiResult<T> {
  ok: boolean;
  data?: T;
  error?: string;
  status?: number;
  isOffline?: boolean;
}

async function request<T>(
  endpoint: string,
  options?: RequestInit,
  timeoutMs = 4000
): Promise<ApiResult<T>> {
  const url = `${getBaseUrl()}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...(options?.headers || {})
      }
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errMsg = `Backend error ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.error || errorJson.detail) {
          errMsg = errorJson.error || errorJson.detail;
        }
      } catch {
        // fallback to statusText
      }

      return {
        ok: false,
        status: response.status,
        error: errMsg,
        isOffline: response.status >= 502 && response.status <= 504
      };
    }

    const data: T = await response.json();
    return { ok: true, data, status: response.status };
  } catch (err: any) {
    clearTimeout(timeoutId);

    const isAbort = err.name === 'AbortError';
    const isNetworkError =
      err instanceof TypeError ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError') ||
      isAbort;

    return {
      ok: false,
      isOffline: isNetworkError,
      error: isAbort
        ? `Request timed out after ${timeoutMs}ms (Backend unreachable)`
        : `Backend service offline (${getBaseUrl()})`
    };
  }
}

export const ApiService = {
  getBaseUrl,

  setBaseUrl: (newUrl: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('strata_api_base_url', newUrl.replace(/\/+$/, ''));
    }
  },

  resetBaseUrl: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('strata_api_base_url');
    }
  },

  /** GET /health - Basic connectivity and health verification */
  async checkHealth(): Promise<ApiResult<BackendHealthResponse>> {
    return request<BackendHealthResponse>('/health');
  },

  /** GET /api/forecast - Retrieve spatio-temporal risk forecast */
  async getForecast(params?: {
    sectorId?: string;
    time?: string;
    date?: string;
  }): Promise<ApiResult<ForecastResponse>> {
    const query = new URLSearchParams();
    if (params?.sectorId) query.set('sector_id', params.sectorId);
    if (params?.time) query.set('time', params.time);
    if (params?.date) query.set('date', params.date);

    const qs = query.toString();
    return request<ForecastResponse>(`/api/forecast${qs ? `?${qs}` : ''}`);
  },

  /** GET /api/map - Retrieve spatial grid, cell polygons and arterial nodes */
  async getMap(params?: {
    sectorId?: string;
    time?: string;
  }): Promise<ApiResult<MapResponse>> {
    const query = new URLSearchParams();
    if (params?.sectorId) query.set('sector_id', params.sectorId);
    if (params?.time) query.set('time', params.time);

    const qs = query.toString();
    return request<MapResponse>(`/api/map${qs ? `?${qs}` : ''}`);
  },

  /** GET /api/model/health - Telemetry, ingestion and model pipeline status */
  async getModelHealth(): Promise<ApiResult<ModelHealthResponse>> {
    return request<ModelHealthResponse>('/api/model/health');
  },

  /** GET /api/validation - Model calibration metrics and fairness audits */
  async getValidation(): Promise<ApiResult<ValidationResponse>> {
    return request<ValidationResponse>('/api/validation');
  },

  /** GET /api/location/search - Search for places, cities, and administrative districts */
  async searchLocations(
    query: string,
    limit = 5
  ): Promise<ApiResult<import('../types').LocationSearchResult[]>> {
    const q = encodeURIComponent(query.trim());
    return request<import('../types').LocationSearchResult[]>(
      `/api/location/search?q=${q}&limit=${limit}`
    );
  },

  /** GET /api/location/coverage - Check geographic coverage for latitude and longitude */
  async checkCoverage(
    latitude: number,
    longitude: number
  ): Promise<ApiResult<import('../types').CoverageCheckResponse>> {
    return request<import('../types').CoverageCheckResponse>(
      `/api/location/coverage?latitude=${latitude}&longitude=${longitude}`
    );
  },

  /** POST /api/forecast/location - Retrieve location-aware risk forecast with provenance */
  async getLocationForecast(params: {
    latitude: number;
    longitude: number;
    horizonHours?: number;
    time?: string;
    date?: string;
    timezone?: string;
  }): Promise<ApiResult<import('../types').LocationForecastResponse>> {
    return request<import('../types').LocationForecastResponse>('/api/forecast/location', {
      method: 'POST',
      body: JSON.stringify({
        latitude: params.latitude,
        longitude: params.longitude,
        horizon_hours: params.horizonHours ?? 4,
        time: params.time ?? '20:00',
        date: params.date ?? 'Mon, Oct 24',
        timezone: params.timezone
      })
    });
  },

  /** GET /api/data/sources - Retrieve registered geographic crime data providers */
  async getDataSources(): Promise<ApiResult<import('../types').DataSourceItem[]>> {
    return request<import('../types').DataSourceItem[]>('/api/data/sources');
  },

  /** GET /api/regions - Retrieve registered operational regions */
  async getRegions(): Promise<ApiResult<any[]>> {
    return request<any[]>('/api/regions');
  }
};

