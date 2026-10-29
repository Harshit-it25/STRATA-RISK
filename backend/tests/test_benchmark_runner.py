"""
Unit tests for multi-model benchmark evaluation and rolling-origin walk-forward splits.
"""

import pytest
import numpy as np
import pandas as pd
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.models.baselines import HistoricalSpatialBaseline, TemporalCyclicalBaseline

def test_stratified_slices():
    runner = BenchmarkRunner()
    test_df = pd.DataFrame({
        "sector_id": ["zone-04"] * 6 + ["zone-02"] * 6,
        "zone_key": ["market", "central", "riverside", "east", "market", "central"] * 2,
        "hour_of_day": [8, 12, 16, 20, 0, 4] * 2,
        "target_event": [0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0]
    })

    class DummyModel:
        def predict_proba(self, df):
            return np.linspace(0.2, 0.8, len(df))

    dummy = DummyModel()
    slices = runner.compute_stratified_slices(test_df, dummy, dummy, dummy)

    assert "by_sector" in slices
    assert "by_time_period" in slices
    assert "by_data_sufficiency" in slices
    assert "zone-04" in slices["by_sector"]
    assert "zone-02" in slices["by_sector"]
