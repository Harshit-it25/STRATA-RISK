"""
test_phase_6_6_dependency_and_config.py
======================================
Regression tests for Strata Risk Phase 6.6:
1. Dependency Manifest & Lockfile Reproducibility (abstract requirements vs exact lock).
2. Pytest Warning Configuration Scope (narrow targeting of third-party matplotlib/pyparsing).
3. Canonicalization and Asymmetric Cryptography Execution.
4. Temporal Embargo Observation Accounting and Boundary Disjointness.
"""

import os
import re
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from backend.pipeline.pune_spatiotemporal_pipeline import (
    PuneFourHourSpatiotemporalPipeline,
    OPERATIONAL_WINDOWS,
    WINDOWS_PER_DAY,
)
from backend.services.pune_data_readiness import (
    canonicalize_rfc8785,
    PUNE_POLICE_STATIONS,
)


# ==============================================================================
# SECTION 1: DEPENDENCY MANIFEST & LOCKFILE REPRODUCIBILITY
# ==============================================================================

def test_requirements_file_has_abstract_constraints():
    """
    Verifies that backend/requirements.txt declares abstract minimum-version constraints
    using '>=' and not exact '==' pins, representing lower bounds for flexibility.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req_path = os.path.join(backend_dir, "requirements.txt")
    assert os.path.exists(req_path), f"Missing {req_path}"

    with open(req_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    assert any("cryptography>=" in l for l in lines), "cryptography>= constraint missing in requirements.txt"
    assert any("jcs>=" in l for l in lines), "jcs>= constraint missing in requirements.txt"

    # Confirm requirements.txt uses lower-bound constraints, not exact pins
    for line in lines:
        assert "==" not in line, f"requirements.txt should use abstract constraints, found exact pin: {line}"


def test_requirements_lock_file_has_exact_pins():
    """
    Verifies that backend/requirements-lock.txt provides exact '==' pins
    for deterministic, bit-for-bit reproducible environments.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_path = os.path.join(backend_dir, "requirements-lock.txt")
    assert os.path.exists(lock_path), f"Missing {lock_path}"

    with open(lock_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    assert len(lines) >= 12, f"Lockfile contains too few dependencies: {lines}"

    # Verify all non-comment lines have exact '==' pins
    for line in lines:
        assert "==" in line, f"Lockfile dependency must have exact '==' pin: {line}"

    # Verify security dependencies are specifically locked
    crypto_lines = [l for l in lines if l.startswith("cryptography==")]
    jcs_lines = [l for l in lines if l.startswith("jcs==")]
    assert len(crypto_lines) == 1, "cryptography exact pin missing in lockfile"
    assert len(jcs_lines) == 1, "jcs exact pin missing in lockfile"


def test_canonicalization_and_ed25519_execution_in_environment():
    """
    Verifies that the installed JCS and cryptography packages execute
    RFC 8785 canonicalization and Ed25519 signing cleanly.
    """
    import jcs
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature

    data = {
        "b_station": "Faraskhana",
        "a_city": "Pune",
        "pi_approx": 3.14159,
        "active": True
    }

    # Canonicalize using JCS
    canonical_bytes = canonicalize_rfc8785(data)
    assert canonical_bytes.startswith(b'{"a_city":"Pune"')

    # Generate key and sign
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    sig = priv.sign(canonical_bytes)

    # Verify signature passes
    pub.verify(sig, canonical_bytes)

    # Verify tampered payload fails
    tampered_bytes = canonical_bytes.replace(b"Pune", b"Mumbai")
    with pytest.raises(InvalidSignature):
        pub.verify(sig, tampered_bytes)


# ==============================================================================
# SECTION 2: PYTEST WARNING FILTER REVIEW
# ==============================================================================

def test_pytest_ini_filter_is_narrowly_scoped():
    """
    Verifies that pytest.ini:
    1. Specifically suppresses only 'pyparsing.PyparsingDeprecationWarning'.
    2. Strictly confines the module to 'matplotlib.*'.
    3. Does not broadly suppress DeprecationWarning, UserWarning, or warnings from backend.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ini_path = os.path.join(root_dir, "pytest.ini")
    assert os.path.exists(ini_path), f"Missing {ini_path}"

    with open(ini_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "ignore::pyparsing.PyparsingDeprecationWarning:matplotlib.*" in content, (
        "pytest.ini missing the narrow matplotlib pyparsing filter"
    )

    # Ensure broad suppressions are NOT present
    assert "ignore::DeprecationWarning" not in content, "pytest.ini must not broadly ignore DeprecationWarning"
    assert "ignore::UserWarning" not in content, "pytest.ini must not broadly ignore UserWarning"
    assert "ignore::Warning" not in content, "pytest.ini must not broadly ignore all Warnings"


# ==============================================================================
# SECTION 3: TEMPORAL EMBARGO & OBSERVATION ACCOUNTING
# ==============================================================================

def test_embargo_zero_preserves_all_observations():
    """
    Verifies that when embargo_windows=0 (the default):
    - No station-windows are dropped across partition boundaries.
    - Total train + val + test rows equals the original grid rows.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-01-07 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-01-03 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-01-05 00:00:00", tz="Asia/Kolkata")

    train_df, val_df, test_df = pipe.create_chronological_splits(
        lattice_df=grid,
        train_end_time_ist=train_end,
        val_end_time_ist=val_end,
        embargo_windows=0
    )

    total_split_rows = len(train_df) + len(val_df) + len(test_df)
    assert total_split_rows == len(grid), (
        f"embargo=0 should drop zero observations: {total_split_rows} != {len(grid)}"
    )


def test_embargo_nonzero_observation_accounting():
    """
    Verifies observation depletion mathematics under nonzero embargo:
    - With embargo_windows = M, exactly M windows per station are held out at train/val
      and M windows per station at val/test.
    - Total dropped station-windows = 2 * M * S (assuming test extends beyond val_end + M).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-01-09 00:00:00", tz="Asia/Kolkata")
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)

    train_end = pd.Timestamp("2026-01-03 00:00:00", tz="Asia/Kolkata")
    val_end = pd.Timestamp("2026-01-06 00:00:00", tz="Asia/Kolkata")

    M = 2  # 2 windows = 8 hours embargo
    train_df, val_df, test_df = pipe.create_chronological_splits(
        lattice_df=grid,
        train_end_time_ist=train_end,
        val_end_time_ist=val_end,
        embargo_windows=M
    )

    # Number of stations S = len(PUNE_POLICE_STATIONS) = 33
    num_stations = len(PUNE_POLICE_STATIONS)
    expected_dropped_rows = 2 * M * num_stations  # 2 boundaries * 2 windows * 33 stations = 132 rows
    actual_dropped_rows = len(grid) - (len(train_df) + len(val_df) + len(test_df))

    assert actual_dropped_rows == expected_dropped_rows, (
        f"Expected {expected_dropped_rows} dropped station-windows under M={M}, got {actual_dropped_rows}"
    )

    # Disjointness is preserved
    train_keys = set(zip(train_df["station_id"], train_df["window_start"]))
    val_keys = set(zip(val_df["station_id"], val_df["window_start"]))
    test_keys = set(zip(test_df["station_id"], test_df["window_start"]))
    assert train_keys.isdisjoint(val_keys)
    assert val_keys.isdisjoint(test_keys)
    assert train_keys.isdisjoint(test_keys)
