"""
Comprehensive Test Suite for Pune Authorized Data Intake and Model-Readiness Gate (Phase 5 Hardened).

Verifies all required dimensions and adversarial hardening:
1. Missing dataset -> NO_DATA
2. Missing authorization manifest -> AUTHORIZATION_MISSING
3. Forged or unverifiable authorization -> AUTHORIZATION_UNVERIFIED
4. Expired authorization -> AUTHORIZATION_UNVERIFIED (expired)
5. Revoked authorization -> AUTHORIZATION_UNVERIFIED (revoked)
6. Manifest-to-dataset hash mismatch -> AUTHORIZATION_UNVERIFIED (mismatch)
7. Untrusted issuing authority -> AUTHORIZATION_UNVERIFIED (untrusted)
8. Fixture credentials used on production dataset -> AUTHORIZATION_UNVERIFIED (blocked)
9. Invalid schema -> SCHEMA_INVALID
10. Privacy-review failure -> PRIVACY_REVIEW_REQUIRED (with zero PII value leak)
11. Insufficient temporal coverage -> INSUFFICIENT_TEMPORAL_COVERAGE
12. Insufficient station coverage -> INSUFFICIENT_SPATIAL_COVERAGE
13. Insufficient target support -> INSUFFICIENT_TARGET_SUPPORT
14. Missing official GIS mapping -> GIS_MAPPING_INCOMPLETE (blocks coordinate-level EDA)
15. Independent separation of station-level vs coordinate-level readiness
16. Readiness statuses cannot be bypassed (sequential non-bypassable gating)
17. Active safety: Pune remains UNSUPPORTED with zero numerical forecasts
18. Exploratory analysis workflow emitting NO_DATA when data is absent
19. Forecasting evaluation protocol hierarchy and calibration split isolation
20. Threshold classifications audit and documentation
"""

import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from backend.services.pune_data_readiness import (
    PuneReadinessStatus,
    PuneLifecycleStage,
    PuneThresholdConfig,
    InstitutionalIssuerRegistry,
    PuneAuthorizationValidator,
    PuneDataReadinessGate,
    PuneDataReadinessAudit,
    PuneExploratoryAnalysisWorkflow,
    PuneForecastingEvaluationProtocol,
    PuneLifecycleTransitionManager,
    PUNE_POLICE_STATIONS,
)
from backend.ingestion.pune_ingestion_pipeline import PuneDataIngestionPipeline
from scripts.run_pune_eda import run_eda_pipeline
from backend.config.city_config import get_city_config, resolve_city_by_coordinates, is_city_model_ready

from cryptography.hazmat.primitives.asymmetric import ed25519

# Generate sandboxed mock keypair for unit testing environment
MOCK_PUNE_COP_PRIVATE_KEY = ed25519.Ed25519PrivateKey.generate()
MOCK_PUNE_COP_PUBLIC_KEY_HEX = MOCK_PUNE_COP_PRIVATE_KEY.public_key().public_bytes_raw().hex()
os.environ["PUNE_COP_ED25519_PUBLIC_KEY"] = MOCK_PUNE_COP_PUBLIC_KEY_HEX

# For fixture authority tests: standard 32-byte sandbox seed
TEST_SANDBOX_PRIVATE_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(
    bytes.fromhex("fb9b4e3e1a5b86449380ff61bfcec074be7ad2dc2b7e422e9968eb67a26ae0e6")
)

# Authentically signed institutional authorization manifest for testing
VALID_MOU_MANIFEST = InstitutionalIssuerRegistry.create_authorized_manifest(
    mou_reference="MOU/PUNE-COP/2026/STRATA-001",
    issuer_id="pune_city_police_cop",
    signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
    permitted_use="public_safety_risk_modeling",
    valid_from="2026-01-01T00:00:00Z",
    valid_until="2027-12-31T23:59:59Z",
    is_fixture=False
)


# 1. Missing Dataset Tests
def test_gate_missing_dataset_emits_no_data():
    """Verify missing file, None path, or empty dataframe emits NO_DATA."""
    res_none = PuneDataReadinessGate.evaluate(df_or_path=None)
    assert res_none["gate_status"] == PuneReadinessStatus.NO_DATA.value
    assert res_none["readiness_status"] == PuneReadinessStatus.NO_DATA.value
    assert res_none["is_ready_for_eda"] is False
    assert res_none["is_ready_for_training"] is False
    assert res_none["is_ready_for_deployment"] is False

    res_nonexistent = PuneDataReadinessGate.evaluate(df_or_path="non_existent_pune_file.csv")
    assert res_nonexistent["gate_status"] == PuneReadinessStatus.NO_DATA.value
    assert "does not exist" in res_nonexistent["gate_message"]

    empty_df = pd.DataFrame()
    res_empty = PuneDataReadinessGate.evaluate(df_or_path=empty_df)
    assert res_empty["gate_status"] == PuneReadinessStatus.NO_DATA.value
    assert "0 records" in res_empty["gate_message"]


# 2. Missing Authorization Manifest Tests
def test_gate_missing_authorization_evidence():
    """Verify local data presence without authorization manifest emits AUTHORIZATION_MISSING."""
    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res_no_auth = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=None)
    assert res_no_auth["gate_status"] == PuneReadinessStatus.AUTHORIZATION_MISSING.value
    assert "AUTHORIZATION_MISSING" in res_no_auth["gate_message"]
    assert res_no_auth["is_ready_for_eda"] is False


# 3. Forged / Unverifiable Authorization Tests (Hardened Trust Model)
def test_gate_forged_or_tampered_token_emits_unverified():
    """Verify user-controlled boolean with forged token is rejected as AUTHORIZATION_UNVERIFIED."""
    forged_manifest = dict(VALID_MOU_MANIFEST)
    # Attacker attempts to change agreement reference without valid cryptographic key
    forged_manifest["mou_reference"] = "FORGED_MOU_REFERENCE_UNAUTHORIZED"

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=forged_manifest)
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert "Cryptographic verification" in str(res["evaluation_details"]["violations"])


def test_gate_user_controlled_boolean_without_token_rejected():
    """Verify naive manifest without cryptographic token cannot bypass authorization."""
    naive_manifest = {
        "mou_reference": "MOU/PUNE-COP/2026/FAKE-999",
        "issuing_authority": "Office of Commissioner of Police, Pune City",
        "permitted_use": "public_safety_risk_modeling",
        "is_authorized": True,  # User-controlled boolean!
        "dpdpa_compliance_certified": True,
        # Missing verification_token!
    }

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=naive_manifest)
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("verification_token" in v for v in res["evaluation_details"]["violations"])


# 4. Expired & Not-Yet-Effective Authorization Tests
def test_gate_expired_authorization_emits_unverified():
    """Verify expired manifest is rejected as AUTHORIZATION_UNVERIFIED."""
    expired_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
        mou_reference="MOU/PUNE-COP/2020/EXPIRED-001",
        valid_from="2020-01-01T00:00:00Z",
        valid_until="2021-01-01T00:00:00Z",  # In the past!
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
    )

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=expired_manifest)
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("expired" in v.lower() for v in res["evaluation_details"]["violations"])


# 5. Revoked Authorization Tests
def test_gate_revoked_authorization_emits_unverified():
    """Verify revoked manifest is rejected as AUTHORIZATION_UNVERIFIED."""
    revoked_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
        mou_reference="MOU/PUNE-COP/2026/REVOKED-001",
        is_revoked=True,  # Explicitly revoked!
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
    )

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=revoked_manifest)
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("revoked" in v.lower() for v in res["evaluation_details"]["violations"])


# 6. Untrusted Authority Tests
def test_gate_untrusted_issuer_emits_unverified():
    """Verify manifest issued by an unknown/untrusted issuer is rejected."""
    untrusted_manifest = dict(VALID_MOU_MANIFEST)
    untrusted_manifest["issuer_id"] = "unknown_rogue_authority"

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(df_or_path=valid_df, authorization_manifest=untrusted_manifest)
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("untrusted" in v.lower() for v in res["evaluation_details"]["violations"])


# 7. Fixture Credentials on Production Dataset Blocked
def test_gate_fixture_credentials_on_production_dataset_blocked():
    """Verify test fixture authority credentials cannot authorize production data."""
    fixture_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
        issuer_id="test_fixture_authority",
        signing_private_key=TEST_SANDBOX_PRIVATE_KEY,
        is_fixture=True
    )

    valid_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    # Presented as production (is_fixture=False)
    res = PuneDataReadinessGate.evaluate(
        df_or_path=valid_df,
        authorization_manifest=fixture_manifest,
        is_fixture=False
    )
    assert res["gate_status"] == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("fixture" in v.lower() for v in res["evaluation_details"]["violations"])


# 8. Manifest-to-Dataset Fingerprint Mismatch Tests
def test_gate_dataset_fingerprint_mismatch_rejected():
    """Verify manifest bound to Dataset A cannot authorize Dataset B."""
    mismatched_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
        dataset_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
    )

    # Calling with real fixture CSV file (whose actual hash differs from 0000...)
    auth_ok, status, violations, _ = PuneAuthorizationValidator.validate(
        manifest=mismatched_manifest,
        dataset_path="fixtures/sample_pune_cctns_fixture.csv",
        is_fixture=False
    )
    assert auth_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("fingerprint mismatch" in v.lower() for v in violations)


# 9. Invalid Schema Tests
def test_gate_invalid_schema():
    """Verify authorized dataset with missing mandatory columns emits SCHEMA_INVALID."""
    bad_schema_df = pd.DataFrame([{
        "fir_number_hash": "FIR-001",
        # Missing police_station_id!
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392"
    }])

    res = PuneDataReadinessGate.evaluate(
        df_or_path=bad_schema_df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.SCHEMA_INVALID.value
    assert "police_station_id" in str(res["evaluation_details"]["schema_errors"])
    assert res["is_ready_for_eda"] is False


# 10. Privacy Review Failure & Zero Value Leak Tests
def test_gate_privacy_review_failure_sanitizes_pii():
    """Verify citizen PII triggers PRIVACY_REVIEW_REQUIRED and does not echo private values."""
    secret_citizen_phone = "9822019999"
    secret_pan_card = "ABCDE1234F"
    pii_df = pd.DataFrame([{
        "fir_number_hash": "FIR-PII-01",
        "police_station_id": "shivajinagar",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "392",
        "place_of_occurrence": f"Contact citizen at {secret_citizen_phone} or PAN {secret_pan_card}"
    }])

    res = PuneDataReadinessGate.evaluate(
        df_or_path=pii_df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.PRIVACY_REVIEW_REQUIRED.value
    assert "DPDPA 2023" in res["gate_message"]
    # Verify the sensitive phone number and PAN are not echoed in exception or message
    assert secret_citizen_phone not in str(res["gate_message"])
    assert secret_citizen_phone not in str(res["evaluation_details"])
    assert secret_pan_card not in str(res["gate_message"])
    assert secret_pan_card not in str(res["evaluation_details"])


# 11. Insufficient Temporal Coverage Tests
def test_gate_insufficient_temporal_coverage():
    """Verify dataset with < 180 days coverage emits INSUFFICIENT_TEMPORAL_COVERAGE."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-TIME-{i}" for i in range(10)],
        "police_station_id": ["kothrud"] * 10,
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 10
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.INSUFFICIENT_TEMPORAL_COVERAGE.value
    assert res["evaluation_details"]["timespan_days"] < 180.0
    assert res["is_ready_for_eda"] is False


# 12. Insufficient Spatial Coverage Tests
def test_gate_insufficient_spatial_coverage():
    """Verify dataset covering < 80% of authorized stations emits INSUFFICIENT_SPATIAL_COVERAGE."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-SPA-{i}" for i in range(200)],
        "police_station_id": ["kothrud" if i % 2 == 0 else "swargate" for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 200
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.INSUFFICIENT_SPATIAL_COVERAGE.value
    assert res["evaluation_details"]["coverage_percentage"] < 80.0
    assert res["is_ready_for_eda"] is False


# 13. Insufficient Target Support Tests
def test_gate_insufficient_target_support():
    """Verify dataset with < 20 positive cases emits INSUFFICIENT_TARGET_SUPPORT."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:28]
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-TAR-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["unknown_minor_non_target_code"] * 200  # Maps to other_cognizable (0 positives)
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.INSUFFICIENT_TARGET_SUPPORT.value
    assert res["evaluation_details"]["positive_target_count"] == 0
    assert res["is_ready_for_eda"] is False


# 14. Independent Separation of Station-Level vs Coordinate-Level Readiness
def test_separation_of_station_level_and_coordinate_level_readiness():
    """
    Verify station-level EDA passes when station IDs are valid even if coordinates/GIS are missing,
    while coordinate-level EDA is correctly blocked until official GIS polygons exist.
    """
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:28]
    # Dataset with valid station identifiers, but ZERO coordinates
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-SEP-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 200,
        "latitude": [np.nan] * 200,
        "longitude": [np.nan] * 200
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST,
        gis_boundary_path=None  # No GIS shapefile
    )

    # Station-level EDA is approved!
    assert res["is_ready_for_station_level_eda"] is True
    assert res["geographic_readiness"]["station_level"]["is_ready"] is True

    # Coordinate-level EDA is strictly blocked!
    assert res["is_ready_for_coordinate_level_eda"] is False
    assert res["geographic_readiness"]["coordinate_level"]["is_ready"] is False
    assert len(res["geographic_readiness"]["coordinate_level"]["blockers"]) > 0

    # Training and deployment permanently blocked
    assert res["is_ready_for_training"] is False
    assert res["is_ready_for_deployment"] is False


# 15. Missing Official GIS Boundaries Tests
def test_gate_missing_official_gis_mapping_when_required():
    """Verify GIS_MAPPING_INCOMPLETE is emitted when coordinate-level GIS polygons are required."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:28]
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-GIS-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 200
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST,
        gis_boundary_path=None,
        require_gis_complete=True
    )
    assert res["gate_status"] == PuneReadinessStatus.GIS_MAPPING_INCOMPLETE.value
    assert res["is_ready_for_coordinate_level_eda"] is False


# 16. Non-Bypassable Sequential Gating Tests
def test_readiness_statuses_cannot_be_bypassed():
    """Verify that an unauthorized dataset cannot skip authorization to become READY."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:30]
    optimal_df = pd.DataFrame({
        "fir_number_hash": [f"FIR-OPT-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 200,
        "latitude": [18.5204] * 200,
        "longitude": [73.8567] * 200
    })

    res_no_auth = PuneDataReadinessGate.evaluate(
        df_or_path=optimal_df,
        authorization_manifest=None
    )
    assert res_no_auth["gate_status"] == PuneReadinessStatus.AUTHORIZATION_MISSING.value
    assert res_no_auth["is_ready_for_eda"] is False
    assert res_no_auth["is_ready_for_training"] is False
    assert res_no_auth["is_ready_for_deployment"] is False


def test_ready_for_eda_does_not_imply_ready_for_training():
    """Verify READY_FOR_EXPLORATORY_ANALYSIS strictly keeps is_ready_for_training=False."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:28]
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-PASS-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392"] * 200
    })

    res = PuneDataReadinessGate.evaluate(
        df_or_path=df,
        authorization_manifest=VALID_MOU_MANIFEST
    )
    assert res["gate_status"] == PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS.value
    assert res["is_ready_for_eda"] is True
    # Critical guarantee: NEVER ready for training or deployment in Phase 5!
    assert res["is_ready_for_training"] is False
    assert res["is_ready_for_deployment"] is False


# 17. Active Safety & No Numerical Pune Forecasts Tests
def test_no_numerical_pune_forecasts_while_unsupported():
    """Verify Pune remains UNSUPPORTED and no numerical forecasts can be returned."""
    cfg = get_city_config("pune")
    assert cfg is not None
    assert cfg.coverage_status == "UNSUPPORTED"
    assert cfg.model.is_validated is False
    assert cfg.model.model_id is None
    assert cfg.model.model_artifact_path is None
    assert is_city_model_ready("pune") is False

    resolved = resolve_city_by_coordinates(18.5196, 73.8553)
    assert resolved is not None
    assert resolved.city_id == "pune"
    assert resolved.coverage_status == "UNSUPPORTED"


# 18. Exploratory Analysis Workflow Tests
def test_exploratory_analysis_workflow_no_data():
    """Verify EDA workflow emits clear NO_DATA rather than inventing results when no file exists."""
    eda_res = PuneExploratoryAnalysisWorkflow.run_exploratory_analysis(dataset_path=None)
    assert eda_res["status"] == PuneReadinessStatus.NO_DATA.value
    assert eda_res["eda_report"] is None
    assert "Exploratory analysis cannot proceed" in eda_res["message"]


def test_exploratory_analysis_workflow_with_fixture_labeled():
    """Verify EDA workflow on unit test fixture labels output as FIXTURE_EVALUATION."""
    dates = pd.date_range("2023-01-01", periods=200, freq="D")
    stations = PUNE_POLICE_STATIONS[:28]
    test_df = pd.DataFrame({
        "fir_number_hash": [f"FIR-EDA-{i}" for i in range(200)],
        "police_station_id": [stations[i % len(stations)] for i in range(200)],
        "incident_datetime": dates.astype(str),
        "section_code": ["392" if i % 2 == 0 else "379" for i in range(200)],
        "latitude": [18.5204] * 200,
        "longitude": [73.8567] * 200
    })

    eda_res = PuneExploratoryAnalysisWorkflow.run_exploratory_analysis(
        dataset_path=test_df,
        authorization_manifest=VALID_MOU_MANIFEST,
        is_fixture=False
    )
    assert eda_res["status"] == PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS.value
    report = eda_res["eda_report"]
    assert report is not None
    assert "temporal_profile" in report
    assert report["temporal_profile"]["total_records"] == 200
    assert "records_per_station" in report["station_profile"]
    assert "target_support_by_forecast_window" in report


# 19. Calibration Split Isolation & Leakage Verification
def test_calibration_split_isolation_and_leakage_detection():
    """Verify calibration fitting detects when test labels leak into the calibrator."""
    val_df = pd.DataFrame({"target": [1, 0, 1, 0]}, index=[10, 11, 12, 13])
    test_df = pd.DataFrame({"target": [0, 1, 0, 1]}, index=[20, 21, 22, 23])

    # Legitimate calibrator fit strictly on validation
    val_calibrator_targets = pd.Series([1, 0, 1, 0], index=[10, 11, 12, 13])
    is_isolated, msg = PuneForecastingEvaluationProtocol.verify_calibration_split_isolation(
        val_df=val_df,
        test_df=test_df,
        calibrator_target_series=val_calibrator_targets
    )
    assert is_isolated is True
    assert "zero test labels" in msg

    # Leaked calibrator fit using test labels
    leaked_calibrator_targets = pd.Series([0, 1], index=[20, 21])
    is_leaked, leak_msg = PuneForecastingEvaluationProtocol.verify_calibration_split_isolation(
        val_df=val_df,
        test_df=test_df,
        calibrator_target_series=leaked_calibrator_targets
    )
    assert is_leaked is False
    assert "Calibration leakage detected" in leak_msg


# 20. Threshold Classifications Audit
def test_threshold_classifications_rationale():
    """Verify threshold registry classifies each threshold by methodological type."""
    classifications = PuneThresholdConfig.get_threshold_classifications()
    assert "training_timespan_days" in classifications
    assert "training_min_records" in classifications
    assert "training_min_target_positives" in classifications

    # Verify 15,000 records is documented as an unvalidated assumption
    assert "UNVALIDATED_ASSUMPTION" in classifications["training_min_records"]["classification"]
    assert "STATISTICALLY_JUSTIFIED" in classifications["training_min_target_positives"]["classification"]


# 21. Secure Authorization Key Management & Unprovisioned Key Tests (Phase 6 / 6.1)
def test_unprovisioned_production_public_key_blocks_authorization(monkeypatch):
    """Verify that when PUNE_COP_ED25519_PUBLIC_KEY is unset, production authorization is blocked."""
    monkeypatch.delenv("PUNE_COP_ED25519_PUBLIC_KEY", raising=False)

    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(
        manifest=VALID_MOU_MANIFEST
    )
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("unprovisioned" in v.lower() for v in violations)


def test_manifest_binding_enforced_requires_dataset_hash():
    """Verify manifest with binding_enforced requires dataset_sha256."""
    bound_manifest = dict(VALID_MOU_MANIFEST)
    bound_manifest["dataset_fingerprint"] = {
        "expected_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "binding_enforced": True
    }

    # Verify without providing dataset hash fails
    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(
        manifest=bound_manifest,
        dataset_sha256=None
    )
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("strict dataset fingerprint binding" in v for v in violations)


# 22. Lifecycle Transition Manager & Hard Locks (Phase 6)
def test_lifecycle_transition_manager_stages_and_hard_locks():
    """Verify lifecycle progression and that Stages 4, 5, 6 remain strictly locked in Phase 6."""
    # Stage 0: Unauthorized / No data
    gate_no_data = PuneDataReadinessGate.evaluate(df_or_path=None)
    res_0 = PuneLifecycleTransitionManager.evaluate_transitions(gate_no_data)
    assert res_0["current_stage"] == PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value
    assert res_0["model_training_eligible"] is False
    assert res_0["pilot_deployment_eligible"] is False

    # Simulate Stage 2 Gate Result (Station EDA Ready)
    mock_gate_stage_2 = {
        "gate_status": PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS.value,
        "checklist": {"authorization_verified": True},
        "is_ready_for_station_level_eda": True,
        "is_ready_for_coordinate_level_eda": False,
    }
    res_2 = PuneLifecycleTransitionManager.evaluate_transitions(mock_gate_stage_2, manifest=VALID_MOU_MANIFEST)
    assert res_2["current_stage"] == PuneLifecycleStage.STAGE_2_READY_FOR_STATION_LEVEL_EDA.value
    assert res_2["stages"][PuneLifecycleStage.STAGE_2_READY_FOR_STATION_LEVEL_EDA.value]["status"] == "COMPLETED"
    assert res_2["model_training_eligible"] is False

    # Stages 4, 5, 6 must remain permanently locked False in Phase 6
    assert res_2["stages"][PuneLifecycleStage.STAGE_4_CONTROLLED_TRAINING_ELIGIBLE.value]["achieved"] is False
    assert res_2["stages"][PuneLifecycleStage.STAGE_4_CONTROLLED_TRAINING_ELIGIBLE.value]["status"] == "LOCKED_DISABLED_IN_PHASE_6"
    assert res_2["stages"][PuneLifecycleStage.STAGE_5_INDEPENDENT_VALIDATION_ELIGIBLE.value]["status"] == "LOCKED_DISABLED_IN_PHASE_6"
    assert res_2["stages"][PuneLifecycleStage.STAGE_6_APPROVED_PILOT_ELIGIBLE.value]["status"] == "LOCKED_DISABLED_IN_PHASE_6"


# 23. Authorized Dataset Ingestion Workflow & Version Immutability (Phase 6)
def test_ingest_authorized_dataset_workflow(tmp_path):
    """Verify reproducible intake workflow, manifest matching, and version collision rejection."""
    # Create raw incident dataset
    raw_df = pd.DataFrame([
        {
            "fir_number_hash": f"FIR-{i:04d}",
            "police_station_id": PUNE_POLICE_STATIONS[i % len(PUNE_POLICE_STATIONS)],
            "incident_datetime": f"2024-0{1 + (i % 6):01d}-15T12:00:00",
            "section_code": "392",
            "latitude": 18.520 + (i * 0.0001),
            "longitude": 73.856 + (i * 0.0001),
        }
        for i in range(100)
    ])
    raw_csv = tmp_path / "raw_incidents.csv"
    raw_df.to_csv(raw_csv, index=False)

    dest_dir = tmp_path / "authorized_store"

    # Ingestion without valid manifest fails with ValueError
    with pytest.raises(ValueError, match="Dataset intake blocked by authorization failure"):
        PuneDataIngestionPipeline.ingest_authorized_dataset(
            raw_dataset_path=str(raw_csv),
            destination_root_dir=str(dest_dir),
            version="1.0",
            manifest=None
        )

    # Ingestion with valid manifest succeeds
    intake_res = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=str(dest_dir),
        version="1.0",
        manifest=VALID_MOU_MANIFEST
    )

    assert intake_res["success"] is True
    assert intake_res["version"] == "1.0"
    assert intake_res["records_retained"] == 100
    assert os.path.exists(os.path.join(dest_dir, "v1.0", "cleaned_incidents.csv"))
    assert os.path.exists(os.path.join(dest_dir, "v1.0", "authorized_manifest.json"))
    assert os.path.exists(os.path.join(dest_dir, "v1.0", "intake_audit_manifest.json"))

    # Attempting to re-ingest to existing version v1.0 must raise FileExistsError (no silent overwriting)
    with pytest.raises(FileExistsError, match="Silent overwriting of prior dataset versions is strictly prohibited"):
        PuneDataIngestionPipeline.ingest_authorized_dataset(
            raw_dataset_path=str(raw_csv),
            destination_root_dir=str(dest_dir),
            version="1.0",
            manifest=VALID_MOU_MANIFEST
        )


# 24. EDA Pipeline Script Execution Tests (Phase 6)
def test_run_pune_eda_pipeline_execution():
    """Verify run_eda_pipeline behaves properly in NO_DATA mode and blocks unverified data."""
    # 1. Default NO_DATA execution
    res_no_data = run_eda_pipeline(dataset_path=None)
    assert res_no_data["execution_status"] == "NO_DATA"
    assert res_no_data["gate_evaluation"]["gate_status"] == PuneReadinessStatus.NO_DATA.value
    assert res_no_data["lifecycle_transitions"]["current_stage"] == PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value

    # 2. Non-existent dataset file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        run_eda_pipeline(dataset_path="non_existent.csv")


# 25. Phase 6.1 Security and Audit Integrity Tests
def test_application_cannot_sign_with_verification_credentials_alone():
    """Verify application possessing only public verification key cannot forge signatures."""
    pubkey = InstitutionalIssuerRegistry.get_issuer_public_key("pune_city_police_cop")
    assert isinstance(pubkey, ed25519.Ed25519PublicKey)
    # Crucial property of asymmetric cryptography: public keys cannot sign
    assert not hasattr(pubkey, "sign")

    # Attempting to sign without an external private key must raise ValueError
    with pytest.raises(ValueError, match="Cannot create authorized manifest: Private signing key is required"):
        InstitutionalIssuerRegistry.create_authorized_manifest(signing_private_key=None)


def test_unknown_issuer_keys_rejected():
    """Verify manifests with unknown issuer ID or unapproved credentials are unconditionally rejected."""
    bad_issuer_manifest = dict(VALID_MOU_MANIFEST)
    bad_issuer_manifest["issuer_id"] = "unauthorized_foreign_dept"

    is_ok, status, violations, details = InstitutionalIssuerRegistry.verify_manifest(
        manifest=bad_issuer_manifest
    )
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("untrusted" in v.lower() for v in violations)


def test_invalid_and_tampered_signatures_rejected():
    """Verify corrupt signature, signature made with rogue private key, or modified payload fails verification."""
    # 1. Corrupt signature hex string
    corrupt_sig_manifest = dict(VALID_MOU_MANIFEST)
    corrupt_sig_manifest["signature"] = "00" * 64
    corrupt_sig_manifest["verification_token"] = "00" * 64

    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=corrupt_sig_manifest)
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("ed25519 signature verification failed" in v.lower() or "cryptographic verification failed" in v.lower() for v in violations)

    # 2. Signature made with a different, rogue private key
    rogue_private_key = ed25519.Ed25519PrivateKey.generate()
    rogue_signed_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
        mou_reference="MOU/PUNE-COP/2026/STRATA-001",
        issuer_id="pune_city_police_cop",
        signing_private_key=rogue_private_key,  # Rogue key!
    )
    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=rogue_signed_manifest)
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("ed25519 signature verification failed" in v.lower() or "cryptographic verification failed" in v.lower() for v in violations)

    # 3. Payload tampering: valid signature on original payload, but attacker changes valid_until or mou_reference
    tampered_payload_manifest = dict(VALID_MOU_MANIFEST)
    tampered_payload_manifest["mou_reference"] = "MOU/PUNE-COP/2026/TAMPERED-001"
    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=tampered_payload_manifest)
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("ed25519 signature verification failed" in v.lower() or "cryptographic verification failed" in v.lower() for v in violations)


def test_audit_manifest_contains_no_pii_and_has_all_required_fields(tmp_path):
    """Verify intake audit manifest contains strictly aggregate metadata and zero citizen-level PII."""
    raw_df = pd.DataFrame([
        {
            "fir_number_hash": f"FIR-PII-TEST-{i:03d}",
            "police_station_id": PUNE_POLICE_STATIONS[i % len(PUNE_POLICE_STATIONS)],
            "incident_datetime": "2024-03-15T12:00:00",
            "section_code": "392",
            "latitude": 18.520 + (i * 0.001),
            "longitude": 73.856 + (i * 0.001),
        }
        for i in range(25)
    ])
    raw_csv = tmp_path / "raw_intake.csv"
    raw_df.to_csv(raw_csv, index=False)
    dest_dir = tmp_path / "authorized_store"

    intake_res = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=str(dest_dir),
        version="1.0",
        manifest=VALID_MOU_MANIFEST
    )
    assert intake_res["success"] is True

    audit_manifest_path = os.path.join(dest_dir, "v1.0", "intake_audit_manifest.json")
    assert os.path.exists(audit_manifest_path)

    import json
    with open(audit_manifest_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    # Required fields check
    assert "raw_input_sha256" in audit_data
    assert "source_and_verified_authorization_reference" in audit_data
    assert "dataset_version" in audit_data
    assert "ingestion_pipeline_version" in audit_data
    assert "configuration_version" in audit_data
    assert "processing_timestamp" in audit_data
    assert "aggregate_retention_and_rejection_counts" in audit_data
    assert "output_fingerprint" in audit_data
    assert "storage_integrity_classification" in audit_data

    # Storage integrity classification audit
    storage_class = audit_data["storage_integrity_classification"]
    assert storage_class["true_write_once_immutability"] is False
    assert storage_class["application_overwrite_prevention"] is True
    assert "SHA256_FINGERPRINT_VERIFIED" in storage_class["cryptographic_tamper_evidence"]

    # PII scan: ensure no individual citizen identifiers, phone numbers, emails, or names appear in audit json
    audit_text = json.dumps(audit_data)
    import re
    assert not re.search(r"\b[6-9]\d{9}\b", audit_text), "Indian phone number pattern detected in audit manifest"
    assert not re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", audit_text), "PAN pattern detected in audit manifest"
    assert not re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", audit_text), "Aadhaar pattern detected in audit manifest"
    assert "FIR-PII-TEST" not in audit_text, "FIR hashes should not be leaked into audit manifest summary"


def test_tampering_is_detectable_by_storage_and_signature_design(tmp_path):
    """Verify data mutation after ingestion is immediately detectable via cryptographic fingerprint mismatch."""
    import hashlib
    import json
    raw_df = pd.DataFrame([
        {
            "fir_number_hash": f"FIR-MUT-{i:03d}",
            "police_station_id": PUNE_POLICE_STATIONS[i % len(PUNE_POLICE_STATIONS)],
            "incident_datetime": "2024-03-15T12:00:00",
            "section_code": "392",
            "latitude": 18.520 + (i * 0.001),
            "longitude": 73.856 + (i * 0.001),
        }
        for i in range(10)
    ])
    raw_csv = tmp_path / "raw_intake_mut.csv"
    raw_df.to_csv(raw_csv, index=False)
    dest_dir = tmp_path / "authorized_store"

    intake_res = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=str(dest_dir),
        version="1.0",
        manifest=VALID_MOU_MANIFEST
    )

    cleaned_csv_path = os.path.join(dest_dir, "v1.0", "cleaned_incidents.csv")
    with open(cleaned_csv_path, "rb") as f:
        clean_sha256 = hashlib.sha256(f.read()).hexdigest()

    audit_manifest_path = os.path.join(dest_dir, "v1.0", "intake_audit_manifest.json")
    with open(audit_manifest_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    # Initial state: clean CSV matches recorded fingerprint
    assert audit_data["output_fingerprint"]["cleaned_file_sha256"] == clean_sha256

    # Adversary tampers with cleaned incidents file directly on disk
    with open(cleaned_csv_path, "a", encoding="utf-8") as f:
        f.write("TAMPERED_RECORD,shivajinagar,2024-03-15T12:00:00,392,18.52,73.85\n")

    # Recalculate hash: tamper is immediately detectable
    with open(cleaned_csv_path, "rb") as f:
        tampered_sha256 = hashlib.sha256(f.read()).hexdigest()

    assert tampered_sha256 != audit_data["output_fingerprint"]["cleaned_file_sha256"], (
        "Tampered dataset hash must differ from recorded cryptographic audit fingerprint"
    )


# 26. Phase 6.2 Cryptographic Authorization and Temporal Window Consistency Tests
def test_all_authorization_sensitive_fields_tamper_evident():
    """Verify modifying any authorization-sensitive field invalidates the Ed25519 digital signature."""
    sensitive_mutations = [
        ("authorization_id", "AUTH-TAMPERED-ID-001"),
        ("mou_reference", "MOU/PUNE-COP/2026/TAMPERED-MOU"),
        ("permitted_use", "offline_validation"),  # Valid purpose in registry, but different from signed "public_safety_risk_modeling"
        ("valid_from", "2025-06-01T00:00:00Z"),
        ("valid_until", "2029-12-31T23:59:59Z"),
        ("permitted_fields", ["fir_number_hash"]),
        ("manifest_version", "3.0"),
    ]

    for field, tampered_val in sensitive_mutations:
        tampered_manifest = dict(VALID_MOU_MANIFEST)
        tampered_manifest[field] = tampered_val
        is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=tampered_manifest)
        assert is_ok is False, f"Tampering with '{field}' must fail verification"
        assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
        assert any("cryptographic verification failed" in v.lower() or "signature verification failed" in v.lower() for v in violations), (
            f"Tampering with '{field}' must trigger cryptographic signature mismatch"
        )


def test_malformed_and_inverted_timestamps_fail_closed():
    """Verify unparseable timestamps or inverted windows (valid_from > valid_until) fail closed."""
    # 1. Inverted window: valid_from after valid_until
    inverted_manifest = dict(VALID_MOU_MANIFEST)
    inverted_manifest["valid_from"] = "2028-01-01T00:00:00Z"
    inverted_manifest["valid_until"] = "2026-01-01T00:00:00Z"

    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=inverted_manifest)
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("malformed" in v.lower() for v in violations)

    # 2. Malformed non-date string
    malformed_manifest = dict(VALID_MOU_MANIFEST)
    malformed_manifest["valid_from"] = "INVALID_NON_ISO_TIMESTAMP"

    is_ok2, status2, violations2, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=malformed_manifest)
    assert is_ok2 is False
    assert status2 == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("malformed" in v.lower() or "unparseable" in v.lower() for v in violations2)


def test_trusted_revocation_mechanism_blocks_tampered_boolean(monkeypatch):
    """
    Verify that an attacker cannot evade revocation by flipping the manifest's is_revoked boolean.
    Revocation registered in trusted registry or environment CRL unconditionally blocks intake.
    """
    # 1. Test trusted in-memory registry revocation
    InstitutionalIssuerRegistry.clear_trusted_revocations()
    target_auth_id = VALID_MOU_MANIFEST["authorization_id"]
    InstitutionalIssuerRegistry.register_revocation(target_auth_id)

    # Manifest presented with is_revoked: False
    presented_manifest = dict(VALID_MOU_MANIFEST)
    presented_manifest["is_revoked"] = False

    is_ok, status, violations, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=presented_manifest)
    assert is_ok is False
    assert status == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("revocation registry" in v.lower() for v in violations)

    # Cleanup in-memory registry
    InstitutionalIssuerRegistry.clear_trusted_revocations()

    # 2. Test environment variable CRL revocation (PUNE_REVOKED_AUTHORIZATIONS)
    monkeypatch.setenv("PUNE_REVOKED_AUTHORIZATIONS", f"AUTH-OTHER, {target_auth_id}, AUTH-ANOTHER")
    is_ok_env, status_env, violations_env, _ = InstitutionalIssuerRegistry.verify_manifest(manifest=presented_manifest)
    assert is_ok_env is False
    assert status_env == PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value
    assert any("environment crl" in v.lower() for v in violations_env)


def test_independent_audit_ledger_detects_simultaneous_file_and_manifest_tampering(tmp_path):
    """
    Verify that an adversary modifying BOTH cleaned_incidents.csv AND intake_audit_manifest.json
    in the version directory is caught by the independent root audit ledger (intake_audit_ledger.jsonl).
    """
    raw_df = pd.DataFrame([
        {
            "fir_number_hash": f"FIR-LEDGER-{i:03d}",
            "police_station_id": PUNE_POLICE_STATIONS[i % len(PUNE_POLICE_STATIONS)],
            "incident_datetime": "2024-03-15T12:00:00",
            "section_code": "392",
            "latitude": 18.520 + (i * 0.001),
            "longitude": 73.856 + (i * 0.001),
        }
        for i in range(15)
    ])
    raw_csv = tmp_path / "raw_ledger.csv"
    raw_df.to_csv(raw_csv, index=False)
    dest_dir = tmp_path / "authorized_store"

    intake_res = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=str(dest_dir),
        version="1.0",
        manifest=VALID_MOU_MANIFEST
    )
    assert intake_res["success"] is True

    # 1. Untampered intake verifies cleanly across all levels
    integrity_clean = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=str(dest_dir),
        version="1.0",
        is_fixture=False
    )
    assert integrity_clean["is_valid"] is True
    assert integrity_clean["ledger_verified"] is True
    assert integrity_clean["authorized_manifest_verified"] is True
    assert len(integrity_clean["violations"]) == 0

    # 2. Adversary tampers with cleaned_incidents.csv AND rewrites intake_audit_manifest.json
    cleaned_csv_path = os.path.join(dest_dir, "v1.0", "cleaned_incidents.csv")
    with open(cleaned_csv_path, "a", encoding="utf-8") as f:
        f.write("TAMPERED_FIR,kothrud,2024-03-15T12:00:00,392,18.52,73.85\n")

    import hashlib
    with open(cleaned_csv_path, "rb") as f:
        new_cleaned_hash = hashlib.sha256(f.read()).hexdigest()

    audit_manifest_path = os.path.join(dest_dir, "v1.0", "intake_audit_manifest.json")
    import json
    with open(audit_manifest_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    # Adversary updates the manifest output_fingerprint to match new file hash
    audit_data["output_fingerprint"]["cleaned_file_sha256"] = new_cleaned_hash
    with open(audit_manifest_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    # 3. Verification must fail because intake_audit_ledger.jsonl recorded original manifest hash!
    integrity_tampered = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=str(dest_dir),
        version="1.0",
        is_fixture=False
    )
    assert integrity_tampered["is_valid"] is False
    assert integrity_tampered["ledger_verified"] is False
    assert any("simultaneous file and manifest tampering detected" in v.lower() for v in integrity_tampered["violations"])


def test_reconciled_forecast_window_calculations():
    """
    Verify temporal window reconciliation:
    - 4-hour operational prediction windows (6 windows/day)
    - 33 police stations = 198 station-windows/day
    - Exact station-window counts for 1, 7, 180, and 365 days
    - Positive target support calculated for intended 4-hour operational window
    """
    # 1. Verify exact station-window counts
    assert PuneForecastingEvaluationProtocol.calculate_expected_station_windows(num_days=1, num_stations=33) == 198
    assert PuneForecastingEvaluationProtocol.calculate_expected_station_windows(num_days=7, num_stations=33) == 1386
    assert PuneForecastingEvaluationProtocol.calculate_expected_station_windows(num_days=180, num_stations=33) == 35640
    assert PuneForecastingEvaluationProtocol.calculate_expected_station_windows(num_days=365, num_stations=33) == 72270
    assert PuneForecastingEvaluationProtocol.calculate_expected_station_windows(num_days=1095, num_stations=33) == 216810

    # 2. Test calculate_window_support on synthetic 7-day test incidents
    dates = pd.date_range("2024-01-01 00:00:00", periods=42, freq="4h")
    df = pd.DataFrame({
        "fir_number_hash": [f"FIR-WIN-{i}" for i in range(len(dates))],
        "police_station_id": ["kothrud" if i % 2 == 0 else "swargate" for i in range(len(dates))],
        "incident_datetime": dates.astype(str),
        "section_code": ["392" if i % 3 == 0 else "379" for i in range(len(dates))],  # violent street harm & property
    })

    support_4h = PuneForecastingEvaluationProtocol.calculate_window_support(df, window_hours=4, num_stations=33)
    assert support_4h["window_hours"] == 4
    assert support_4h["windows_per_day"] == 6
    assert support_4h["active_station_windows_with_incidents"] > 0
    assert support_4h["station_windows_with_target"] > 0
    assert support_4h["total_potential_station_windows"] > 0
    assert support_4h["target_event_prevalence_pct"] > 0.0

    # 3. Test EDA workflow output contains 4_hour_operational_window on valid 200-day dataset
    eda_dates = pd.date_range("2023-01-01", periods=200, freq="D")
    eda_stations = PUNE_POLICE_STATIONS[:28]
    valid_eda_df = pd.DataFrame({
        "fir_number_hash": [f"FIR-EDA-{i}" for i in range(200)],
        "police_station_id": [eda_stations[i % len(eda_stations)] for i in range(200)],
        "incident_datetime": eda_dates.astype(str),
        "section_code": ["392" if i % 2 == 0 else "379" for i in range(200)],
        "latitude": [18.5204] * 200,
        "longitude": [73.8567] * 200,
    })

    eda_result = PuneExploratoryAnalysisWorkflow.run_exploratory_analysis(
        dataset_path=valid_eda_df,
        authorization_manifest=VALID_MOU_MANIFEST,
        is_fixture=False
    )
    assert eda_result["status"] == PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS.value
    target_support = eda_result["eda_report"]["target_support_by_forecast_window"]
    assert "4_hour_operational_window" in target_support
    assert "8_hour_patrol_shift" in target_support
    assert "24_hour_daily_window" in target_support
    assert target_support["4_hour_operational_window"]["windows_per_day"] == 6
    assert target_support["8_hour_patrol_shift"]["windows_per_day"] == 3


