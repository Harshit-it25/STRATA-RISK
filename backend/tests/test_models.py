"""
Unit tests for Models: Baselines and CatBoost Forecaster.
"""

import pytest
import numpy as np
import pandas as pd
from backend.models.baselines import HistoricalSpatialBaseline, TemporalCyclicalBaseline
from backend.models.forecasting_engine import SpatioTemporalForecaster

@pytest.fixture
def dummy_train_df():
    data = {
        "sector_id": ["zone-04"] * 10 + ["zone-02"] * 10,
        "zone_key": ["market"] * 5 + ["central"] * 5 + ["market"] * 5 + ["central"] * 5,
        "hour_of_day": [8, 12, 16, 20, 0] * 4,
        "is_weekend": [0, 0, 1, 1, 0] * 4,
        "lag_1_count": [1, 2, 3, 4, 1] * 4,
        "lag_2_count": [1, 1, 2, 3, 1] * 4,
        "lag_6_count": [0, 1, 1, 2, 0] * 4,
        "lag_42_count": [0, 0, 1, 1, 0] * 4,
        "rolling_24h_sum": [4, 5, 8, 9, 3] * 4,
        "rolling_7d_mean": [0.5, 0.6, 0.8, 0.9, 0.4] * 4,
        "sector_other_zones_count": [1.0] * 20,
        "empirical_cell_rate": [0.4] * 20,
        "day_of_week": [1] * 20,
        "sin_hour": [0.5] * 20,
        "cos_hour": [0.5] * 20,
        "sin_day": [0.5] * 20,
        "cos_day": [0.5] * 20,
        "target_event": [0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0]
    }
    return pd.DataFrame(data)

def test_spatial_baseline_fitting_and_prediction(dummy_train_df):
    model = HistoricalSpatialBaseline(prior_weight=2.0)
    model.fit(dummy_train_df)
    preds = model.predict_proba(dummy_train_df)
    assert len(preds) == len(dummy_train_df)
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)

def test_temporal_baseline_fitting_and_prediction(dummy_train_df):
    model = TemporalCyclicalBaseline(prior_weight=2.0)
    model.fit(dummy_train_df)
    preds = model.predict_proba(dummy_train_df)
    assert len(preds) == len(dummy_train_df)
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)

def test_catboost_forecaster_fit_and_predict(dummy_train_df):
    feature_cols = [c for c in dummy_train_df.columns if c not in ["target_event"]]
    forecaster = SpatioTemporalForecaster(iterations=20, learning_rate=0.1, depth=3)
    forecaster.fit(dummy_train_df, dummy_train_df, feature_cols=feature_cols)

    probs = forecaster.predict_proba(dummy_train_df)
    assert len(probs) == len(dummy_train_df)
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)

    importances = forecaster.get_feature_importances()
    assert len(importances) > 0
