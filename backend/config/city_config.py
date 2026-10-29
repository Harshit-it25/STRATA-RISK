"""
Minimal, typed City Configuration Abstraction for Strata Risk.

Enables multi-city operational management while ensuring:
1. Chicago remains fully operational on existing validated artifacts.
2. Candidate / pilot cities (Pune, Mumbai, NYC, London) are explicitly configured
   without implying model availability.
3. Unsupported cities never receive fabricated risk probabilities or foreign weights.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class CitySpatialConfig(BaseModel):
    """Spatial bounding box and jurisdictional unit configuration."""
    core_bounds: Dict[str, float]
    buffer_bounds: Optional[Dict[str, float]] = None
    spatial_unit_type: str = "lattice"  # "lattice" (grid cells) or "police_station" (administrative)
    spatial_resolution_desc: str = "N/A"
    unit_count: Optional[int] = None


class CityModelConfig(BaseModel):
    """City-specific ML model, calibrator, and feature schema registry."""
    model_id: Optional[str] = None
    engine: Optional[str] = None
    feature_schema_version: Optional[str] = None
    feature_columns: List[str] = Field(default_factory=list)
    model_artifact_path: Optional[str] = None
    calibrator_artifact_path: Optional[str] = None
    metadata_artifact_path: Optional[str] = None
    is_validated: bool = False
    operational_threshold: float = 0.50


class CityConfig(BaseModel):
    """Root configuration for an operational or candidate city."""
    city_id: str
    display_name: str
    country: str
    timezone: str
    coverage_status: str  # "SUPPORTED", "PARTIAL_COVERAGE", "INSUFFICIENT_DATA", "UNSUPPORTED"
    spatial: CitySpatialConfig
    model: CityModelConfig
    data_provider_id: Optional[str] = None
    dataset_name: Optional[str] = None
    data_source_name: Optional[str] = None
    source_url: Optional[str] = None
    unsupported_reason: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)


# ----------------- CANONICAL CITY REGISTRY -----------------

CHICAGO_CITY_CONFIG = CityConfig(
    city_id="chicago",
    display_name="Chicago Metropolitan Area, Illinois, USA",
    country="United States",
    timezone="America/Chicago",
    coverage_status="SUPPORTED",
    spatial=CitySpatialConfig(
        core_bounds={"min_lat": 41.644, "max_lat": 42.023, "min_lon": -87.940, "max_lon": -87.523},
        buffer_bounds={"min_lat": 41.500, "max_lat": 42.200, "min_lon": -88.100, "max_lon": -87.300},
        spatial_unit_type="lattice",
        spatial_resolution_desc="250m regular micro-zones (CPD Precincts)",
        unit_count=20
    ),
    model=CityModelConfig(
        model_id="v4.2.1-catboost-calibrated",
        engine="CatBoost Spatio-Temporal Classifier v1.2.10",
        feature_schema_version="chicago-17-feat-v1",
        feature_columns=[
            "sector_id", "zone_key", "hour_of_day", "day_of_week", "is_weekend",
            "sin_hour", "cos_hour", "sin_day", "cos_day", "lag_1_count",
            "lag_2_count", "lag_6_count", "lag_42_count", "rolling_24h_sum",
            "rolling_7d_mean", "sector_other_zones_count", "empirical_cell_rate"
        ],
        model_artifact_path="backend/artifacts/forecaster_catboost.cbm",
        calibrator_artifact_path="backend/artifacts/calibrator.joblib",
        metadata_artifact_path="backend/artifacts/model_metadata.json",
        is_validated=True,
        operational_threshold=0.50
    ),
    data_provider_id="cpd-chicago-socrata",
    dataset_name="Chicago Police Department Incident Feed (Proxy)",
    data_source_name="City of Chicago Open Data Portal (Socrata API)",
    source_url="https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2",
    limitations=[
        "Model forecasts are calibrated using chronological out-of-time splits (CPD 2023).",
        "Extreme weather and unmonitored anomalies may alter temporal variance."
    ]
)

PUNE_CITY_CONFIG = CityConfig(
    city_id="pune",
    display_name="Pune City, Maharashtra, India",
    country="India",
    timezone="Asia/Kolkata",
    coverage_status="UNSUPPORTED",
    spatial=CitySpatialConfig(
        core_bounds={"min_lat": 18.410, "max_lat": 18.630, "min_lon": 73.740, "max_lon": 74.010},
        buffer_bounds={"min_lat": 18.350, "max_lat": 18.700, "min_lon": 73.650, "max_lon": 74.100},
        spatial_unit_type="police_station",
        spatial_resolution_desc="33 Police Station Jurisdictions (Candidate Pilot Architecture)",
        unit_count=33
    ),
    model=CityModelConfig(
        model_id=None,
        engine=None,
        feature_schema_version="pune-24-feat-candidate",
        feature_columns=[],
        model_artifact_path=None,
        calibrator_artifact_path=None,
        metadata_artifact_path=None,
        is_validated=False
    ),
    data_provider_id="pune-police-cctns-candidate",
    dataset_name="Pune City Police CCTNS (Candidate Data Partner)",
    data_source_name="Office of Commissioner of Police, Pune (Institutional Access Required)",
    source_url="https://punepolice.gov.in",
    unsupported_reason=(
        "No public machine-readable incident-level crime feed is available for Pune. "
        "A local CatBoost model has not been trained or evaluated on local ground truth. "
        "Chicago model weights are strictly non-transferable."
    ),
    limitations=[
        "Pune forecasting is disabled pending formal institutional data agreement (MoU) and local out-of-time validation.",
        "Zero synthetic or foreign model weights are permitted to generate risk scores for Pune."
    ]
)

MUMBAI_CITY_CONFIG = CityConfig(
    city_id="mumbai",
    display_name="Greater Mumbai, Maharashtra, India",
    country="India",
    timezone="Asia/Kolkata",
    coverage_status="UNSUPPORTED",
    spatial=CitySpatialConfig(
        core_bounds={"min_lat": 18.890, "max_lat": 19.280, "min_lon": 72.775, "max_lon": 72.990},
        spatial_unit_type="police_station",
        spatial_resolution_desc="94 Police Station Jurisdictions",
        unit_count=94
    ),
    model=CityModelConfig(
        model_id=None,
        is_validated=False
    ),
    data_provider_id="mumbai-data-status",
    dataset_name=None,
    data_source_name="Greater Mumbai Police",
    source_url="https://mumbaipolice.gov.in",
    unsupported_reason=(
        "No machine-readable incident-level crime stream is published for Mumbai. "
        "Cross-city model projection from Chicago is prohibited."
    ),
    limitations=[
        "Forecasting is safely disabled until localized training data is ingested and audited."
    ]
)


CITY_REGISTRY: Dict[str, CityConfig] = {
    "chicago": CHICAGO_CITY_CONFIG,
    "pune": PUNE_CITY_CONFIG,
    "mumbai": MUMBAI_CITY_CONFIG,
}


def get_city_config(city_id: str) -> Optional[CityConfig]:
    """Retrieve city configuration by city identifier."""
    return CITY_REGISTRY.get(city_id.lower().strip())


def resolve_city_by_coordinates(lat: float, lon: float) -> Optional[CityConfig]:
    """Resolve a configured city based on geographic coordinate bounds."""
    for cfg in CITY_REGISTRY.values():
        b = cfg.spatial.core_bounds
        if b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]:
            return cfg
        buf = cfg.spatial.buffer_bounds
        if buf and buf["min_lat"] <= lat <= buf["max_lat"] and buf["min_lon"] <= lon <= buf["max_lon"]:
            return cfg
    return None


def is_city_model_ready(city_id: str) -> bool:
    """Return True if and only if a validated local model exists for the city."""
    cfg = get_city_config(city_id)
    if not cfg:
        return False
    return cfg.model.is_validated and (cfg.model.model_artifact_path is not None)
