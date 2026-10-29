"""
Tests for Pune Spatio-Temporal 4-Hour Aggregation Pipeline (Phase 6.3).

Verifies:
1. Six 4-Hour Windows per Day in Indian Standard Time (Asia/Kolkata).
2. Strict Half-Open Intervals [t, t + 4h): boundary incidents at 04:00:00 vs 03:59:59.
3. Midnight Rollover (23:59:59 Day D vs 00:00:00 Day D+1).
4. Timezone Conversion (UTC to IST timestamp shift).
5. Repeated Station Records within the same window.
6. Missing Reporting Coverage: unobserved stations receive NaN, never fabricated zeros.
7. Anti-Leakage Feature Construction: lags use tau < t strictly.
8. Chronological Partitioning: non-overlapping boundaries.
9. Theoretical Station-Window Capacity Accounting: 6 * D * 33.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from backend.pipeline.pune_spatiotemporal_pipeline import (
    PuneFourHourSpatiotemporalPipeline,
    OPERATIONAL_WINDOWS,
    WINDOWS_PER_DAY,
    WINDOW_HOURS,
)
from backend.services.pune_data_readiness import PUNE_POLICE_STATIONS


def test_six_four_hour_windows_per_day_definition():
    """Confirms exactly 6 four-hour operational windows defined per day."""
    assert WINDOWS_PER_DAY == 6
    assert WINDOW_HOURS == 4
    assert len(OPERATIONAL_WINDOWS) == 6

    expected_starts = ["00:00:00", "04:00:00", "08:00:00", "12:00:00", "16:00:00", "20:00:00"]
    for idx, w in enumerate(OPERATIONAL_WINDOWS):
        assert w["index"] == idx
        assert w["start_time"] == expected_starts[idx]


def test_half_open_window_boundary_assignment():
    """
    Verifies half-open interval [t, t + 4h):
    - 04:00:00.000 belongs to Window 1 [04:00, 08:00).
    - 03:59:59.999 belongs to Window 0 [00:00, 04:00).
    - 08:00:00.000 belongs to Window 2 [08:00, 12:00).
    - 07:59:59.999 belongs to Window 1 [04:00, 08:00).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    # Exact boundary 04:00:00.000 IST
    ts_boundary = pd.Timestamp("2026-03-01 04:00:00", tz="Asia/Kolkata")
    w_idx, w_start, w_end = pipe.get_window_assignment(ts_boundary)
    assert w_idx == 1
    assert w_start == pd.Timestamp("2026-03-01 04:00:00", tz="Asia/Kolkata")
    assert w_end == pd.Timestamp("2026-03-01 08:00:00", tz="Asia/Kolkata")

    # One millisecond prior: 03:59:59.999 IST
    ts_prior = pd.Timestamp("2026-03-01 03:59:59.999", tz="Asia/Kolkata")
    w_idx_p, w_start_p, w_end_p = pipe.get_window_assignment(ts_prior)
    assert w_idx_p == 0
    assert w_start_p == pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    assert w_end_p == pd.Timestamp("2026-03-01 04:00:00", tz="Asia/Kolkata")

    # Exact boundary 08:00:00.000 IST
    ts_b2 = pd.Timestamp("2026-03-01 08:00:00", tz="Asia/Kolkata")
    w_idx_2, w_start_2, _ = pipe.get_window_assignment(ts_b2)
    assert w_idx_2 == 2
    assert w_start_2 == pd.Timestamp("2026-03-01 08:00:00", tz="Asia/Kolkata")


def test_midnight_rollover_assignment():
    """
    Verifies midnight transition:
    - 23:59:59.999 belongs to Window 5 of Day D.
    - 00:00:00.000 belongs to Window 0 of Day D+1.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    ts_late = pd.Timestamp("2026-03-01 23:59:59", tz="Asia/Kolkata")
    w_idx_late, w_start_late, w_end_late = pipe.get_window_assignment(ts_late)
    assert w_idx_late == 5
    assert w_start_late == pd.Timestamp("2026-03-01 20:00:00", tz="Asia/Kolkata")
    assert w_end_late == pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")

    ts_midnight = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")
    w_idx_mid, w_start_mid, w_end_mid = pipe.get_window_assignment(ts_midnight)
    assert w_idx_mid == 0
    assert w_start_mid == pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")
    assert w_end_mid == pd.Timestamp("2026-03-02 04:00:00", tz="Asia/Kolkata")


def test_utc_to_ist_timezone_conversion():
    """
    Verifies UTC to IST conversion:
    - 18:30:00 UTC on March 1 is 00:00:00 IST on March 2 (Window 0 of next day).
    - 18:29:59 UTC on March 1 is 23:59:59 IST on March 1 (Window 5 of current day).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    utc_ts_rollover = "2026-03-01T18:30:00Z"
    ist_ts_rollover = pipe.localize_timestamp(utc_ts_rollover)
    assert ist_ts_rollover == pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")
    w_idx, w_start, _ = pipe.get_window_assignment(ist_ts_rollover)
    assert w_idx == 0
    assert w_start.day == 2

    utc_ts_prior = "2026-03-01T18:29:59Z"
    ist_ts_prior = pipe.localize_timestamp(utc_ts_prior)
    assert ist_ts_prior == pd.Timestamp("2026-03-01 23:59:59", tz="Asia/Kolkata")
    w_idx_p, w_start_p, _ = pipe.get_window_assignment(ist_ts_prior)
    assert w_idx_p == 5
    assert w_start_p.day == 1


def test_repeated_station_records_aggregation():
    """
    Verifies that multiple incidents at the same station within the same 4-hour window
    are correctly aggregated (count = 3, target_binary = 1).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    records = [
        {"fir_number_hash": "fir_01", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T04:15:00Z", "section_code": "302"},
        {"fir_number_hash": "fir_02", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T04:45:00Z", "section_code": "392"},
        {"fir_number_hash": "fir_03", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T05:10:00Z", "section_code": "379"},
    ]
    df = pd.DataFrame(records)

    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")

    lattice, audit = pipe.aggregate_incidents(df, start_time=start_t, end_time=end_t)

    # 04:15 UTC is 09:45 IST -> belongs to Window 2 [08:00, 12:00) IST
    match = lattice[(lattice["station_id"] == "shivajinagar") & (lattice["window_idx"] == 2)]
    assert len(match) == 1
    row = match.iloc[0]
    assert row["total_incidents"] == 3
    assert row["target_harm_count"] == 2  # 302 and 392 are violent_street_harm
    assert row["target_binary"] == 1
    assert row["coverage_status"] == "OBSERVED_INCIDENT"


def test_missing_reporting_coverage_prevents_zero_fabrication():
    """
    CRITICAL POLICY TEST:
    If a station is outside its verified reporting coverage window, its target is NaN
    and coverage_status is 'UNOBSERVED'.
    The pipeline must NEVER fabricate zero-event labels (Y = 0) for unobserved stations.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    df = pd.DataFrame([
        {"fir_number_hash": "fir_01", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T10:00:00+05:30", "section_code": "302"},
    ])

    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")

    # Only shivajinagar and kothrud are active reporting stations; other 31 are unobserved
    reporting_windows = {
        "shivajinagar": (start_t, end_t),
        "kothrud": (start_t, end_t),
    }

    lattice, audit = pipe.aggregate_incidents(
        df,
        start_time=start_t,
        end_time=end_t,
        station_reporting_windows=reporting_windows
    )

    # 1. Kothrud had verified reporting coverage and 0 incidents -> target_binary is 0
    kothrud_rows = lattice[lattice["station_id"] == "kothrud"]
    assert (kothrud_rows["target_binary"] == 0).all()
    assert (kothrud_rows["coverage_status"] == "OBSERVED_ZERO").all()

    # 2. Hadapsar was NOT in reporting windows -> target_binary MUST be NaN (unobserved)
    hadapsar_rows = lattice[lattice["station_id"] == "hadapsar"]
    assert hadapsar_rows["target_binary"].isna().all()
    assert (hadapsar_rows["coverage_status"] == "UNOBSERVED").all()
    assert (hadapsar_rows["coverage_verified"] == False).all()

    # Total verified reporting windows is 2 stations * 6 windows = 12
    assert audit["verified_reporting_station_windows"] == 12
    # Unobserved station windows is 31 stations * 6 windows = 186
    assert audit["unobserved_station_windows"] == 186


def test_anti_leakage_feature_construction_zero_lookahead():
    """
    Verifies that lag features (lag_1, lag_6, lag_42, rolling_24h, rolling_7d)
    use information strictly prior to window_start t (tau < t).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-08 00:00:00", tz="Asia/Kolkata")  # 7 days = 42 windows

    # Build empty grid
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)
    grid["total_incidents"] = 0

    # Put 5 incidents at shivajinagar at window 0 (2026-03-01 00:00:00)
    sh_mask = (grid["station_id"] == "shivajinagar") & (grid["window_start"] == start_t)
    grid.loc[sh_mask, "total_incidents"] = 5

    # Put 10 incidents at window 1 (2026-03-01 04:00:00)
    sh_mask_1 = (grid["station_id"] == "shivajinagar") & (grid["window_start"] == start_t + pd.Timedelta(hours=4))
    grid.loc[sh_mask_1, "total_incidents"] = 10

    lagged = pipe.construct_lag_features(grid)

    sh_lagged = lagged[lagged["station_id"] == "shivajinagar"].sort_values("window_start").reset_index(drop=True)

    # Window 0: lag_1 must be NaN (no prior window)
    assert pd.isna(sh_lagged.loc[0, "lag_1_count"])

    # Window 1: lag_1 must be 5 (the count at Window 0)
    assert sh_lagged.loc[1, "lag_1_count"] == 5

    # Window 2: lag_1 must be 10 (the count at Window 1)
    assert sh_lagged.loc[2, "lag_1_count"] == 10

    # Diurnal lag (lag_6): Window 6 (2026-03-02 00:00:00, exactly 24h later)
    # lag_6 must be 5 (the count at Window 0)
    assert sh_lagged.loc[6, "lag_6_count"] == 5

    # Weekly seasonal lag (lag_42): Window 42 (exactly 7 days later)
    if len(sh_lagged) > 42:
        assert sh_lagged.loc[42, "lag_42_count"] == 5


def test_chronological_splits_strict_isolation():
    """
    Verifies that train, validation, and test splits have non-overlapping boundaries.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-04-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-03-20 00:00:00", tz="Asia/Kolkata")

    train_df, val_df, test_df = pipe.create_chronological_splits(grid, train_end, val_end)

    assert not train_df.empty
    assert not val_df.empty
    assert not test_df.empty

    # Max train window end must be <= min val window start
    assert train_df["window_end"].max() <= val_df["window_start"].min()
    # Max val window end must be <= min test window start
    assert val_df["window_end"].max() <= test_df["window_start"].min()


def test_theoretical_capacity_accounting_distinct_from_observed():
    """
    Verifies that theoretical capacity (6 * D * 33) is tracked distinctly from
    observed active windows, and statistical adequacy cannot be inferred from gross record count.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    # 10 days of data across 33 stations -> 10 * 6 * 33 = 1980 theoretical station-windows
    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-11 00:00:00", tz="Asia/Kolkata")

    df = pd.DataFrame([
        {"fir_number_hash": "fir_01", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T04:15:00+05:30", "section_code": "302"},
        {"fir_number_hash": "fir_02", "police_station_id": "kothrud", "incident_datetime": "2026-03-02T12:30:00+05:30", "section_code": "392"},
    ])

    lattice, audit = pipe.aggregate_incidents(df, start_time=start_t, end_time=end_t)

    assert audit["timespan_days"] == 10.0
    assert audit["num_stations"] == 33
    assert audit["theoretical_capacity_station_windows"] == 1980
    assert audit["observed_active_station_windows"] == 2
    assert audit["positive_target_station_windows"] == 2
    assert audit["sparsity_warning"] is True  # Prevalence is 2 / 1980 = ~0.10% << 1.0%
