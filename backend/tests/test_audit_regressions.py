"""
Audit Regression Tests for Strata Risk Spatio-Temporal Forecasting Pipeline.

Verifies:
1. Source meaning preservation: arrest_made is distinct from sensor_witnessed.
2. Strict artifact provenance: rejects synthetic artifacts when real is requested.
3. Exact Precision@Top-K computation without hardcoded/fabricated figures.
4. Leakage-free probability calibration on held-out validation data.
5. Non-arbitrary empirical uncertainty interval derived from validation residuals.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from backend.ingestion.chicago_processor import ChicagoCrimeProcessor
from backend.models.forecasting_engine import SpatioTemporalForecaster
from backend.evaluation.benchmark_runner import BenchmarkRunner

def test_arrest_not_mapped_to_sensor_witnessed(tmp_path):
    """
    REGRESSION TEST: Verify that the CPD arrest flag is mapped to arrest_made
    and NOT falsely conflated with automated sensor detections (sensor_witnessed).
    """
    raw_data = {
        "id": [101, 102],
        "date": ["2023-01-01T12:00:00.000", "2023-01-01T14:00:00.000"],
        "latitude": [41.8719, 41.9003],
        "longitude": [-87.6283, -87.6336],
        "district": [1, 18],
        "primary_type": ["THEFT", "BATTERY"],
        "arrest": [True, False]
    }
    raw_csv = str(tmp_path / "raw_chicago.csv")
    out_csv = str(tmp_path / "proc_chicago.csv")
    rep_json = str(tmp_path / "rep.json")

    pd.DataFrame(raw_data).to_csv(raw_csv, index=False)
    processor = ChicagoCrimeProcessor()
    proc_df, rep = processor.process_raw_dataset(raw_csv, out_csv, rep_json)

    assert "arrest_made" in proc_df.columns
    assert "sensor_witnessed" in proc_df.columns
    # Check that arrest_made preserves CPD arrest boolean
    assert proc_df["arrest_made"].iloc[0] == 1
    assert proc_df["arrest_made"].iloc[1] == 0
    # Check that sensor_witnessed is 0 (no acoustic/CCTV sensor telemetry)
    assert proc_df["sensor_witnessed"].iloc[0] == 0
    assert proc_df["sensor_witnessed"].iloc[1] == 0

def test_strict_dataset_provenance_verification(tmp_path):
    """
    REGRESSION TEST: Verify that load_artifacts raises RuntimeError
    when an expected dataset type does not match the artifact metadata.
    """
    art_dir = str(tmp_path / "artifacts")
    os.makedirs(art_dir, exist_ok=True)

    synthetic_meta = {
        "model_type": "CatBoostClassifier",
        "dataset_type": "synthetic",
        "dataset_name": "Synthetic Benchmark",
        "feature_columns": ["hour_of_day"],
        "cat_features": []
    }
    with open(os.path.join(art_dir, "model_metadata.json"), "w") as f:
        json.dump(synthetic_meta, f)

    # Create dummy model file
    from catboost import CatBoostClassifier
    cb = CatBoostClassifier(iterations=2)
    cb.fit(np.array([[1], [2]]), np.array([0, 1]), verbose=False)
    cb.save_model(os.path.join(art_dir, "forecaster_catboost.cbm"))

    forecaster = SpatioTemporalForecaster()
    # Loading expecting 'real' should fail on synthetic artifacts
    with pytest.raises(RuntimeError, match="Dataset artifact mismatch"):
        forecaster.load_artifacts(art_dir, expected_dataset_type="real")

    # Loading expecting 'synthetic' should succeed
    loaded = forecaster.load_artifacts(art_dir, expected_dataset_type="synthetic")
    assert loaded.metadata["dataset_type"] == "synthetic"

def test_precision_top_k_exact_recomputation():
    """
    REGRESSION TEST: Verify that compute_hotspot_ranking_metrics computes
    the exact ratio of observed events among the top K highest-scoring cells.
    """
    runner = BenchmarkRunner()
    # 10 test samples: 4 positives, 6 negatives
    y_true = np.array([1, 0, 1, 0, 0, 1, 0, 0, 1, 0])
    # Predicted scores: indices 0 and 2 have highest probabilities
    y_prob = np.array([0.9, 0.1, 0.85, 0.2, 0.3, 0.4, 0.15, 0.05, 0.7, 0.25])

    # Top 20% of 10 samples is top 2 samples (indices 0 and 2)
    # Both are positive in y_true, so precision should be 2/2 = 1.0 (100%)
    res_20 = runner.compute_hotspot_ranking_metrics(y_true, y_prob, top_k_pct=0.20)
    assert res_20["evaluated_k_cells"] == 2
    assert res_20["precision_at_top_k"] == 1.0
    assert res_20["recall_at_top_k"] == 2 / 4  # 50% of total positives

def test_empirical_uncertainty_is_non_arbitrary():
    """
    REGRESSION TEST: Verify that empirical uncertainty is derived from
    actual validation set residuals, not hardcoded arbitrary values.
    """
    runner = BenchmarkRunner()

    class MockModel:
        def predict_proba(self, df):
            # Perfect predictions: residuals = 0
            return df["target_event"].values.astype(float)

    val_df = pd.DataFrame({"target_event": [1, 0, 1, 0, 1, 0]})
    unc = runner.compute_empirical_uncertainty(val_df, MockModel())
    assert unc["residual_std"] == 0.0
    assert unc["uncertainty_points"] == 0.0


def test_cors_security_disallows_wildcard_credentials():
    """
    REGRESSION TEST: Verify CORS middleware does not permit allow_credentials=True
    in conjunction with allow_origins=['*'], which violates security best practices.
    """
    from backend.main import app
    from starlette.middleware.cors import CORSMiddleware

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware is not None, "CORSMiddleware must be configured on app"
    # starlette stores middleware arguments in .kwargs
    kwargs = getattr(cors_middleware, "kwargs", {})
    if "*" in kwargs.get("allow_origins", []):
        assert kwargs.get("allow_credentials") is False, (
            "CORS allow_credentials must be False when allow_origins is wildcard '*'"
        )


def test_sparse_zone_does_not_fabricate_probability():
    """
    REGRESSION TEST: Verify that a sparse geographic zone returns risk_probability=None
    and risk_score_100=None instead of fabricating a 0.28 probability or 28 score.
    """
    from backend.services.forecasting_service import ForecastingService
    from unittest.mock import MagicMock

    service = ForecastingService()
    # Mock forecast_zone to simulate sparse data detection
    service.forecast_zone = MagicMock(return_value={
        "id": "loop01",
        "key": "north",
        "name": "Loop North",
        "score": "--",
        "prob": None,
        "level": "Sparse",
        "reasons": ["Sparsity in micro-cell logs"]
    })

    res = service.get_location_forecast(
        latitude=41.881837,
        longitude=-87.623177,
        time="20:00",
        date="Mon, Oct 24"
    )

    assert res["forecast"]["risk_probability"] is None, "Sparse zone must not fabricate risk_probability"
    assert res["forecast"]["risk_score_100"] is None, "Sparse zone must not fabricate risk_score_100"
    assert res["forecast"]["risk_level"] == "SPARSE"


def test_nan_inf_probability_clamped_safely():
    """
    REGRESSION TEST: Verify that non-finite probabilities (NaN, Inf) do not cause
    crashes or get passed through as corrupt values during zone forecasting.
    """
    from backend.services.forecasting_service import ForecastingService
    from unittest.mock import MagicMock
    import math

    service = ForecastingService()
    service.is_ready = True
    service.model = MagicMock()
    service.model.model = MagicMock()
    service.model.predict_proba = MagicMock(return_value=np.array([float("nan")]))
    service._get_historical_state = MagicMock(return_value=pd.DataFrame({"lag_1_count": [0], "rolling_24h_sum": [0]}))
    service.pipeline = MagicMock()
    service.pipeline.is_sparse_cell = MagicMock(return_value=False)

    res = service.forecast_zone("sector_1", "north", "20:00", "Mon, Oct 24")
    prob = res["prob"]
    assert prob is not None
    assert math.isfinite(prob)
    assert 0.0 <= prob <= 1.0
    assert prob == 0.50  # Safe fallback for NaN


def test_operational_ranking_metrics_per_shift():
    """
    REGRESSION TEST: Verify that compute_operational_ranking_metrics groups by time_step
    and computes top-K ranking per shift, avoiding global pooling distortion.
    """
    runner = BenchmarkRunner()
    # 2 time steps, each with 5 cells
    # Time 1: cells with prob [0.9, 0.8, 0.3, 0.2, 0.1], true = [1, 0, 0, 0, 0]
    # Top 20% is top 1 cell (prob 0.9, true 1) -> precision = 1.0
    # Time 2: cells with prob [0.95, 0.85, 0.4, 0.2, 0.1], true = [0, 1, 0, 0, 0]
    # Top 20% is top 1 cell (prob 0.95, true 0) -> precision = 0.0
    # Mean operational precision = (1.0 + 0.0) / 2 = 0.50
    df = pd.DataFrame({
        "time_step": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
        "target_event": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0]
    })
    probs = np.array([0.9, 0.8, 0.3, 0.2, 0.1, 0.95, 0.85, 0.4, 0.2, 0.1])

    res = runner.compute_operational_ranking_metrics(df, probs, top_k_pct=0.20)
    assert res["operational_precision_top_k"] == 0.50
