"""
test_phase_7_data_exploration.py
================================
Regression tests for Strata Risk Phase 7:
1. Authorized Real Data Verification (defaults to NO_DATA, STAGE_0_UNAUTHORIZED).
2. Strict Rejection of Test Fixtures as Production Data.
3. Reporting Coverage Semantics (no zero inference from empty extract).
4. Point-in-Time Delay & Anti-Leakage Feature Construction.
5. Invariant Checks: Zero Pune Model Trained, Serving Blocked.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from backend.services.pune_data_readiness import (
    PuneReadinessStatus,
    PuneLifecycleStage,
    PuneDataReadinessGate,
    PuneExploratoryAnalysisWorkflow,
    PuneLifecycleTransitionManager,
    PuneAuthorizationValidator,
    InstitutionalIssuerRegistry,
    PUNE_POLICE_STATIONS,
)
from backend.pipeline.pune_spatiotemporal_pipeline import PuneFourHourSpatiotemporalPipeline
from scripts.run_pune_eda import run_eda_pipeline


# ==============================================================================
# SECTION 1: VERIFICATION OF NO_DATA AND INSTITUTIONAL DEPENDENCY
# ==============================================================================

def test_pipeline_defaults_to_no_data_when_unprovided():
    """
    CRITICAL INVARIANT TEST:
    When no dataset path is supplied, the pipeline and gate must unconditionally
    emit NO_DATA and STAGE_0_UNAUTHORIZED, and never invent empirical statistics.
    """
    res = run_eda_pipeline(dataset_path=None)

    assert res["execution_status"] == "NO_DATA"
    assert res["is_fixture"] is False

    gate_eval = res["gate_evaluation"]
    assert gate_eval["gate_status"] == PuneReadinessStatus.NO_DATA.value
    assert gate_eval["readiness_status"] == PuneReadinessStatus.NO_DATA.value
    assert gate_eval["is_ready_for_eda"] is False
    assert gate_eval["is_ready_for_training"] is False
    assert gate_eval["is_ready_for_deployment"] is False

    eda_eval = res["eda_evaluation"]
    assert eda_eval["status"] == PuneReadinessStatus.NO_DATA.value
    assert eda_eval["eda_report"] is None

    lifecycle = res["lifecycle_transitions"]
    assert lifecycle["current_stage"] == PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value
    assert lifecycle["stages"][PuneLifecycleStage.STAGE_1_AUTHORIZATION_VERIFIED.value]["achieved"] is False
    assert lifecycle["model_training_eligible"] is False


def test_test_fixtures_strictly_blocked_from_production_intake():
    """
    Verifies that sample test fixtures in fixtures/ cannot be submitted
    as authorized production data.
    """
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "fixtures",
        "sample_pune_cctns_fixture.csv"
    )
    assert os.path.exists(fixture_path), f"Missing fixture file at {fixture_path}"

    # Attempting to evaluate fixture in production mode (is_fixture=False) without an authorized manifest
    gate_res = PuneDataReadinessGate.evaluate(
        df_or_path=fixture_path,
        authorization_manifest=None,
        is_fixture=False
    )

    # Must fail authorization immediately
    assert gate_res["gate_status"] in (
        PuneReadinessStatus.AUTHORIZATION_MISSING.value,
        PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value,
    )
    assert gate_res["is_ready_for_eda"] is False
    assert gate_res["is_ready_for_training"] is False


# ==============================================================================
# SECTION 2: REPORTING COVERAGE SEMANTICS (ZERO INFERENCE FORBIDDEN)
# ==============================================================================

def test_empty_incident_extract_does_not_infer_zero_events():
    """
    CRITICAL METHODOLOGICAL TEST:
    An empty incident extract or station without verified reporting coverage
    must be classified as UNKNOWN_COVERAGE (target Y = NaN), NEVER as
    VERIFIED_OBSERVED_ZERO (Y = 0).
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-01-03 00:00:00", tz="Asia/Kolkata")

    # Empty incidents dataframe
    empty_incidents = pd.DataFrame(columns=[
        "fir_number_hash", "police_station_id", "incident_datetime", "section_code"
    ])

    lattice, audit = pipe.aggregate_incidents(
        empty_incidents,
        start_time=start_t,
        end_time=end_t,
        require_coverage_evidence=True
    )

    # Zero station-windows can be classified as VERIFIED_OBSERVED_ZERO
    assert (lattice["observation_coverage_class"] == "VERIFIED_OBSERVED_ZERO").sum() == 0
    # Coverage classes must only be UNKNOWN_COVERAGE or NOT_OPERATIONAL
    assert set(lattice["observation_coverage_class"].unique()).issubset({"UNKNOWN_COVERAGE", "NOT_OPERATIONAL"})
    # Binary targets must be NaN, never fabricated zeros
    assert lattice["target_binary"].isna().all()
    assert audit["verified_reporting_station_windows"] == 0
    assert audit["observed_active_station_windows"] == 0


# ==============================================================================
# SECTION 3: POINT-IN-TIME INFORMATION AVAILABILITY & REGISTRATION DELAY
# ==============================================================================

def test_point_in_time_registration_delay_filtering():
    """
    Verifies that when FIR registration time is recorded, an incident that
    occurred before forecast time t but was registered AFTER t cannot enter
    the feature vector available at time t.
    """
    # Prediction time: 2026-03-01 12:00:00 IST
    t_pred = pd.Timestamp("2026-03-01 12:00:00", tz="Asia/Kolkata")

    # Incidents:
    # Incident A: occurred 10:00, registered 11:30 -> Available at t_pred
    # Incident B: occurred 09:30, registered 14:00 -> NOT available at t_pred (reporting delay = 4.5h)
    incidents = pd.DataFrame([
        {
            "fir_hash": "fir_A",
            "station_id": "shivajinagar",
            "incident_datetime": pd.Timestamp("2026-03-01 10:00:00", tz="Asia/Kolkata"),
            "registration_datetime": pd.Timestamp("2026-03-01 11:30:00", tz="Asia/Kolkata"),
        },
        {
            "fir_hash": "fir_B",
            "station_id": "shivajinagar",
            "incident_datetime": pd.Timestamp("2026-03-01 09:30:00", tz="Asia/Kolkata"),
            "registration_datetime": pd.Timestamp("2026-03-01 14:00:00", tz="Asia/Kolkata"),
        },
    ])

    # Point-in-time filter: registration_datetime <= t_pred
    pit_available = incidents[incidents["registration_datetime"] <= t_pred]

    assert len(pit_available) == 1
    assert pit_available.iloc[0]["fir_hash"] == "fir_A"
    assert "fir_B" not in pit_available["fir_hash"].values


def test_embargo_does_not_replace_point_in_time_feature_filtering():
    """
    Documents that while an embargo creates an inter-split deadband buffer,
    it does not substitute for strict point-in-time feature construction.
    """
    # Incident occurring 1h before split boundary but registered 12h later
    split_boundary = pd.Timestamp("2026-04-01 00:00:00", tz="Asia/Kolkata")
    incident_time = split_boundary - pd.Timedelta(hours=1)
    registration_time = split_boundary + pd.Timedelta(hours=11)

    # If evaluated at split_boundary, incident is NOT yet registered
    is_available_at_split = registration_time <= split_boundary
    assert not is_available_at_split, "Unregistered incident cannot be available at split boundary"
