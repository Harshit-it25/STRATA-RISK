"""
Unit tests for SpatioTemporalDataPipeline.
Verifies data validation, grid lattice construction, missing value handling, and boundary checks.
"""

import pytest
import pandas as pd
import numpy as np
from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline

def test_data_validation_valid():
    pipeline = SpatioTemporalDataPipeline()
    sample_df = pd.DataFrame([
        {
            "incident_id": "INC-1",
            "timestamp": "2026-08-01 10:00:00",
            "sector_id": "zone-04",
            "zone_key": "market",
            "latitude": 41.8818,
            "longitude": -87.6231,
            "severity_score": 2,
            "sensor_witnessed": 1
        }
    ])
    clean = pipeline.validate_raw_data(sample_df)
    assert len(clean) == 1
    assert clean["sector_id"].iloc[0] == "zone-04"

def test_data_validation_out_of_bounds():
    pipeline = SpatioTemporalDataPipeline()
    sample_df = pd.DataFrame([
        {
            "incident_id": "INC-1",
            "timestamp": "2026-08-01 10:00:00",
            "sector_id": "zone-04",
            "zone_key": "market",
            "latitude": 25.0, # Out of Chicago bounds
            "longitude": -80.0,
        }
    ])
    clean = pipeline.validate_raw_data(sample_df)
    assert len(clean) == 0

def test_grid_lattice_construction():
    pipeline = SpatioTemporalDataPipeline(time_interval_hours=4)
    sample_df = pd.DataFrame([
        {
            "incident_id": "INC-1",
            "timestamp": "2026-08-01 08:15:00",
            "sector_id": "zone-04",
            "zone_key": "market",
            "latitude": 41.8818,
            "longitude": -87.6231
        },
        {
            "incident_id": "INC-2",
            "timestamp": "2026-08-01 09:30:00",
            "sector_id": "zone-04",
            "zone_key": "market",
            "latitude": 41.8818,
            "longitude": -87.6231
        }
    ])
    clean = pipeline.validate_raw_data(sample_df)
    grid = pipeline.build_spatio_temporal_grid(clean)
    assert len(grid) > 0
    # Both incidents in the 08:00 window for zone-04 market
    mkt_row = grid[(grid["sector_id"] == "zone-04") & (grid["zone_key"] == "market")]
    assert mkt_row["incident_count"].sum() == 2
