"""
Geographic Coverage and Data Availability Service for Strata Risk.

Determines whether historical crime data and validated machine-learning models
exist for a given geographic location.
Never equates geocoding success with crime data availability.
Never projects Chicago predictions or centroids onto other cities.
"""

import math
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

from backend.pipeline.data_pipeline import SECTOR_METADATA, ZONE_METADATA
from backend.services.data_providers import provider_registry, ChicagoCrimeDataProvider


# Coverage status constants
STATUS_SUPPORTED = "SUPPORTED"
STATUS_PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"


# Known geographic region configurations
KNOWN_REGIONS = {
    "chicago": {
        "region_id": "chicago",
        "name": "Chicago Metropolitan Area, Illinois, USA",
        "country": "United States",
        "timezone": "America/Chicago",
        "core_bounds": {"min_lat": 41.644, "max_lat": 42.023, "min_lon": -87.940, "max_lon": -87.523},
        "buffer_bounds": {"min_lat": 41.500, "max_lat": 42.200, "min_lon": -88.100, "max_lon": -87.300},
        "has_validated_model": True,
        "model_id": "v4.2.1-catboost-calibrated",
        "engine": "CatBoost Spatio-Temporal Classifier v1.2.10",
        "dataset_name": "Chicago Police Department Incident Feed (Proxy)",
        "data_source": "City of Chicago Open Data Portal (Socrata API)",
        "source_url": "https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2",
        "historical_start": "2023-01-01T00:00:00",
        "historical_end": "2023-05-23T19:06:00",
        "observations_available": 24815,
        "spatial_lattice": "250m micro-zones (CPD Precincts)"
    },
    "new_york": {
        "region_id": "new_york",
        "name": "New York City, New York, USA",
        "country": "United States",
        "timezone": "America/New_York",
        "core_bounds": {"min_lat": 40.477, "max_lat": 40.917, "min_lon": -74.259, "max_lon": -73.700},
        "has_validated_model": False,
        "model_id": None,
        "dataset_name": "NYC Open Data (NYPD Historic Complaints)",
        "data_source": "NYC Open Data Portal",
        "status": STATUS_INSUFFICIENT_DATA,
        "observations_available": 0,
        "reason": "Candidate dataset registered, but regional CatBoost model has not been trained and calibrated for NYC spatial dynamics."
    },
    "london_uk": {
        "region_id": "london_uk",
        "name": "Greater London, United Kingdom",
        "country": "United Kingdom",
        "timezone": "Europe/London",
        "core_bounds": {"min_lat": 51.286, "max_lat": 51.691, "min_lon": -0.510, "max_lon": 0.334},
        "has_validated_model": False,
        "model_id": None,
        "dataset_name": "data.police.uk Street Crimes",
        "data_source": "UK Police Open Data API",
        "status": STATUS_INSUFFICIENT_DATA,
        "observations_available": 0,
        "reason": "UK Police open feeds publish monthly aggregates, which lacks the 4-hour temporal granularity required for operational dispatch."
    },
    "mumbai": {
        "region_id": "mumbai",
        "name": "Mumbai, Maharashtra, India",
        "country": "India",
        "timezone": "Asia/Kolkata",
        "core_bounds": {"min_lat": 18.890, "max_lat": 19.280, "min_lon": 72.775, "max_lon": 72.990},
        "has_validated_model": False,
        "model_id": None,
        "dataset_name": None,
        "data_source": None,
        "status": STATUS_UNSUPPORTED,
        "observations_available": 0,
        "reason": "No open machine-readable municipal crime incident stream is published for Mumbai. Models trained on Chicago cannot be applied without local ground truth."
    },
    "pune": {
        "region_id": "pune",
        "name": "Pune City, Maharashtra, India",
        "country": "India",
        "timezone": "Asia/Kolkata",
        "core_bounds": {"min_lat": 18.410, "max_lat": 18.630, "min_lon": 73.740, "max_lon": 74.010},
        "has_validated_model": False,
        "model_id": None,
        "dataset_name": "Pune City Police CCTNS (Candidate Data Partner)",
        "data_source": "Office of Commissioner of Police, Pune",
        "status": STATUS_UNSUPPORTED,
        "observations_available": 0,
        "reason": "No public authorized incident-level crime feed is published for Pune. Local CatBoost model has not been trained or evaluated on local ground truth."
    }
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points."""
    r = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def estimate_timezone_from_coords(lat: float, lon: float) -> str:
    """
    Estimates standard IANA timezone based on regional geographic bounds,
    falling back to standard GMT offset.
    """
    # India bounding box
    if 6.0 <= lat <= 37.0 and 68.0 <= lon <= 97.5:
        return "Asia/Kolkata"

    # US Continental timezones
    if 24.0 <= lat <= 50.0 and -125.0 <= lon <= -65.0:
        if lon > -77.0:
            return "America/New_York"  # Eastern
        elif lon > -87.0:
            return "America/Indiana/Indianapolis"
        elif lon > -90.0:
            return "America/Chicago"  # Central
        elif lon > -104.0:
            return "America/Chicago"
        elif lon > -114.0:
            return "America/Denver"  # Mountain
        else:
            return "America/Los_Angeles"  # Pacific

    # UK
    if 49.8 <= lat <= 60.8 and -8.0 <= lon <= 2.0:
        return "Europe/London"

    # Western Europe
    if 35.0 <= lat <= 70.0 and -10.0 <= lon <= 30.0:
        return "Europe/Paris"

    # Japan
    if 30.0 <= lat <= 46.0 and 128.0 <= lon <= 146.0:
        return "Asia/Tokyo"

    # Australia Eastern
    if -44.0 <= lat <= -10.0 and 140.0 <= lon <= 155.0:
        return "Australia/Sydney"

    # Fallback to UTC offset representation
    offset_hours = int(round(lon / 15.0))
    if offset_hours == 0:
        return "UTC"
    return f"Etc/GMT{'+' if offset_hours < 0 else '-'}{abs(offset_hours)}"


class GeographicCoverageService:
    """Service to evaluate coordinate validity, coverage status, and model readiness."""

    def __init__(self):
        self.chicago_provider = ChicagoCrimeDataProvider()

    def validate_coordinates(self, lat: float, lon: float) -> Tuple[bool, Optional[str]]:
        """Validate geographic coordinate ranges."""
        if not (-90.0 <= lat <= 90.0):
            return False, f"Invalid latitude {lat}. Latitude must be between -90 and 90 degrees."
        if not (-180.0 <= lon <= 180.0):
            return False, f"Invalid longitude {lon}. Longitude must be between -180 and 180 degrees."
        return True, None

    def evaluate_coverage(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Evaluates coverage status for coordinates.
        Returns:
            - status: SUPPORTED | PARTIAL_COVERAGE | INSUFFICIENT_DATA | UNSUPPORTED
            - region_id: e.g. "chicago" or None
            - details: dict with dataset, model, and limitation information
        """
        valid, err = self.validate_coordinates(lat, lon)
        if not valid:
            raise ValueError(err)

        tz = estimate_timezone_from_coords(lat, lon)
        chi_cfg = KNOWN_REGIONS["chicago"]
        core_b = chi_cfg["core_bounds"]
        buf_b = chi_cfg["buffer_bounds"]

        # Check Chicago Core bounds
        if core_b["min_lat"] <= lat <= core_b["max_lat"] and core_b["min_lon"] <= lon <= core_b["max_lon"]:
            # Inside fully supported Chicago area
            sector_id, zone_key, dist_km = self.resolve_closest_chicago_sector(lat, lon)
            sec_meta = SECTOR_METADATA[sector_id]
            return {
                "status": STATUS_SUPPORTED,
                "region_id": "chicago",
                "region_name": chi_cfg["name"],
                "timezone": "America/Chicago",
                "dataset_name": chi_cfg["dataset_name"],
                "data_source": chi_cfg["data_source"],
                "source_url": chi_cfg["source_url"],
                "historical_start": chi_cfg["historical_start"],
                "historical_end": chi_cfg["historical_end"],
                "observations_available": self.chicago_provider.get_record_count(),
                "spatial_resolution": "250m regular lattice",
                "resolved_sector_id": sector_id,
                "resolved_sector_name": sec_meta["name"],
                "resolved_zone_key": zone_key,
                "distance_to_centroid_km": round(dist_km, 2),
                "model_id": chi_cfg["model_id"],
                "model_engine": chi_cfg["engine"],
                "validated_for_region": True,
                "limitations": [
                    "Model forecasts are calibrated using chronological out-of-time splits (CPD 2023).",
                    "Extreme weather and unmonitored anomalies may alter temporal variance."
                ]
            }

        # Check Chicago Buffer bounds (Partial coverage)
        if buf_b["min_lat"] <= lat <= buf_b["max_lat"] and buf_b["min_lon"] <= lon <= buf_b["max_lon"]:
            sector_id, zone_key, dist_km = self.resolve_closest_chicago_sector(lat, lon)
            sec_meta = SECTOR_METADATA[sector_id]
            return {
                "status": STATUS_PARTIAL_COVERAGE,
                "region_id": "chicago",
                "region_name": "Chicago Outer Metro Fringe (Buffer Zone)",
                "timezone": "America/Chicago",
                "dataset_name": chi_cfg["dataset_name"],
                "data_source": chi_cfg["data_source"],
                "source_url": chi_cfg["source_url"],
                "historical_start": chi_cfg["historical_start"],
                "historical_end": chi_cfg["historical_end"],
                "observations_available": self.chicago_provider.get_record_count(),
                "spatial_resolution": "250m regular lattice (degraded boundary confidence)",
                "resolved_sector_id": sector_id,
                "resolved_sector_name": sec_meta["name"],
                "resolved_zone_key": zone_key,
                "distance_to_centroid_km": round(dist_km, 2),
                "model_id": chi_cfg["model_id"],
                "model_engine": chi_cfg["engine"],
                "validated_for_region": False,
                "limitations": [
                    "Coordinates fall in the outer metropolitan buffer outside core municipal precincts.",
                    "Spatial density confidence is degraded; operational predictions may exhibit higher variance."
                ]
            }

        # Check known candidate regions with insufficient data or unsupported models
        for reg_id, reg in KNOWN_REGIONS.items():
            if reg_id == "chicago":
                continue
            b = reg.get("core_bounds", {})
            if b.get("min_lat", 999) <= lat <= b.get("max_lat", -999) and b.get("min_lon", 999) <= lon <= b.get("max_lon", -999):
                status = reg.get("status", STATUS_UNSUPPORTED)
                return {
                    "status": status,
                    "region_id": reg["region_id"],
                    "region_name": reg["name"],
                    "timezone": reg["timezone"],
                    "dataset_name": reg.get("dataset_name"),
                    "data_source": reg.get("data_source"),
                    "source_url": reg.get("source_url"),
                    "historical_start": None,
                    "historical_end": None,
                    "observations_available": 0,
                    "spatial_resolution": None,
                    "resolved_sector_id": None,
                    "resolved_sector_name": None,
                    "resolved_zone_key": None,
                    "distance_to_centroid_km": None,
                    "model_id": None,
                    "model_engine": None,
                    "validated_for_region": False,
                    "limitations": [
                        reg.get("reason", "No validated predictive model exists for this region."),
                        "Strata Risk strictly prohibits cross-regional model extrapolation without localized chronological training."
                    ]
                }

        # Completely unsupported geographic area (e.g. Mumbai, Tokyo, Sydney, anywhere else)
        return {
            "status": STATUS_UNSUPPORTED,
            "region_id": None,
            "region_name": f"Coordinates ({lat:.4f}, {lon:.4f})",
            "timezone": tz,
            "dataset_name": None,
            "data_source": None,
            "source_url": None,
            "historical_start": None,
            "historical_end": None,
            "observations_available": 0,
            "spatial_resolution": None,
            "resolved_sector_id": None,
            "resolved_sector_name": None,
            "resolved_zone_key": None,
            "distance_to_centroid_km": None,
            "model_id": None,
            "model_engine": None,
            "validated_for_region": False,
            "limitations": [
                f"No verified public crime incident feed is currently integrated for these coordinates ({lat:.4f}, {lon:.4f}).",
                "The active CatBoost model is calibrated exclusively on Chicago spatio-temporal dynamics.",
                "Predictions are disabled for unvalidated regions to prevent algorithmic bias or miscalibrated dispatch."
            ]
        }

    def resolve_closest_chicago_sector(self, lat: float, lon: float) -> Tuple[str, str, float]:
        """
        Finds the nearest Chicago sector centroid and assigns the most appropriate zone.
        Only called when coordinates are confirmed to be in Chicago bounds.
        """
        best_sector = "zone-04"
        min_dist = float("inf")

        for sec_id, meta in SECTOR_METADATA.items():
            dist = haversine_km(lat, lon, meta["center_lat"], meta["center_lon"])
            if dist < min_dist:
                min_dist = dist
                best_sector = sec_id

        # Determine zone key based on quadrant relative to sector centroid
        sec_meta = SECTOR_METADATA[best_sector]
        d_lat = lat - sec_meta["center_lat"]
        d_lon = lon - sec_meta["center_lon"]

        if d_lat >= 0 and d_lon <= 0:
            best_zone = "market"
        elif d_lat >= 0 and d_lon > 0:
            best_zone = "central"
        elif d_lat < 0 and d_lon <= 0:
            best_zone = "riverside"
        else:
            best_zone = "east"

        return best_sector, best_zone, min_dist

    def list_regions(self) -> List[Dict[str, Any]]:
        """List all registered regions and their capability."""
        regions = []
        for reg_id, reg in KNOWN_REGIONS.items():
            is_supported = reg_id == "chicago"
            cb = reg.get("core_bounds", {})
            regions.append({
                "region_id": reg_id,
                "name": reg["name"],
                "country": reg["country"],
                "center_lat": round((cb.get("min_lat", 0) + cb.get("max_lat", 0)) / 2.0, 4),
                "center_lon": round((cb.get("min_lon", 0) + cb.get("max_lon", 0)) / 2.0, 4),
                "bounding_box": cb,
                "coverage_status": STATUS_SUPPORTED if is_supported else reg.get("status", STATUS_UNSUPPORTED),
                "has_validated_model": is_supported,
                "dataset_provider": reg.get("data_source") or "None integrated",
                "sensor_lattice_type": reg.get("spatial_lattice") or "N/A"
            })
        return regions


# Singleton instance
coverage_service = GeographicCoverageService()
