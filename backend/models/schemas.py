"""
Pydantic Schemas for Universal Location-Aware Forecasting in Strata Risk.
Strictly defines request and response payloads, ensuring robust validation,
honest coverage reporting, and backward compatibility.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class LocationCoordinate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90 degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180 degrees")


class LocationForecastRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Target location latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Target location longitude")
    horizon_hours: int = Field(default=4, ge=1, le=24, description="Forecast horizon in hours (default: 4)")
    time: str = Field(default="20:00", description="Forecast time slice (e.g. '08:00', '12:00', '16:00', '20:00', '00:00')")
    date: Optional[str] = Field(default="Mon, Oct 24", description="Scenario date string")
    timezone: Optional[str] = Field(default=None, description="Optional target location timezone identifier")

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        # Standardize or accept valid HH:MM
        parts = v.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        return "20:00"


class LocationInfo(BaseModel):
    latitude: float
    longitude: float
    display_name: str
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    timezone: str = "UTC"
    resolved_sector_id: Optional[str] = None
    resolved_sector_name: Optional[str] = None
    resolved_zone_key: Optional[str] = None
    distance_to_centroid_km: Optional[float] = None


class CoverageInfo(BaseModel):
    status: str = Field(..., description="Coverage status: SUPPORTED | PARTIAL_COVERAGE | INSUFFICIENT_DATA | UNSUPPORTED | DATA_SOURCE_UNAVAILABLE")
    dataset_name: Optional[str] = None
    data_source: Optional[str] = None
    provenance_url: Optional[str] = None
    historical_start: Optional[str] = None
    historical_end: Optional[str] = None
    observations_available: int = 0
    spatial_resolution: Optional[str] = None
    last_synced: Optional[str] = None


class ForecastResult(BaseModel):
    horizon_hours: int = 4
    risk_probability: Optional[float] = None
    risk_level: Optional[str] = None  # Lower | Moderate | Higher | Sparse | Unavailable
    risk_score_100: Optional[int] = None
    calibrated: bool = False
    uncertainty: Optional[str] = None
    local_forecast_time: Optional[str] = None
    utc_forecast_time: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)


class ModelMetaInfo(BaseModel):
    model_id: str
    engine: str
    dataset_type: str  # real | synthetic | none
    validated_for_region: bool
    operational_threshold: float = 0.50
    auc_roc: Optional[float] = None
    brier_score: Optional[float] = None


class LocationForecastResponse(BaseModel):
    status: str = Field(..., description="Overall response status: supported | partial_coverage | insufficient_data | unsupported | error")
    location: LocationInfo
    coverage: CoverageInfo
    forecast: Optional[ForecastResult] = None
    model: Optional[ModelMetaInfo] = None
    limitations: List[str] = Field(default_factory=list)
    available_alternatives: List[Dict[str, Any]] = Field(default_factory=list)


class LocationSearchResult(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    region_id: Optional[str] = None
    coverage_status: str
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = "UTC"


class CoverageCheckResponse(BaseModel):
    latitude: float
    longitude: float
    status: str
    region_id: Optional[str] = None
    region_name: Optional[str] = None
    dataset_name: Optional[str] = None
    validated_model_available: bool = False
    message: str


class DataSourceInfo(BaseModel):
    id: str
    name: str
    region_id: str
    region_name: str
    country: str
    status: str
    is_validated: bool
    historical_records: int
    source_url: str
    auth_required: bool
    observation_period: Dict[str, str]
    notes: str


class RegionInfo(BaseModel):
    region_id: str
    name: str
    country: str
    center_lat: float
    center_lon: float
    bounding_box: Dict[str, float]
    coverage_status: str
    has_validated_model: bool
    dataset_provider: str
    sensor_lattice_type: str
