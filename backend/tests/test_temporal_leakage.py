"""
Unit tests for Temporal Leakage Prevention.
Verifies target construction, lag ordering, and chronological partitioning.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline

def test_no_future_information_in_lags():
    pipeline = SpatioTemporalDataPipeline(time_interval_hours=4)

    # Synthetic grid over 10 consecutive windows
    times = [datetime(2026, 8, 1, 0, 0) + timedelta(hours=4 * i) for i in range(10)]
    rows = []
    for i, t in enumerate(times):
        rows.append({
            "window_time": t,
            "sector_id": "zone-04",
            "zone_key": "market",
            "incident_count": i * 2, # counts: 0, 2, 4, 6, 8, 10...
            "mean_severity": 1.0,
            "sensor_witness_sum": 0
        })

    grid_df = pd.DataFrame(rows)
    feat_df = pipeline.generate_features_and_targets(grid_df)

    # For window i, target_count must be window i+1's count
    for i in range(len(feat_df) - 1):
        curr_row = feat_df.iloc[i]
        next_count = grid_df.iloc[i+1]["incident_count"]
        assert curr_row["target_count"] == next_count

        # lag_1_count must be exactly the count of window i (not i+1)
        assert curr_row["lag_1_count"] == curr_row["incident_count"]

def test_chronological_split_strict_ordering():
    pipeline = SpatioTemporalDataPipeline(time_interval_hours=4)
    times = [datetime(2026, 8, 1, 0, 0) + timedelta(hours=4 * i) for i in range(20)]
    rows = []
    for t in times:
        for s in ["zone-04", "zone-02"]:
            for z in ["market", "central"]:
                rows.append({
                    "window_time": t,
                    "sector_id": s,
                    "zone_key": z,
                    "incident_count": 1,
                    "mean_severity": 1.0,
                    "sensor_witness_sum": 0
                })

    grid_df = pd.DataFrame(rows)
    feat_df = pipeline.generate_features_and_targets(grid_df)
    train_df, val_df, test_df = pipeline.split_chronological(feat_df, train_frac=0.6, val_frac=0.2)

    # Assert max train time < min val time <= max val time < min test time
    assert train_df["window_time"].max() < val_df["window_time"].min()
    assert val_df["window_time"].max() < test_df["window_time"].min()
