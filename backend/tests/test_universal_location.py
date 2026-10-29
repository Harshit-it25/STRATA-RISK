"""
Unit and Integration Tests for Universal Location-Aware Forecasting.
Tests:
- Coordinate validation & boundary enforcement
- Location geocoding & reverse geocoding
- Timezone resolution
- Geographic coverage classification (SUPPORTED, PARTIAL_COVERAGE, INSUFFICIENT_DATA, UNSUPPORTED)
- POST /api/forecast/location endpoint (Chicago vs Mumbai vs invalid coords)
- Truthful reporting: no fake numbers or false zero-risk for unsupported cities
- Provider registry & regional coverage endpoints
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.coverage_service import (
    coverage_service,
    STATUS_SUPPORTED,
    STATUS_PARTIAL_COVERAGE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_UNSUPPORTED,
    estimate_timezone_from_coords
)
from backend.services.geocoding_service import geocoding_service
from backend.services.data_providers import provider_registry


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ============================================================================
# A. Location & Geocoding Tests
# ============================================================================

def test_coordinate_validation():
    # Valid coordinates
    valid, err = coverage_service.validate_coordinates(41.8781, -87.6298)
    assert valid is True
    assert err is None

    # Invalid latitude
    valid, err = coverage_service.validate_coordinates(95.0, 72.8777)
    assert valid is False
    assert "latitude" in err.lower()

    # Invalid longitude
    valid, err = coverage_service.validate_coordinates(19.0760, 200.0)
    assert valid is False
    assert "longitude" in err.lower()


def test_timezone_resolution():
    assert estimate_timezone_from_coords(41.8781, -87.6298) == "America/Chicago"
    assert estimate_timezone_from_coords(19.0760, 72.8777) == "Asia/Kolkata"
    assert estimate_timezone_from_coords(51.5074, -0.1278) == "Europe/London"
    assert estimate_timezone_from_coords(40.7128, -74.0060) == "America/New_York"
    assert estimate_timezone_from_coords(35.6762, 139.6503) == "Asia/Tokyo"


def test_location_search_gazetteer():
    results = geocoding_service.search_locations("Chicago", limit=5)
    assert len(results) > 0
    first = results[0]
    assert "Chicago" in first["display_name"]
    assert first["coverage_status"] == STATUS_SUPPORTED
    assert first["region_id"] == "chicago"

    mumbai_res = geocoding_service.search_locations("Mumbai", limit=5)
    assert len(mumbai_res) > 0
    m_first = mumbai_res[0]
    assert "Mumbai" in m_first["display_name"]
    assert m_first["coverage_status"] == STATUS_UNSUPPORTED
    assert m_first["timezone"] == "Asia/Kolkata"


def test_location_search_empty_and_short():
    assert geocoding_service.search_locations("") == []
    assert geocoding_service.search_locations("a") == []


def test_reverse_geocoding():
    rev = geocoding_service.reverse_geocode(41.8781, -87.6298)
    assert "Chicago" in rev["display_name"]
    assert rev["coverage_status"] == STATUS_SUPPORTED


# ============================================================================
# B. Geographic Coverage Classification Tests
# ============================================================================

def test_coverage_evaluation_chicago_supported():
    cov = coverage_service.evaluate_coverage(41.8781, -87.6298)
    assert cov["status"] == STATUS_SUPPORTED
    assert cov["region_id"] == "chicago"
    assert cov["validated_for_region"] is True
    assert cov["resolved_sector_id"] in ["zone-04", "zone-02", "zone-09", "zone-12", "zone-07"]
    assert cov["resolved_zone_key"] in ["market", "central", "riverside", "east"]
    assert cov["distance_to_centroid_km"] is not None
    assert cov["observations_available"] > 5000


def test_coverage_evaluation_chicago_buffer():
    # Outer fringe of Chicago metro
    cov = coverage_service.evaluate_coverage(41.52, -87.35)
    assert cov["status"] == STATUS_PARTIAL_COVERAGE
    assert cov["region_id"] == "chicago"
    assert cov["validated_for_region"] is False
    assert len(cov["limitations"]) > 0


def test_coverage_evaluation_mumbai_unsupported():
    cov = coverage_service.evaluate_coverage(19.0760, 72.8777)
    assert cov["status"] == STATUS_UNSUPPORTED
    assert cov["validated_for_region"] is False
    assert cov["resolved_sector_id"] is None
    assert cov["resolved_zone_key"] is None
    assert cov["distance_to_centroid_km"] is None
    assert "Chicago" in " ".join(cov["limitations"])


def test_coverage_evaluation_candidate_regions():
    london_cov = coverage_service.evaluate_coverage(51.5074, -0.1278)
    assert london_cov["status"] == STATUS_INSUFFICIENT_DATA
    assert london_cov["region_id"] == "london_uk"
    assert london_cov["validated_for_region"] is False


# ============================================================================
# C. Location-Aware Forecasting Endpoint Tests
# ============================================================================

def test_post_location_forecast_chicago(client):
    payload = {
        "latitude": 41.8781,
        "longitude": -87.6298,
        "horizon_hours": 4,
        "time": "20:00",
        "date": "Mon, Oct 24"
    }
    res = client.post("/api/forecast/location", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "supported"
    assert data["location"]["region_id"] == "chicago"
    assert data["location"]["timezone"] == "America/Chicago"
    assert data["location"]["resolved_sector_id"] is not None

    # Coverage metadata
    assert data["coverage"]["status"] == "SUPPORTED"
    assert "Chicago" in data["coverage"]["dataset_name"]
    assert data["coverage"]["observations_available"] > 0

    # Actual forecast result
    assert data["forecast"] is not None
    assert "risk_probability" in data["forecast"]
    assert 0.0 <= data["forecast"]["risk_probability"] <= 1.0
    assert data["forecast"]["risk_level"] in ["LOWER", "MODERATE", "HIGHER", "SPARSE"]
    assert data["forecast"]["calibrated"] is True
    assert "uncertainty" in data["forecast"]
    assert len(data["forecast"]["reasons"]) > 0

    # Model metadata
    assert data["model"] is not None
    assert data["model"]["validated_for_region"] is True
    assert "v4.2.1" in data["model"]["model_id"]


def test_post_location_forecast_mumbai_unsupported(client):
    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "horizon_hours": 4,
        "time": "20:00"
    }
    res = client.post("/api/forecast/location", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Honest unsupported reporting: NO fake risk score!
    assert data["status"] == "unsupported"
    assert data["coverage"]["status"] == "UNSUPPORTED"
    assert data["forecast"] is None
    assert data["model"] is None
    assert len(data["limitations"]) > 0
    assert any("Chicago" in lim for lim in data["limitations"])
    assert len(data["available_alternatives"]) > 0
    assert data["available_alternatives"][0]["region_id"] == "chicago"


def test_post_location_forecast_invalid_coordinates(client):
    # Invalid lat > 90
    res = client.post("/api/forecast/location", json={"latitude": 95.0, "longitude": 0.0})
    assert res.status_code == 422

    # Invalid lon < -180
    res = client.post("/api/forecast/location", json={"latitude": 40.0, "longitude": -190.0})
    assert res.status_code == 422


# ============================================================================
# D. Location Search and Coverage API Endpoints
# ============================================================================

def test_api_location_search(client):
    res = client.get("/api/location/search?q=Chicago&limit=3")
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    assert any(item["region_id"] == "chicago" for item in data)


def test_api_location_coverage_endpoint(client):
    res = client.get("/api/location/coverage?latitude=41.8781&longitude=-87.6298")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUPPORTED"
    assert data["region_id"] == "chicago"
    assert data["validated_model_available"] is True

    # Mumbai coverage check
    m_res = client.get("/api/location/coverage?latitude=19.0760&longitude=72.8777")
    assert m_res.status_code == 200
    m_data = m_res.json()
    assert m_data["status"] == "UNSUPPORTED"
    assert m_data["validated_model_available"] is False


def test_api_data_sources_endpoint(client):
    res = client.get("/api/data/sources")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) >= 4
    provider_ids = [s["id"] for s in sources]
    assert "chicago-cpd-socrata" in provider_ids
    assert "mumbai-data-status" in provider_ids


def test_api_regions_endpoints(client):
    res = client.get("/api/regions")
    assert res.status_code == 200
    regions = res.json()
    assert len(regions) >= 4
    region_ids = [r["region_id"] for r in regions]
    assert "chicago" in region_ids
    assert "mumbai" in region_ids

    # Detailed region coverage
    r_res = client.get("/api/regions/chicago/coverage")
    assert r_res.status_code == 200
    assert r_res.json()["has_validated_model"] is True

    # Unknown region returns 404
    bad_res = client.get("/api/regions/nonexistent_city/coverage")
    assert bad_res.status_code == 404
