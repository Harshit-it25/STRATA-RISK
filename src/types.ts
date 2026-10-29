export type ScreenType = 'overview' | 'risk-map' | 'compare' | 'validation';

export type RiskLevel = 'Lower' | 'Moderate' | 'Higher' | 'Sparse';

export interface ZoneData {
  id: string;
  key: 'market' | 'central' | 'riverside' | 'east';
  name: string;
  code: string;
  tag: string;
  score: number | string;
  delta: string;
  trend: 'north_east' | 'south_east' | 'trending_flat' | 'remove';
  trendLabel: string;
  level: RiskLevel;
  observations: number | string;
  reasons: string[];
  coordinates: { x: number; y: number };
}

export interface TimeStep {
  hour: string;
  label: string;
  sublabel: string;
  fillPct: string;
  zones: {
    market: ZoneData;
    central: ZoneData;
    riverside: ZoneData;
    east: ZoneData;
  };
}

export interface SectorOption {
  id: string;
  name: string;
  code: string;
  status: string;
  incidentTrend: string;
}

export interface OverlayLayers {
  densityHeatmap: boolean;
  transitArteries: boolean;
  sensorNodes: boolean;
  confidenceBands: boolean;
  topographicGrid: boolean;
}

// Backend API Contracts
export interface BackendHealthResponse {
  status: string;
  timestamp: string;
  service?: string;
  version?: string;
}

export interface ModelHealthResponse {
  status: string;
  engine: string;
  model_version: string;
  feed_integrity: string;
  active_precinct_logs: number;
  precinct_coverage?: string;
  last_ingested?: string;
  mean_latency_ms?: number;
  records_ingested_total?: number | string;
  confidence_interval?: string;
}

export interface BaselineMetrics {
  brier_score?: number;
  roc_auc?: number;
  pr_auc?: number;
  log_loss?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  precision_top_20pct?: number;
  sample_count?: number;
}

export interface ValidationResponse {
  validation_status: 'completed' | 'pending';
  dataset_type?: 'synthetic' | 'real';
  dataset_name?: string;
  real_data_validation_status?: 'completed' | 'pending';
  usable_records?: number;
  total_records_ingested?: number;
  date_range?: { start: string; end: string; duration_days?: number };
  evaluation_period?: string;
  data_quality_warnings?: string[];
  brier_score?: number | string | null;
  brier_target?: string;
  brier_status?: string;
  roc_auc?: number | string | null;
  roc_auc_status?: string;
  pr_auc?: number | string | null;
  expected_calibration_error?: number | string | null;
  calibration_slope?: number | string | null;
  log_loss?: number | string | null;
  precision?: number | string | null;
  recall?: number | string | null;
  f1_score?: number | string | null;
  precision_top_20pct?: number | string | null;
  recall_top_20pct?: number | string | null;
  operational_precision_top_20pct?: number | null;
  operational_recall_top_20pct?: number | null;
  demographic_parity?: number | string | null;
  disparate_impact_ratio?: number | string | null;
  personal_identity_ingestion?: string;
  empirical_uncertainty?: {
    residual_std?: number;
    empirical_uncertainty_band?: string;
    uncertainty_points?: number;
    methodology?: string;
  };
  baseline_comparison?: {
    candidate_catboost?: BaselineMetrics;
    historical_spatial_baseline?: BaselineMetrics;
    temporal_cyclical_baseline?: BaselineMetrics;
  };
  last_calibration_date?: string;
  audited_by?: string;
  model_version?: string;
  sample_count?: number;
}

export interface ForecastResponse {
  sector_id: string;
  sector_name: string;
  time: string;
  date: string;
  status_overview: {
    status: string;
    window: string;
    risk_percentage: number;
    monitored_sectors_count: number;
    refreshed_at: string;
    elevated_sectors: Array<{
      name: string;
      variance?: string;
      density?: string;
      level: RiskLevel;
    }>;
  };
  time_step: TimeStep;
  timeline: TimeStep[];
  uncertainty_band?: string;
  model_id?: string;
}

export interface MapResponse {
  sector_id: string;
  coordinate_bounds: string;
  active_overlay_layers: number;
  cell_resolution: string;
  zones: Record<string, {
    score: number | string;
    level: RiskLevel;
    delta: string;
    trend: 'north_east' | 'south_east' | 'trending_flat' | 'remove';
    prob?: number | null;
  }>;
  heatmap_centers?: Array<{
    id: string;
    x: number;
    y: number;
    radius: number;
    intensity: number;
    color: string;
  }>;
  arteries?: string[];
  sensor_count?: number;
}

// Universal Location-Aware Forecasting Contracts

export type GeographicCoverageStatus =
  | 'SUPPORTED'
  | 'PARTIAL_COVERAGE'
  | 'INSUFFICIENT_DATA'
  | 'UNSUPPORTED'
  | 'DATA_SOURCE_UNAVAILABLE';

export interface LocationSearchResult {
  display_name: string;
  latitude: number;
  longitude: number;
  region_id?: string | null;
  coverage_status: GeographicCoverageStatus;
  city?: string | null;
  country?: string | null;
  timezone?: string | null;
}

export interface SelectedLocation {
  displayName: string;
  latitude: number;
  longitude: number;
  regionId?: string | null;
  regionName?: string | null;
  coverageStatus: GeographicCoverageStatus;
  timezone?: string;
  resolvedSectorId?: string | null;
  resolvedZoneKey?: string | null;
  sourceType: 'search' | 'current_location' | 'coordinates' | 'map_click' | 'preset';
}

export interface CoverageCheckResponse {
  latitude: number;
  longitude: number;
  status: GeographicCoverageStatus;
  region_id?: string | null;
  region_name?: string | null;
  dataset_name?: string | null;
  validated_model_available: boolean;
  message: string;
}

export interface LocationForecastResponse {
  status: 'supported' | 'partial_coverage' | 'insufficient_data' | 'unsupported' | 'error';
  location: {
    latitude: number;
    longitude: number;
    display_name: string;
    region_id?: string | null;
    region_name?: string | null;
    timezone: string;
    resolved_sector_id?: string | null;
    resolved_sector_name?: string | null;
    resolved_zone_key?: string | null;
    distance_to_centroid_km?: number | null;
  };
  coverage: {
    status: GeographicCoverageStatus;
    dataset_name?: string | null;
    data_source?: string | null;
    provenance_url?: string | null;
    historical_start?: string | null;
    historical_end?: string | null;
    observations_available: number;
    spatial_resolution?: string | null;
    last_synced?: string | null;
  };
  forecast?: {
    horizon_hours: number;
    risk_probability: number | null;
    risk_level: string | null;
    risk_score_100: number | null;
    calibrated: boolean;
    uncertainty?: string | null;
    local_forecast_time?: string | null;
    utc_forecast_time?: string | null;
    reasons: string[];
  } | null;
  model?: {
    model_id: string;
    engine: string;
    dataset_type: string;
    validated_for_region: boolean;
    operational_threshold: number;
    auc_roc?: number | null;
    brier_score?: number | null;
  } | null;
  limitations: string[];
  available_alternatives: Array<{
    region_id: string;
    name: string;
    latitude: number;
    longitude: number;
    coverage_status: string;
    description: string;
  }>;
}

export interface DataSourceItem {
  id: string;
  region_id: string;
  name: string;
  source_url: string;
  records_count: number;
  model_validated: boolean;
  requires_auth: boolean;
  bounding_box: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  observation_period: {
    start: string;
    end: string;
  };
  notes: string;
}


