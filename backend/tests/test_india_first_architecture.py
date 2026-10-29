"""
Test Suite for India-First Architecture and Multi-City Operational Safety.

Verifies:
1. Chicago continues using the existing validated model and calibrator.
2. Pune remains explicitly unsupported without a locally trained and validated model.
3. Missing city configuration cannot trigger a default Chicago prediction for Pune.
4. Unknown cities cannot receive fabricated forecasts.
5. Model and calibrator routing remains city-specific via CityConfig.
6. Pune Data Readiness interface reports truthful missing prerequisites.
7. PII checks and IPC/BNS category mappings function correctly.
"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.city_config import (
    CITY_REGISTRY,
    CHICAGO_CITY_CONFIG,
    PUNE_CITY_CONFIG,
    get_city_config,
    resolve_city_by_coordinates,
    is_city_model_ready
)
from backend.services.coverage_service import coverage_service, STATUS_SUPPORTED, STATUS_UNSUPPORTED
from backend.services.forecasting_service import ForecastingService
from backend.services.pune_data_readiness import PuneDataReadinessAudit, PUNE_POLICE_STATIONS


@pytest.fixture
def client():
    return TestClient(app)


# 1. Chicago Production Parity Tests
def test_chicago_continues_using_existing_model(client):
    """Verify Chicago continues serving real predictions using the validated model."""
    req_payload = {
        "latitude": 41.8781,
        "longitude": -87.6298,
        "horizon_hours": 4,
        "time": "20:00",
        "date": "Mon, Oct 24"
    }
    res = client.post("/api/forecast/location", json=req_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "supported"
    assert data["location"]["region_id"] == "chicago"
    assert data["forecast"] is not None
    prob = data["forecast"]["risk_probability"]
    assert prob is not None
    assert 0.0 <= prob <= 1.0
    assert data["model"]["model_id"] == "v4.2.1-catboost-calibrated"
    assert data["model"]["validated_for_region"] is True


# 2. Pune Unsupported Gating Tests
def test_pune_remains_unsupported_without_validated_model(client):
    """Verify Pune location requests return a structured unsupported response with null probability."""
    pune_coords = {"latitude": 18.5204, "longitude": 73.8567}
    res = client.post("/api/forecast/location", json={**pune_coords, "horizon_hours": 4})
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "unsupported"
    assert data["location"]["region_id"] == "pune"
    assert data["location"]["timezone"] == "Asia/Kolkata"
    # Crucial safety check: No fabricated probability or risk score!
    assert data["forecast"] is None
    assert data["model"] is None
    assert any("Pune" in lim for lim in data["limitations"])


def test_pune_location_coverage_api(client):
    """Verify location coverage endpoint correctly identifies Pune as UNSUPPORTED."""
    res = client.get("/api/location/coverage?latitude=18.5204&longitude=73.8567")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "UNSUPPORTED"
    assert data["region_id"] == "pune"
    assert data["validated_model_available"] is False
    assert "Pune" in data["region_name"]


def test_pune_location_search_gazetteer(client):
    """Verify search endpoint allows locating Pune without falsely enabling forecasting."""
    res = client.get("/api/location/search?q=pune&limit=5")
    assert res.status_code == 200
    results = res.json()

    assert len(results) > 0
    pune_match = next((r for r in results if "Pune" in r["display_name"]), None)
    assert pune_match is not None
    assert pune_match["region_id"] == "pune"
    assert pune_match["coverage_status"] == "UNSUPPORTED"


# 3. Model Isolation & Cross-City Leakage Prevention
def test_missing_city_config_cannot_trigger_chicago_default_for_pune():
    """Verify Pune coordinates cannot borrow Chicago sectors or Chicago model weights."""
    cov = coverage_service.evaluate_coverage(18.5204, 73.8567)
    assert cov["status"] == STATUS_UNSUPPORTED
    assert cov["region_id"] == "pune"
    assert cov["resolved_sector_id"] is None
    assert cov["resolved_zone_key"] is None
    assert cov["validated_for_region"] is False


def test_unknown_cities_cannot_receive_fabricated_forecasts(client):
    """Verify arbitrary global coordinates safely return unsupported with null forecasts."""
    unknown_locations = [
        {"lat": 21.1458, "lon": 79.0882, "name": "Nagpur"},
        {"lat": 52.5200, "lon": 13.4050, "name": "Berlin"},
        {"lat": 0.0, "lon": 0.0, "name": "Atlantic Ocean"}
    ]
    for loc in unknown_locations:
        res = client.post("/api/forecast/location", json={"latitude": loc["lat"], "longitude": loc["lon"]})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "unsupported"
        assert data["forecast"] is None
        assert data["model"] is None


# 4. City Configuration Registry Verification
def test_city_config_registry_abstraction():
    """Verify CityConfig abstraction cleanly separates city parameters and model availability."""
    assert "chicago" in CITY_REGISTRY
    assert "pune" in CITY_REGISTRY

    chi = get_city_config("chicago")
    assert chi is not None
    assert chi.model.is_validated is True
    assert len(chi.model.feature_columns) == 17
    assert is_city_model_ready("chicago") is True

    pune = get_city_config("pune")
    assert pune is not None
    assert pune.model.is_validated is False
    assert pune.model.model_id is None
    assert is_city_model_ready("pune") is False

    # Check coordinate bounds resolution
    resolved_chi = resolve_city_by_coordinates(41.8781, -87.6298)
    assert resolved_chi is not None
    assert resolved_chi.city_id == "chicago"

    resolved_pune = resolve_city_by_coordinates(18.5204, 73.8567)
    assert resolved_pune is not None
    assert resolved_pune.city_id == "pune"


# 5. Pune Data Readiness Interface & Schema Governance
def test_pune_data_readiness_audit_reports_truthful_missing_requirements():
    """Verify assess_readiness correctly reports unacquired data and required steps."""
    audit = PuneDataReadinessAudit.assess_readiness(dataset_path=None)
    assert audit["city_id"] == "pune"
    assert audit["is_ready_for_training"] is False
    assert audit["is_ready_for_eda"] is False
    assert audit["readiness_status"] in ["NO_DATA", "INSUFFICIENT_DATA"]
    assert audit["gate_status"] == "NO_DATA"
    assert audit["data_acquired"] is False
    assert len(audit["missing_requirements"]) >= 4
    assert any("MoU" in req for req in audit["missing_requirements"])
    assert any("CCTNS" in req for req in audit["missing_requirements"])


def test_pune_schema_validator_catches_pii_and_missing_columns():
    """Verify schema auditor catches missing columns and rejects citizen PII."""
    # Test missing columns
    bad_df = pd.DataFrame([{"fir_number_hash": "123", "section_code": "392"}])
    valid, errors = PuneDataReadinessAudit.validate_dataset_schema(bad_df)
    assert valid is False
    assert any("police_station_id" in err for err in errors)

    # Test PII detection
    pii_df = pd.DataFrame([{
        "fir_number_hash": "123",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392",
        "victim_name": "Private Citizen"  # Prohibited!
    }])
    pii_safe, violations = PuneDataReadinessAudit.check_for_prohibited_pii(pii_df)
    assert pii_safe is False
    assert any("victim_name" in v for v in violations)


def test_pune_category_mapper_and_temporal_split():
    """Verify IPC/BNS category mapping and chronological non-overlapping splitting."""
    sections = pd.Series(["392", "457", "302", "unknown_123"])
    mapped = PuneDataReadinessAudit.map_incident_categories(sections)
    assert mapped.iloc[0] == "violent_street_harm"
    assert mapped.iloc[1] == "property_harm"
    assert mapped.iloc[2] == "violent_street_harm"
    assert mapped.iloc[3] == "other_cognizable"

    # Test chronological splitting without lookahead
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    sample_df = pd.DataFrame({
        "incident_datetime": dates,
        "fir_number_hash": [f"hash_{i}" for i in range(100)]
    })
    split_res = PuneDataReadinessAudit.check_temporal_leakage_and_split(sample_df)
    assert split_res["valid_split"] is True
    assert split_res["zero_lookahead_verified"] is True
