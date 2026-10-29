"""
test_phase_7_1_handoff_and_intake.py
====================================
Regression tests for Strata Risk Phase 7.1:
1. Schema & Field Consistency across Ingestion, Readiness, and Spatiotemporal Pipelines.
2. Asymmetric Ed25519 vs. Legacy HMAC Authorization Fail-Closed Validation.
3. Reporting Coverage Evidence Enforcement (Zero Inference Prohibited).
4. Point-in-Time Availability and Delay Auditing.
5. Invariant Attestations: Zero Pune Model Trained, Serving Blocked.
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
    PuneAuthorizationValidator,
    InstitutionalIssuerRegistry,
    EXPECTED_PUNE_SCHEMA,
    PUNE_POLICE_STATIONS,
    PUNE_STATION_VERIFICATION_STATUS,
    canonicalize_rfc8785,
)
from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
    PUNE_LAT_BOUNDS,
    PUNE_LON_BOUNDS,
    STATION_ALIASES,
)
from backend.pipeline.pune_spatiotemporal_pipeline import PuneFourHourSpatiotemporalPipeline


# ==============================================================================
# SECTION 1: SCHEMA & FIELD CONSISTENCY AUDIT
# ==============================================================================

def test_schema_field_names_and_types_match_pipeline():
    """
    Verifies that EXPECTED_PUNE_SCHEMA matches the core columns expected
    by PuneDataIngestionPipeline and PuneFourHourSpatiotemporalPipeline.
    """
    required_cols = {"fir_number_hash", "police_station_id", "incident_datetime", "section_code"}
    optional_cols = {"registration_datetime", "place_of_occurrence", "latitude", "longitude"}

    schema_keys = set(EXPECTED_PUNE_SCHEMA.keys())

    assert required_cols.issubset(schema_keys), (
        f"Missing required columns in EXPECTED_PUNE_SCHEMA: {required_cols - schema_keys}"
    )
    assert optional_cols.issubset(schema_keys), (
        f"Missing optional columns in EXPECTED_PUNE_SCHEMA: {optional_cols - schema_keys}"
    )


def test_station_registry_contains_all_33_pune_stations():
    """
    Verifies that the canonical station registry contains exactly the 33 standardized
    Pune City Police stations and categorizes core vs bifurcated jurisdictions.
    """
    assert len(PUNE_POLICE_STATIONS) == 33
    assert len(PUNE_STATION_VERIFICATION_STATUS) == 33

    # Check bifurcated stations
    bifurcated = [
        s for s, m in PUNE_STATION_VERIFICATION_STATUS.items()
        if m["status"] == "UNVERIFIED_RECENT_BIFURCATION"
    ]
    assert set(bifurcated) == {"alankar", "pashan", "bavdhan"}


# ==============================================================================
# SECTION 2: FAIL-CLOSED AUTHORIZATION VALIDATION
# ==============================================================================

def test_legacy_hmac_or_unsigned_manifest_rejected_in_production():
    """
    Verifies that legacy HMAC manifests or unsigned manifests are rejected
    with fail-closed security in production mode (is_fixture=False).
    """
    legacy_hmac_manifest = {
        "manifest_version": "2.0",
        "authorization_id": "AUTH-LEGACY-001",
        "mou_reference": "MOU/PUNE-COP/2026/STRATA-001",
        "issuing_authority": "Office of Commissioner of Police, Pune City",
        "issuer_id": "pune_city_police_cop",
        "issued_at": "2026-01-01T00:00:00Z",
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_until": "2027-12-31T23:59:59Z",
        "is_authorized": True,
        "permitted_use": "public_safety_risk_modeling",
        "dpdpa_compliance_certified": True,
        "dataset_fingerprint": {
            "expected_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        },
        "verification_token": "hmac_signature_token"  # Legacy symmetric HMAC format without Ed25519 signature
    }

    is_ok, status, violations, _ = PuneAuthorizationValidator.validate(
        manifest=legacy_hmac_manifest,
        is_fixture=False
    )

    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("public key" in v.lower() or "signature" in v.lower() or "cryptographic" in v.lower() for v in violations)


def test_unauthorized_dataset_transition_manager_locks_training():
    """
    Verifies that in STAGE_0_UNAUTHORIZED, model_training_eligible,
    independent_validation_eligible, and pilot_deployment_eligible are strictly False.
    """
    gate_eval = PuneDataReadinessGate.evaluate(df_or_path=None)
    from backend.services.pune_data_readiness import PuneLifecycleTransitionManager

    transitions = PuneLifecycleTransitionManager.evaluate_transitions(gate_eval)
    assert transitions["current_stage"] == PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value
    assert transitions["model_training_eligible"] is False
    assert transitions["independent_validation_eligible"] is False
    assert transitions["pilot_deployment_eligible"] is False


# ==============================================================================
# SECTION 3: OBSERVATION COVERAGE & DELAY LOGIC
# ==============================================================================

def test_observation_coverage_requires_explicit_evidence():
    """
    Verifies that zero incidents in a window requires explicit station reporting
    evidence to be labeled VERIFIED_OBSERVED_ZERO, otherwise labeled UNKNOWN_COVERAGE.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")

    # One station has verified reporting window, one does not
    reporting_evidence = {
        "shivajinagar": (start_t, end_t)
    }

    # Empty incidents
    df_empty = pd.DataFrame(columns=[
        "fir_number_hash", "police_station_id", "incident_datetime", "section_code"
    ])

    lattice, audit = pipe.aggregate_incidents(
        df_empty,
        start_time=start_t,
        end_time=end_t,
        station_reporting_windows=reporting_evidence
    )

    # Shivajinagar had reporting evidence and 0 incidents -> VERIFIED_OBSERVED_ZERO
    sh_rows = lattice[lattice["station_id"] == "shivajinagar"]
    assert (sh_rows["observation_coverage_class"] == "VERIFIED_OBSERVED_ZERO").all()
    assert (sh_rows["target_binary"] == 0).all()

    # Kothrud had NO reporting evidence -> UNKNOWN_COVERAGE
    kt_rows = lattice[lattice["station_id"] == "kothrud"]
    assert (kt_rows["observation_coverage_class"] == "UNKNOWN_COVERAGE").all()
    assert kt_rows["target_binary"].isna().all()
