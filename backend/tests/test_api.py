"""
Integration and Schema Compatibility tests for FastAPI endpoints.
Tests:
- GET /health
- GET /api/forecast
- GET /api/map
- GET /api/model/health
- GET /api/validation
- Invalid query inputs
- Sparse zone behavior
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert "timestamp" in data
    assert "service" in data

def test_forecast_endpoint_default(client):
    res = client.get("/api/forecast?sector_id=zone-04&time=20:00&date=Mon, Oct 24")
    assert res.status_code == 200
    data = res.json()
    assert data["sector_id"] == "zone-04"
    assert "status_overview" in data
    assert "time_step" in data
    assert "timeline" in data
    assert len(data["timeline"]) == 5

    # Check required micro-zones
    zones = data["time_step"]["zones"]
    for zk in ["market", "central", "riverside", "east"]:
        assert zk in zones
        assert "score" in zones[zk]
        assert "level" in zones[zk]
        assert "delta" in zones[zk]
        assert "trend" in zones[zk]
        assert "reasons" in zones[zk]
        assert isinstance(zones[zk]["reasons"], list)

def test_forecast_sparse_zone_behavior(client):
    # zone-12 is the industrial sparse sector
    res = client.get("/api/forecast?sector_id=zone-12&time=08:00")
    assert res.status_code == 200
    data = res.json()
    assert data["sector_id"] == "zone-12"
    east_zone = data["time_step"]["zones"]["east"]
    assert east_zone["level"] == "Sparse"
    assert east_zone["score"] == "--"

def test_forecast_invalid_input_fallback(client):
    # Non-existent sector ID should safely fallback or handle gracefully
    res = client.get("/api/forecast?sector_id=zone-invalid&time=99:99")
    assert res.status_code == 200
    data = res.json()
    assert "time_step" in data

def test_map_endpoint(client):
    res = client.get("/api/map?sector_id=zone-04&time=20:00")
    assert res.status_code == 200
    data = res.json()
    assert "coordinate_bounds" in data
    assert "cell_resolution" in data
    assert "zones" in data
    assert "heatmap_centers" in data
    assert len(data["heatmap_centers"]) > 0
    assert "arteries" in data

def test_model_health_endpoint(client):
    res = client.get("/api/model/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "engine" in data
    assert "model_version" in data
    assert "records_ingested_total" in data

def test_validation_endpoint(client):
    res = client.get("/api/validation")
    assert res.status_code == 200
    data = res.json()
    assert "validation_status" in data
    if data["validation_status"] == "completed":
        assert "brier_score" in data
        assert "roc_auc" in data
        assert "calibration_slope" in data
        assert "personal_identity_ingestion" in data
        assert data["personal_identity_ingestion"] == "0.00%"
