"""
Unit tests for Chicago Crimes Ingestion, Schema Mapping, and Quality Auditor.
"""

import os
import pytest
import pandas as pd
from backend.ingestion.chicago_processor import (
    ChicagoCrimeProcessor,
    CPD_DISTRICT_TO_SECTOR,
    CHICAGO_DISTRICT_CENTROIDS,
    CHICAGO_ZONE_OFFSETS
)

def test_cpd_district_to_sector_mapping():
    assert CPD_DISTRICT_TO_SECTOR[1] == "zone-04"   # Central / Loop
    assert CPD_DISTRICT_TO_SECTOR[18] == "zone-02"  # Near North
    assert CPD_DISTRICT_TO_SECTOR[19] == "zone-09"  # Town Hall / Lakefront
    assert CPD_DISTRICT_TO_SECTOR[9] == "zone-12"   # Deering / Industrial South
    assert CPD_DISTRICT_TO_SECTOR[12] == "zone-07"  # Near West / Medical

def test_micro_zone_spatial_assignment():
    processor = ChicagoCrimeProcessor()
    # Downtown Loop center: 41.87186, -87.62829
    # Point near market offset (+0.0022, -0.0018)
    mkt_lat = 41.87186 + 0.0022
    mkt_lon = -87.62829 - 0.0018
    assigned_zone = processor.assign_micro_zone(mkt_lat, mkt_lon, "zone-04")
    assert assigned_zone == "market"

def test_chicago_processor_data_cleaning(tmp_path):
    # Sample synthetic raw Chicago records simulating Socrata ijzp-q8t2 format
    raw_data = [
        {
            "id": 10001,
            "date": "2023-01-01T08:00:00.000",
            "primary_type": "THEFT",
            "district": 1,
            "latitude": 41.87186,
            "longitude": -87.62829,
            "arrest": True
        },
        {
            "id": 10002,
            "date": "2023-01-01T12:00:00.000",
            "primary_type": "BATTERY",
            "district": 18,
            "latitude": 41.90029,
            "longitude": -87.63355,
            "arrest": False
        },
        {
            "id": 10003,
            "date": "2023-01-01T14:00:00.000",
            "primary_type": "ROBBERY",
            "district": 1,
            "latitude": None, # Missing coordinate - should be excluded
            "longitude": None,
            "arrest": False
        },
        {
            "id": 10004,
            "date": "2023-01-01T16:00:00.000",
            "primary_type": "THEFT",
            "district": 99, # District outside study scope - should be excluded
            "latitude": 41.87186,
            "longitude": -87.62829,
            "arrest": False
        },
        {
            "id": 10001, # Duplicate ID - should be deduplicated
            "date": "2023-01-01T08:00:00.000",
            "primary_type": "THEFT",
            "district": 1,
            "latitude": 41.87186,
            "longitude": -87.62829,
            "arrest": True
        }
    ]

    raw_csv = str(tmp_path / "raw_chicago.csv")
    out_csv = str(tmp_path / "processed_chicago.csv")
    out_rep = str(tmp_path / "report.json")

    pd.DataFrame(raw_data).to_csv(raw_csv, index=False)

    processor = ChicagoCrimeProcessor()
    df_clean, report = processor.process_raw_dataset(
        raw_csv_path=raw_csv,
        output_csv_path=out_csv,
        report_output_path=out_rep
    )

    assert len(df_clean) == 2
    assert report["raw_record_count"] == 5
    assert report["processed_record_count"] == 2
    assert report["missing_coordinates_count"] == 1
    assert report["duplicate_records_count"] == 1
    assert report["unmapped_districts_count"] == 1
    assert "sector_id" in df_clean.columns
    assert "zone_key" in df_clean.columns
    assert "severity_score" in df_clean.columns
    assert "arrest_made" in df_clean.columns
    assert "sensor_witnessed" in df_clean.columns
    assert (df_clean["sensor_witnessed"] == 0).all()
