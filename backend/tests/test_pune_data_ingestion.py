"""
Comprehensive Test Suite for Pune Data Acquisition & Ingestion Pipeline (Phase 2).

Verifies all 8 required dimensions:
1. Valid and invalid schemas
2. Duplicate records (non-PII deduplication)
3. Missing and unparseable timestamps
4. Invalid station identifiers and alias normalization
5. Prohibited PII rejection (DPDPA 2023 compliance)
6. Category mapping and unmapped fallbacks
7. Chronological anti-leakage splitting
8. Empty and insufficient datasets
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
    PIIViolationError,
    SchemaValidationError,
    InsufficientDataError,
    PUNE_LAT_BOUNDS,
    PUNE_LON_BOUNDS,
)
from backend.services.pune_data_readiness import PUNE_POLICE_STATIONS


# 1. Valid Schema & Clean Ingestion Tests
def test_valid_cctns_fixture_ingestion_and_audit():
    """Verify that a compliant CCTNS fixture ingests completely and produces a detailed audit report."""
    pipeline = PuneDataIngestionPipeline()
    df = pd.read_csv("fixtures/sample_pune_cctns_fixture.csv", comment="#")

    cleaned_df, report = pipeline.process_records(df, source_name="pune_cctns_test_fixture")

    assert len(cleaned_df) == 20
    assert report["records_summary"]["total_records_read"] == 20
    assert report["records_summary"]["valid_records_retained"] == 20
    assert report["records_summary"]["total_records_dropped"] == 0
    assert report["records_summary"]["retention_rate_pct"] == 100.0

    # Verify audit sections
    assert report["city_id"] == "pune"
    assert "source_provenance" in report
    assert report["source_provenance"]["jurisdiction"] == "Pune City Police Commissionerate"
    assert report["source_provenance"]["pii_compliance_status"] == "CERTIFIED_NON_PII"

    # Verify spatial and temporal metrics
    assert report["spatial_coverage"]["coordinate_completeness_pct"] == 100.0
    assert report["spatial_coverage"]["records_with_coordinates"] == 20
    assert report["stations_represented_count"] == 20
    assert report["temporal_coverage"]["timespan_days"] > 400

    # Ensure required columns exist in output
    expected_cols = [
        "dedup_key", "fir_number_hash", "police_station_id_normalized",
        "incident_datetime_normalized", "incident_datetime_iso", "section_code",
        "harm_tier", "latitude_clean", "longitude_clean", "has_valid_coordinates"
    ]
    for col in expected_cols:
        assert col in cleaned_df.columns


# 2. Invalid Schema Tests
def test_missing_mandatory_schema_columns():
    """Verify missing mandatory columns raise SchemaValidationError with clear error messages."""
    pipeline = PuneDataIngestionPipeline()

    # Missing fir_number_hash and section_code
    bad_df = pd.DataFrame({
        "police_station_id": ["shivajinagar"],
        "incident_datetime": ["2024-01-01T10:00:00"]
    })

    with pytest.raises(SchemaValidationError) as exc_info:
        pipeline.process_records(bad_df)
    err_str = str(exc_info.value)
    assert "fir_number_hash" in err_str
    assert "section_code" in err_str


# 3. Duplicate Records & Deduplication Tests
def test_non_pii_deduplication():
    """Verify duplicate records are dropped on (fir_number_hash, station, datetime)."""
    pipeline = PuneDataIngestionPipeline()

    raw_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-DUP-01",
            "police_station_id": "swargate",
            "incident_datetime": "2024-02-01T12:00:00",
            "section_code": "379",
            "latitude": 18.5018,
            "longitude": 73.8580
        },
        {
            # Exact duplicate
            "fir_number_hash": "FIR-DUP-01",
            "police_station_id": "swargate",
            "incident_datetime": "2024-02-01T12:00:00",
            "section_code": "379",
            "latitude": 18.5018,
            "longitude": 73.8580
        },
        {
            # Different time -> distinct incident
            "fir_number_hash": "FIR-DUP-01",
            "police_station_id": "swargate",
            "incident_datetime": "2024-02-01T15:30:00",
            "section_code": "379",
            "latitude": 18.5018,
            "longitude": 73.8580
        }
    ])

    cleaned_df, report = pipeline.process_records(raw_data)
    assert len(cleaned_df) == 2
    assert report["records_summary"]["total_records_read"] == 3
    assert report["records_summary"]["valid_records_retained"] == 2
    assert report["drop_reasons_breakdown"]["duplicate_records"] == 1


# 4. Missing & Invalid Timestamps Tests
def test_missing_and_invalid_timestamps_handling():
    """Verify records with missing or malformed timestamps are cleanly dropped and counted."""
    pipeline = PuneDataIngestionPipeline()

    raw_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-TIME-01",
            "police_station_id": "kothrud",
            "incident_datetime": "2024-01-15T10:00:00",
            "section_code": "379"
        },
        {
            "fir_number_hash": "FIR-TIME-02",
            "police_station_id": "kothrud",
            "incident_datetime": None,  # Null datetime
            "section_code": "379"
        },
        {
            "fir_number_hash": "FIR-TIME-03",
            "police_station_id": "kothrud",
            "incident_datetime": "INVALID_TIMESTAMP_STRING",  # Unparseable
            "section_code": "379"
        }
    ])

    cleaned_df, report = pipeline.process_records(raw_data)
    assert len(cleaned_df) == 1
    assert cleaned_df.iloc[0]["fir_number_hash"] == "FIR-TIME-01"
    assert report["drop_reasons_breakdown"]["invalid_or_missing_timestamp"] == 2


# 5. Invalid Police Station Identifiers & Alias Tests
def test_invalid_police_station_rejection():
    """Verify out-of-jurisdiction stations are rejected and never silently mapped."""
    pipeline = PuneDataIngestionPipeline()

    raw_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-STA-01",
            "police_station_id": "hadapsar",  # Valid
            "incident_datetime": "2024-01-10T12:00:00",
            "section_code": "380"
        },
        {
            "fir_number_hash": "FIR-STA-02",
            "police_station_id": "chicago_central_district_001",  # Foreign station
            "incident_datetime": "2024-01-10T12:00:00",
            "section_code": "380"
        },
        {
            "fir_number_hash": "FIR-STA-03",
            "police_station_id": "unknown_police_stn_xyz",  # Unknown station
            "incident_datetime": "2024-01-10T12:00:00",
            "section_code": "380"
        }
    ])

    cleaned_df, report = pipeline.process_records(raw_data)
    assert len(cleaned_df) == 1
    assert cleaned_df.iloc[0]["police_station_id_normalized"] == "hadapsar"
    assert report["drop_reasons_breakdown"]["invalid_or_unmapped_station"] == 2


def test_police_station_alias_normalization():
    """Verify station aliases and suffixes are normalized to standard identifiers."""
    aliases = [
        ("deccan", "deccan_gymkhana"),
        ("Deccan Gymkhana Police Station", "deccan_gymkhana"),
        ("chaturshrungi", "chaturshringi"),
        ("cantonment", "lashkar_cantonment"),
        ("sahakar nagar", "sahakar_nagar"),
        ("sinhgad road", "sinhagad_road"),
        ("warje malwadi ps", "warje_malwadi"),
    ]

    for raw, expected in aliases:
        norm = PuneDataIngestionPipeline.normalize_station_id(raw)
        assert norm == expected, f"Failed to normalize '{raw}' -> expected '{expected}', got '{norm}'"


# 6. Prohibited PII Rejection Tests (DPDPA 2023)
def test_prohibited_pii_columns_rejection():
    """Verify dataset containing citizen PII columns raises PIIViolationError."""
    pipeline = PuneDataIngestionPipeline()

    pii_columns = [
        "victim_name", "complainant_name", "accused_name", "phone_number",
        "aadhaar_number", "exact_residential_address", "caste", "religion"
    ]

    for pii_col in pii_columns:
        pii_df = pd.DataFrame([{
            "fir_number_hash": "FIR-PII-01",
            "police_station_id": "shivajinagar",
            "incident_datetime": "2024-01-01T10:00:00",
            "section_code": "379",
            pii_col: "Sensitive Citizen Data"
        }])

        with pytest.raises(PIIViolationError) as exc_info:
            pipeline.process_records(pii_df)
        assert "DPDPA 2023" in str(exc_info.value)
        assert pii_col in str(exc_info.value).lower()


def test_prohibited_pii_value_detection():
    """Verify phone number patterns in free-text columns are detected."""
    pipeline = PuneDataIngestionPipeline()

    phone_df = pd.DataFrame([{
        "fir_number_hash": "FIR-PHONE-01",
        "police_station_id": "swargate",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "379",
        "place_of_occurrence": "Contact complainant at 9822012345 near market"
    }])

    with pytest.raises(PIIViolationError) as exc_info:
        pipeline.process_records(phone_df)
    assert "Phone number pattern detected" in str(exc_info.value)


# 7. Category Mapping & Unmapped Fallbacks
def test_category_mapping_ipc_bns():
    """Verify IPC and BNS sections map to operational harm tiers or fallback gracefully."""
    pipeline = PuneDataIngestionPipeline()

    test_cases = pd.DataFrame([
        {"fir_number_hash": "H1", "police_station_id": "bundgarden", "incident_datetime": "2024-01-01T01:00:00", "section_code": "302"},
        {"fir_number_hash": "H2", "police_station_id": "bundgarden", "incident_datetime": "2024-01-01T02:00:00", "section_code": "392"},
        {"fir_number_hash": "H3", "police_station_id": "bundgarden", "incident_datetime": "2024-01-01T03:00:00", "section_code": "379"},
        {"fir_number_hash": "H4", "police_station_id": "bundgarden", "incident_datetime": "2024-01-01T04:00:00", "section_code": "147"},
        {"fir_number_hash": "H5", "police_station_id": "bundgarden", "incident_datetime": "2024-01-01T05:00:00", "section_code": "UNKNOWN_CUSTOM_SEC"},
    ])

    cleaned_df, report = pipeline.process_records(test_cases)
    assert len(cleaned_df) == 5

    tier_map = dict(zip(cleaned_df["section_code"], cleaned_df["harm_tier"]))
    assert tier_map["302"] == "violent_street_harm"
    assert tier_map["392"] == "violent_street_harm"
    assert tier_map["379"] == "property_harm"
    assert tier_map["147"] == "public_disorder"
    assert tier_map["UNKNOWN_CUSTOM_SEC"] == "other_cognizable"

    assert report["unmapped_categories_count"] == 1


# 8. Chronological Leakage & Anti-Lookahead Tests
def test_chronological_splits_zero_leakage():
    """Verify chronological split strictly guarantees max(train) < min(val) < min(test)."""
    # Create 100 consecutive chronological incidents
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    times = [base_time + timedelta(hours=i * 6) for i in range(100)]

    df = pd.DataFrame({
        "incident_datetime_normalized": times,
        "fir_number_hash": [f"FIR-CHRONO-{i}" for i in range(100)],
        "police_station_id_normalized": ["kothrud"] * 100
    })

    split = PuneDataIngestionPipeline.create_chronological_splits(
        df,
        time_col="incident_datetime_normalized",
        train_frac=0.65,
        val_frac=0.15,
        test_frac=0.20
    )

    assert split["zero_leakage_verified"] is True
    assert split["split_metrics"]["temporal_leakage_detected"] is False

    train = split["train_df"]
    val = split["val_df"]
    test = split["test_df"]

    assert len(train) == 65
    assert len(val) == 15
    assert len(test) == 20

    t_train_max = train["incident_datetime_normalized"].max()
    t_val_min = val["incident_datetime_normalized"].min()
    t_val_max = val["incident_datetime_normalized"].max()
    t_test_min = test["incident_datetime_normalized"].min()

    assert t_train_max < t_val_min
    assert t_val_max < t_test_min


def test_chronological_split_detects_leakage():
    """Verify split detects and flags when time distributions overlap."""
    # Data with identical timestamps across boundary
    times = [datetime(2023, 1, 1, 10, 0, 0)] * 10
    df = pd.DataFrame({
        "incident_datetime_normalized": times,
        "fir_number_hash": [f"FIR-OVL-{i}" for i in range(10)]
    })

    split = PuneDataIngestionPipeline.create_chronological_splits(df)
    assert split["zero_leakage_verified"] is False
    assert split["split_metrics"]["temporal_leakage_detected"] is True


# 9. Empty and Insufficient Datasets Tests
def test_empty_dataset_rejection():
    """Verify empty dataset raises InsufficientDataError."""
    pipeline = PuneDataIngestionPipeline()
    empty_df = pd.DataFrame()

    with pytest.raises(InsufficientDataError):
        pipeline.process_records(empty_df)


def test_insufficient_volume_flagging():
    """Verify dataset with < 500 records is flagged as INSUFFICIENT_VOLUME."""
    pipeline = PuneDataIngestionPipeline()
    small_df = pd.read_csv("fixtures/sample_pune_cctns_fixture.csv", comment="#")

    cleaned_df, report = pipeline.process_records(small_df)
    assert report["operational_readiness"]["is_sufficient_for_forecasting"] is False
    assert report["operational_readiness"]["status"] == "INSUFFICIENT_VOLUME"
    assert "UNSUPPORTED" in report["operational_readiness"]["active_safety_warning"]


# 10. Coordinate Handling & Zero Imputation Tests
def test_coordinate_handling_zero_imputation():
    """Verify coordinates are never invented and out-of-bounds coords are reset to NaN."""
    pipeline = PuneDataIngestionPipeline()

    raw_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-GEO-01",
            "police_station_id": "shivajinagar",
            "incident_datetime": "2024-01-01T10:00:00",
            "section_code": "379",
            "latitude": 18.5284,  # Valid Pune coordinate
            "longitude": 73.8425
        },
        {
            "fir_number_hash": "FIR-GEO-02",
            "police_station_id": "shivajinagar",
            "incident_datetime": "2024-01-01T11:00:00",
            "section_code": "379",
            "latitude": None,     # Missing coordinate
            "longitude": None
        },
        {
            "fir_number_hash": "FIR-GEO-03",
            "police_station_id": "shivajinagar",
            "incident_datetime": "2024-01-01T12:00:00",
            "section_code": "379",
            "latitude": 41.8781,  # Chicago coordinate (out of Pune bounds)
            "longitude": -87.6298
        }
    ])

    cleaned_df, report = pipeline.process_records(raw_data)
    assert len(cleaned_df) == 3

    # Row 1: Valid
    row1 = cleaned_df[cleaned_df["fir_number_hash"] == "FIR-GEO-01"].iloc[0]
    assert bool(row1["has_valid_coordinates"]) is True
    assert row1["latitude_clean"] == 18.5284

    # Row 2: Missing -> preserved as NaN, NOT synthesized!
    row2 = cleaned_df[cleaned_df["fir_number_hash"] == "FIR-GEO-02"].iloc[0]
    assert bool(row2["has_valid_coordinates"]) is False
    assert np.isnan(row2["latitude_clean"])

    # Row 3: Out-of-bounds -> reset to NaN, NOT accepted!
    row3 = cleaned_df[cleaned_df["fir_number_hash"] == "FIR-GEO-03"].iloc[0]
    assert bool(row3["has_valid_coordinates"]) is False
    assert np.isnan(row3["latitude_clean"])

    assert report["spatial_coverage"]["out_of_bounds_coordinates_count"] == 1
    assert report["spatial_coverage"]["records_with_coordinates"] == 1


# 11. Malformed Fixture Processing
def test_malformed_fixture_pipeline_run():
    """Verify malformed fixture cleanly drops invalid rows and generates audit breakdown."""
    pipeline = PuneDataIngestionPipeline()
    malformed_df = pd.read_csv("fixtures/malformed_pune_cctns_fixture.csv", comment="#")

    cleaned_df, report = pipeline.process_records(malformed_df, source_name="malformed_fixture")

    # In malformed fixture:
    # 8 total rows read
    # 1 duplicate (PN-MAL-01)
    # 1 invalid station (PN-MAL-02)
    # 1 missing timestamp (PN-MAL-03)
    # 1 unparseable timestamp (PN-MAL-04)
    # 4 valid rows retained: PN-MAL-01 (1st), PN-MAL-05, PN-MAL-06, PN-MAL-07
    assert len(cleaned_df) == 4
    assert report["records_summary"]["total_records_read"] == 8
    assert report["records_summary"]["valid_records_retained"] == 4
    assert report["records_summary"]["total_records_dropped"] == 4

    assert report["drop_reasons_breakdown"]["duplicate_records"] == 1
    assert report["drop_reasons_breakdown"]["invalid_or_unmapped_station"] == 1
    assert report["drop_reasons_breakdown"]["invalid_or_missing_timestamp"] == 2


# ---------------- PHASE 3 ADVANCED AUDIT TESTS ----------------

# 12. Deduplication Edge Cases (Step 2)
def test_repeated_firs_across_stations_audit():
    """Verify detection of Zero FIR cross-station transfers where same FIR is logged at 2 stations."""
    pipeline = PuneDataIngestionPipeline()
    transfer_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-TRANS-01",
            "police_station_id": "shivajinagar",  # Station A
            "incident_datetime": "2024-03-01T10:00:00",
            "section_code": "379"
        },
        {
            "fir_number_hash": "FIR-TRANS-01",
            "police_station_id": "swargate",      # Transferred to Station B
            "incident_datetime": "2024-03-01T10:00:00",
            "section_code": "379"
        }
    ])

    cleaned_df, report = pipeline.process_records(transfer_data)
    # Both records have different stations so different dedup keys in incident mode
    assert len(cleaned_df) == 2
    # But deduplication_audit correctly flags cross-station transfer
    assert report["deduplication_audit"]["cross_station_repeated_fir_count"] == 1
    assert "FIR-TRANS-01" in report["deduplication_audit"]["cross_station_firs"]


def test_corrected_timestamp_repeated_fir_audit():
    """Verify detection of amended/corrected timestamps on the same FIR."""
    pipeline = PuneDataIngestionPipeline()
    amended_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-AMEND-01",
            "police_station_id": "kothrud",
            "incident_datetime": "2024-03-01T10:00:00",  # Initial filing time
            "section_code": "457"
        },
        {
            "fir_number_hash": "FIR-AMEND-01",
            "police_station_id": "kothrud",
            "incident_datetime": "2024-03-01T14:30:00",  # Corrected occurrence time
            "section_code": "457"
        }
    ])

    cleaned_df, report = pipeline.process_records(amended_data)
    assert len(cleaned_df) == 2
    assert report["deduplication_audit"]["corrected_timestamp_repeated_fir_count"] == 1


def test_idempotent_repeated_ingestion():
    """Verify that repeatedly ingesting identical batches produces identical deterministic outputs."""
    pipeline = PuneDataIngestionPipeline()
    df = pd.read_csv("fixtures/sample_pune_cctns_fixture.csv", comment="#")

    cleaned_1, report_1 = pipeline.process_records(df)
    cleaned_2, report_2 = pipeline.process_records(df)

    assert len(cleaned_1) == len(cleaned_2)
    assert list(cleaned_1["dedup_key"]) == list(cleaned_2["dedup_key"])
    assert report_1["records_summary"] == report_2["records_summary"]
    assert report_1["deduplication_audit"]["idempotent_ingestion_verified"] is True


def test_dedup_mode_incident_vs_offence():
    """Verify that dedup_mode='offence' retains multiple penal sections for the same FIR."""
    pipeline = PuneDataIngestionPipeline()
    multi_offence_data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-MULTI-01",
            "police_station_id": "hadapsar",
            "incident_datetime": "2024-02-10T15:00:00",
            "section_code": "379"  # Theft
        },
        {
            "fir_number_hash": "FIR-MULTI-01",
            "police_station_id": "hadapsar",
            "incident_datetime": "2024-02-10T15:00:00",
            "section_code": "326"  # Grievous hurt in same event
        }
    ])

    # Incident mode collapses multiple sections of same FIR
    cleaned_inc, _ = pipeline.process_records(multi_offence_data, dedup_mode="incident")
    assert len(cleaned_inc) == 1

    # Offence mode preserves distinct penal sections
    cleaned_off, _ = pipeline.process_records(multi_offence_data, dedup_mode="offence")
    assert len(cleaned_off) == 2


def test_zero_pii_in_dedup_signature():
    """Verify dedup_key is a 64-hex SHA-256 hash containing zero cleartext personal identifiers."""
    pipeline = PuneDataIngestionPipeline()
    data = pd.DataFrame([{
        "fir_number_hash": "FIR-HASH-SECURE",
        "police_station_id": "deccan_gymkhana",
        "incident_datetime": "2024-01-01T12:00:00",
        "section_code": "379"
    }])

    cleaned, _ = pipeline.process_records(data)
    key = cleaned.iloc[0]["dedup_key"]
    assert len(key) == 64  # Full 256-bit SHA-256 hex string
    assert all(c in "0123456789abcdef" for c in key)


# 13. Privacy Audit Edge Cases (Step 3)
def test_email_and_pan_pattern_pii_rejection():
    """Verify email address and PAN card patterns in free text trigger PIIViolationError."""
    pipeline = PuneDataIngestionPipeline()

    email_df = pd.DataFrame([{
        "fir_number_hash": "FIR-PII-EMAIL",
        "police_station_id": "faraskhana",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "379",
        "place_of_occurrence": "Contact officer at test.cop@mahapolice.gov.in"
    }])
    with pytest.raises(PIIViolationError) as exc_info:
        pipeline.process_records(email_df)
    assert "Email address pattern detected" in str(exc_info.value)

    pan_df = pd.DataFrame([{
        "fir_number_hash": "FIR-PII-PAN",
        "police_station_id": "faraskhana",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "379",
        "place_of_occurrence": "Found PAN card ABCDE1234F at spot"
    }])
    with pytest.raises(PIIViolationError) as exc_info:
        pipeline.process_records(pan_df)
    assert "PAN card pattern detected" in str(exc_info.value)


def test_pii_detection_scans_beyond_row_100():
    """Verify PII detection scans the entire dataset, catching PII occurring after row 100."""
    pipeline = PuneDataIngestionPipeline()

    rows = []
    for i in range(150):
        row = {
            "fir_number_hash": f"FIR-SCAN-{i}",
            "police_station_id": "swargate",
            "incident_datetime": f"2024-01-01T{10 + (i // 60):02d}:{i % 60:02d}:00",
            "section_code": "379",
            "place_of_occurrence": "Standard location description"
        }
        if i == 145:  # Row 145 contains a phone number
            row["place_of_occurrence"] = "Informant mobile number 9890123456"
        rows.append(row)

    df = pd.DataFrame(rows)
    with pytest.raises(PIIViolationError) as exc_info:
        pipeline.process_records(df)
    assert "Phone number pattern detected" in str(exc_info.value)


def test_sanitized_pii_exception_does_not_leak_values():
    """Verify exception messages and logs do not print the sensitive value."""
    pipeline = PuneDataIngestionPipeline()
    secret_number = "9823099999"
    df = pd.DataFrame([{
        "fir_number_hash": "FIR-SAFE-01",
        "police_station_id": "bundgarden",
        "incident_datetime": "2024-01-01T10:00:00",
        "section_code": "379",
        "place_of_occurrence": f"Call {secret_number} for inquiry"
    }])

    with pytest.raises(PIIViolationError) as exc_info:
        pipeline.process_records(df)

    err_msg = str(exc_info.value)
    # The error message must alert to the violation without repeating the private phone number!
    assert secret_number not in err_msg
    assert "Phone number pattern detected" in err_msg


def test_additional_pii_column_names_rejected():
    """Verify expanded PII column names like contact_number and email_id are rejected."""
    pipeline = PuneDataIngestionPipeline()
    for col in ["contact_number", "email_id", "suspect_name", "aadhaar_no"]:
        df = pd.DataFrame([{
            "fir_number_hash": "FIR-01",
            "police_station_id": "swargate",
            "incident_datetime": "2024-01-01T10:00:00",
            "section_code": "379",
            col: "data"
        }])
        with pytest.raises(PIIViolationError) as exc_info:
            pipeline.process_records(df)
        assert col in str(exc_info.value).lower()


# 14. Police Station Registry & Transliteration Audit (Step 4)
def test_station_verification_audit_and_transliteration_alias():
    """Verify that wanawadi normalizes to wanowrie and station verification audit is populated."""
    pipeline = PuneDataIngestionPipeline()
    data = pd.DataFrame([
        {
            "fir_number_hash": "FIR-ST-01",
            "police_station_id": "wanawadi",  # Transliteration variant
            "incident_datetime": "2024-01-01T10:00:00",
            "section_code": "379"
        },
        {
            "fir_number_hash": "FIR-ST-02",
            "police_station_id": "pashan",     # Recent bifurcation
            "incident_datetime": "2024-01-01T11:00:00",
            "section_code": "379"
        }
    ])

    cleaned, report = pipeline.process_records(data)
    assert len(cleaned) == 2
    # wanawadi alias normalizes to wanowrie
    assert cleaned.iloc[0]["police_station_id_normalized"] == "wanowrie"
    assert cleaned.iloc[1]["police_station_id_normalized"] == "pashan"

    # Verify audit of verified core vs bifurcated
    audit = report["station_verification_audit"]
    assert audit["verified_core_station_records"] == 1  # wanowrie is core
    assert audit["unverified_or_bifurcated_station_records"] == 1  # pashan is recent bifurcation
    assert "pashan" in audit["unverified_stations_present"]


# 15. Temporal Anti-Leakage Advanced Audit (Step 5)
def test_cross_split_fir_leakage_detection():
    """Verify that the same FIR present across train and test splits is flagged as cross-split leakage."""
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "incident_datetime_normalized": dates,
        "fir_number_hash": ["FIR-1", "FIR-2", "FIR-3", "FIR-4", "FIR-5", "FIR-6", "FIR-7", "FIR-8", "FIR-9", "FIR-1"],  # FIR-1 repeated in train and test!
        "police_station_id_normalized": ["kothrud"] * 10
    })

    split = PuneDataIngestionPipeline.create_chronological_splits(df, train_frac=0.6, val_frac=0.2, test_frac=0.2)
    assert split["split_metrics"]["cross_split_fir_leakage_detected"] is True
    assert split["zero_leakage_verified"] is False


def test_enforce_clean_boundaries_on_identical_split_timestamps():
    """Verify enforce_clean_boundaries cleanly handles multiple events at split boundary timestamp."""
    # Rows 5, 6, 7 have identical timestamp
    base = datetime(2023, 1, 1, 0, 0, 0)
    times = [base + timedelta(hours=i) for i in [0, 1, 2, 3, 4, 5, 5, 5, 8, 9, 10, 11]]
    df = pd.DataFrame({
        "incident_datetime_normalized": times,
        "fir_number_hash": [f"FIR-CLEAN-{i}" for i in range(len(times))],
        "police_station_id_normalized": ["swargate"] * len(times)
    })

    # With enforce_clean_boundaries=True, identical timestamps are shifted together
    split = PuneDataIngestionPipeline.create_chronological_splits(
        df,
        train_frac=0.5,
        val_frac=0.25,
        test_frac=0.25,
        enforce_clean_boundaries=True
    )
    assert split["zero_leakage_verified"] is True
    assert split["split_metrics"]["temporal_leakage_detected"] is False


def test_target_prevalence_audit_across_splits():
    """Verify target_prevalence audit reports positive target distribution across splits."""
    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "incident_datetime_normalized": dates,
        "fir_number_hash": [f"FIR-PREV-{i}" for i in range(20)],
        "police_station_id_normalized": ["bundgarden"] * 20,
        "harm_tier": ["violent_street_harm" if i % 2 == 0 else "other_cognizable" for i in range(20)]
    })

    split = PuneDataIngestionPipeline.create_chronological_splits(df)
    prev = split["target_prevalence"]
    assert "train" in prev and "val" in prev and "test" in prev
    assert prev["train"]["positive_target_count"] > 0
    assert prev["test"]["positive_target_count"] > 0
    assert prev["sufficient_test_positives"] is True
    assert split["temporal_notes"]["timezone"] == "Asia/Kolkata (IST)"
    assert split["temporal_notes"]["dst_observed"] is False

