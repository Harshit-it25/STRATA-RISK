"""
Unit tests for Data Quality Auditor.
Verifies detection of malformed coordinates, missing timestamps, Null Island, and duplicates.
"""

import os
import pytest
import pandas as pd
from backend.ingestion.quality_auditor import DataQualityAuditor

def test_audit_malformed_fixture():
    fixture_path = "fixtures/malformed_external_dataset.csv"
    assert os.path.exists(fixture_path)
    df = pd.read_csv(fixture_path, comment="#")

    auditor = DataQualityAuditor(min_records_threshold=10, min_days_threshold=2)
    report = auditor.audit_raw_dataset(
        df=df,
        time_col="occurred_at",
        lat_col="lat",
        lon_col="lon",
        id_col="case_id"
    )

    assert report["total_raw_records"] == 6
    assert report["missing_timestamps"] >= 1
    assert report["missing_coordinates"] >= 1
    assert report["null_island_coordinates"] == 1
    assert report["out_of_bounds_coordinates"] >= 1
    assert report["duplicate_records"] == 1
    assert report["data_sufficiency"] == "INSUFFICIENT"
    assert len(report["warnings"]) > 0

def test_clean_dataset_audit():
    clean_df = pd.DataFrame([
        {
            "case_id": f"ID-{i}",
            "occurred_at": f"2026-08-{i%28+1:02d} 12:00:00",
            "lat": 41.8818,
            "lon": -87.6231
        }
        for i in range(120)
    ])

    auditor = DataQualityAuditor(min_records_threshold=100, min_days_threshold=7)
    report = auditor.audit_raw_dataset(
        df=clean_df,
        time_col="occurred_at",
        lat_col="lat",
        lon_col="lon",
        id_col="case_id"
    )

    assert report["total_raw_records"] == 120
    assert report["usable_records"] == 120
    assert report["missing_timestamps"] == 0
    assert report["missing_coordinates"] == 0
    assert report["duplicate_records"] == 0
    assert report["data_sufficiency"] == "SUFFICIENT"
