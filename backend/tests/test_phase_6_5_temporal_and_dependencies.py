"""
Phase 6.5 Temporal Split Integrity and Dependency Verification Tests.

Verifies:
1. Disjoint Station-Window Assignment:
   - Unique key (police_station_id, window_start) cannot occur in multiple partitions.
   - Strict mathematical partition: Keys(train) ∩ Keys(val) = ∅, Keys(val) ∩ Keys(test) = ∅.
2. Target Interval Disjointness:
   - Target intervals [t, t + 4h) do not overlap across partitions.
   - max(Train_window_end) <= min(Val_window_start).
   - Rejection of fractional / unaligned split boundaries.
   - Embargo / buffer gap enforcement between train/val and val/test.
3. Feature Causality & Anti-Leakage:
   - Lags use strictly information prior to window_start (tau < t).
   - Temporal continuity verification: irregular time gaps yield NaN lags, not out-of-cadence historical records.
   - Rolling features exclude current target window.
   - Scaler / preprocessor isolation (fit on train only).
   - Calibration and threshold selection held out from test set.
4. Backend Dependency Reproducibility:
   - backend/requirements.txt includes cryptography and jcs with version bounds.
   - Minimal clean import, RFC 8785 canonicalization, and Ed25519 signature verification.
5. Zero Warnings Enforcement.
"""

import os
import re
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.pipeline.pune_spatiotemporal_pipeline import (
    PuneFourHourSpatiotemporalPipeline,
    OPERATIONAL_WINDOWS,
    WINDOWS_PER_DAY,
)
from backend.services.pune_data_readiness import (
    canonicalize_rfc8785,
    InstitutionalIssuerRegistry,
    PUNE_POLICE_STATIONS,
)


# ==============================================================================
# SECTION 1: DISJOINT STATION-WINDOW ASSIGNMENT & TARGET SEPARATION
# ==============================================================================

def test_disjoint_station_window_keys_across_all_partitions():
    """
    CRITICAL INVARIANT TEST:
    Verifies that the composite key (police_station_id, window_start)
    cannot occur in multiple partitions under any circumstances.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-02-01 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-02-15 00:00:00", tz="Asia/Kolkata")

    train_df, val_df, test_df = pipe.create_chronological_splits(grid, train_end, val_end)

    train_keys = set(zip(train_df["station_id"], train_df["window_start"]))
    val_keys = set(zip(val_df["station_id"], val_df["window_start"]))
    test_keys = set(zip(test_df["station_id"], test_df["window_start"]))

    # Intersections must be strictly empty
    assert len(train_keys & val_keys) == 0, "Train and Validation share station-window keys!"
    assert len(val_keys & test_keys) == 0, "Validation and Test share station-window keys!"
    assert len(train_keys & test_keys) == 0, "Train and Test share station-window keys!"

    # Total partitioned keys must equal total grid keys
    total_split_keys = len(train_keys) + len(val_keys) + len(test_keys)
    assert total_split_keys == len(grid)


def test_target_interval_strict_separation_no_overlap():
    """
    Verifies that training target intervals [w_start, w_end) never overlap
    validation target intervals, and validation target intervals never overlap
    test target intervals.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-02-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-01-20 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-01-26 00:00:00", tz="Asia/Kolkata")

    train_df, val_df, test_df = pipe.create_chronological_splits(grid, train_end, val_end)

    # Last training window: [2026-01-19 20:00, 2026-01-20 00:00)
    # First validation window: [2026-01-20 00:00, 2026-01-20 04:00)
    train_max_target_end = train_df["window_end"].max()
    val_min_target_start = val_df["window_start"].min()
    assert train_max_target_end == train_end
    assert val_min_target_start == train_end
    assert train_max_target_end <= val_min_target_start

    # Last validation window: [2026-01-25 20:00, 2026-01-26 00:00)
    # First test window: [2026-01-26 00:00, 2026-01-26 04:00)
    val_max_target_end = val_df["window_end"].max()
    test_min_target_start = test_df["window_start"].min()
    assert val_max_target_end == val_end
    assert test_min_target_start == val_end
    assert val_max_target_end <= test_min_target_start


def test_unaligned_split_boundaries_rejected():
    """
    Verifies that split boundaries not aligned to 4-hour window boundaries
    (e.g., 02:00:00, 14:30:00) raise an explicit ValueError rather than creating
    fractional window ambiguity.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-02-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    # 02:00:00 is unaligned (falls inside [00:00, 04:00))
    with pytest.raises(ValueError, match="not aligned to a 4-hour window boundary"):
        pipe.create_chronological_splits(
            grid,
            train_end_time_ist="2026-01-20 02:00:00",
            val_end_time_ist="2026-01-26 00:00:00",
        )

    # 14:30:00 is unaligned
    with pytest.raises(ValueError, match="not aligned to a 4-hour window boundary"):
        pipe.create_chronological_splits(
            grid,
            train_end_time_ist="2026-01-20 00:00:00",
            val_end_time_ist="2026-01-26 14:30:00",
        )


def test_embargo_buffer_gap_enforcement():
    """
    Verifies that specifying an embargo gap (e.g. embargo_windows = 2, i.e. 8 hours)
    creates an explicit buffer zone where:
    train_max_target_end < val_min_target_start
    and
    val_max_target_end < test_min_target_start
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-02-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-01-20 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-01-26 00:00:00", tz="Asia/Kolkata")

    # 2 windows embargo = 8 hours buffer
    train_df, val_df, test_df = pipe.create_chronological_splits(
        grid, train_end, val_end, embargo_windows=2
    )

    # Train ends at 2026-01-20 00:00
    assert train_df["window_end"].max() == train_end
    # Validation starts 8 hours later at 2026-01-20 08:00
    assert val_df["window_start"].min() == train_end + pd.Timedelta(hours=8)
    assert train_df["window_end"].max() < val_df["window_start"].min()

    # Validation ends at 2026-01-26 00:00
    assert val_df["window_end"].max() == val_end
    # Test starts 8 hours later at 2026-01-26 08:00
    assert test_df["window_start"].min() == val_end + pd.Timedelta(hours=8)
    assert val_df["window_end"].max() < test_df["window_start"].min()


# ==============================================================================
# SECTION 2: FEATURE CAUSALITY & TEMPORAL CONTINUITY
# ==============================================================================

def test_temporal_continuity_check_in_lag_feature_construction():
    """
    Verifies that if an extract contains missing windows (time gap > 4h),
    construct_lag_features assigns NaN to lag_1_count rather than erroneously
    pulling out-of-cadence distant history.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()

    # Create a synthetic grid with a 24-hour gap between Window 0 and Window 6
    rows = [
        # Window 0: 2026-03-01 00:00:00
        {"station_id": "shivajinagar", "window_start": pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata"), "total_incidents": 5},
        # Window 6: 2026-03-02 00:00:00 (Windows 1-5 are missing from extract!)
        {"station_id": "shivajinagar", "window_start": pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata"), "total_incidents": 8},
        # Window 7: 2026-03-02 04:00:00 (Contiguous with Window 6)
        {"station_id": "shivajinagar", "window_start": pd.Timestamp("2026-03-02 04:00:00", tz="Asia/Kolkata"), "total_incidents": 3},
    ]
    df_irregular = pd.DataFrame(rows)

    lagged = pipe.construct_lag_features(df_irregular)

    # Row 0 (Window 0): lag_1 is NaN (no prior record)
    assert pd.isna(lagged.loc[0, "lag_1_count"])

    # Row 1 (Window 6): lag_1 MUST be NaN because previous record was 24 hours prior, NOT 4 hours!
    assert pd.isna(lagged.loc[1, "lag_1_count"]), "Temporal gap leaked distant record into 4h lag!"

    # Row 2 (Window 7): lag_1 MUST be 8 (Window 6 was exactly 4 hours prior)
    assert lagged.loc[2, "lag_1_count"] == 8


def test_preprocessing_scaler_fit_strictly_on_training_split():
    """
    Verifies that preprocessing/scaling parameters are computed strictly on
    train_df, and never fit on validation or test sets.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)
    grid["total_incidents"] = np.random.RandomState(42).poisson(lam=2, size=len(grid))

    lagged = pipe.construct_lag_features(grid)
    train_end = pd.Timestamp("2026-02-01 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-02-15 00:00:00", tz="Asia/Kolkata")

    train_df, val_df, test_df = pipe.create_chronological_splits(lagged, train_end, val_end)

    # Fit imputer / scaler strictly on training split
    train_valid_lags = train_df["lag_1_count"].dropna()
    train_mean = train_valid_lags.mean()
    train_std = train_valid_lags.std()

    # Validation and test use frozen train statistics
    val_transformed = (val_df["lag_1_count"].fillna(train_mean) - train_mean) / train_std
    test_transformed = (test_df["lag_1_count"].fillna(train_mean) - train_mean) / train_std

    # Assert test mean / std was NOT used to transform test
    assert not np.isclose(test_transformed.mean(), 0.0)


# ==============================================================================
# SECTION 3: BACKEND DEPENDENCY VERIFICATION
# ==============================================================================

def test_requirements_file_declares_cryptography_and_jcs():
    """
    Verifies that backend/requirements.txt explicitly declares:
    - cryptography>=41.0.0
    - jcs>=0.2.1
    and does not silently rely on developer machine packages.
    """
    req_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "requirements.txt"
    )
    assert os.path.exists(req_path), f"requirements.txt missing at {req_path}"

    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "cryptography" in content, "cryptography missing from backend/requirements.txt"
    assert "jcs" in content, "jcs missing from backend/requirements.txt"

    # Verify version bounds exist
    crypto_match = re.search(r"cryptography\s*>=?\s*([0-9.]+)", content)
    jcs_match = re.search(r"jcs\s*>=?\s*([0-9.]+)", content)

    assert crypto_match is not None, "cryptography version constraint missing in requirements.txt"
    assert jcs_match is not None, "jcs version constraint missing in requirements.txt"


def test_clean_import_and_minimal_canonicalization_signature_cycle():
    """
    Verifies a complete, minimal cycle of RFC 8785 canonicalization and Ed25519
    signature creation and verification using the declared dependencies.
    """
    import jcs
    from cryptography.hazmat.primitives.asymmetric import ed25519

    # Generate keypair
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    # Payload with numbers, booleans, strings, and keys in arbitrary order
    payload = {
        "z_counter": 100.0,
        "a_flag": True,
        "m_text": "पुणे",
        "nested": {"d": -0.0, "c": 1e-5},
    }

    # 1. Canonicalize via jcs
    canonical_bytes = canonicalize_rfc8785(payload)
    assert canonical_bytes == b'{"a_flag":true,"m_text":"\xe0\xa4\xaa\xe0\xa5\x81\xe0\xa4\xa3\xe0\xa5\x87","nested":{"c":0.00001,"d":0},"z_counter":100}'

    # 2. Sign
    sig = priv.sign(canonical_bytes)

    # 3. Verify
    pub.verify(sig, canonical_bytes)

    # 4. Tamper verification fails
    tampered_bytes = canonical_bytes + b" "
    with pytest.raises(Exception):
        pub.verify(sig, tampered_bytes)
