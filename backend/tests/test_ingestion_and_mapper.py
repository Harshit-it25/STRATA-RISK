"""
Unit and integration tests for Dataset Ingestion Engine and Schema Mapper.
"""

import os
import pytest
import pandas as pd
from backend.ingestion.schema_mapper import ColumnMapping, SpatialLatticeCentroids
from backend.ingestion.dataset_loader import DatasetIngestionEngine

def test_spatial_lattice_centroid_classification():
    # Test downtown coordinates close to Downtown Metro (zone-04) center (41.8818, -87.6231)
    sector, zone = SpatialLatticeCentroids.assign_sector_and_zone(41.8818, -87.6231)
    assert sector == "zone-04"
    assert zone in ["market", "central", "riverside", "east"]

    # Test coordinate close to Riverside Esplanade (zone-09) (41.8890, -87.6350)
    sec_river, _ = SpatialLatticeCentroids.assign_sector_and_zone(41.8890, -87.6350)
    assert sec_river == "zone-09"

def test_external_fixture_ingestion_with_mapping(tmp_path):
    fixture_path = "fixtures/sample_external_dataset.csv"
    assert os.path.exists(fixture_path), "External fixture file must exist"

    mapping = ColumnMapping(
        incident_id="case_id",
        timestamp="occurred_at",
        latitude="lat",
        longitude="lon",
        incident_type="offense_category",
        severity_score="priority_level",
        sensor_witnessed="witness_flag"
    )

    output_csv = str(tmp_path / "processed_external.csv")
    engine = DatasetIngestionEngine(mapping=mapping)
    df_clean, meta = engine.load_and_process(
        file_path=fixture_path,
        output_path=output_csv,
        dataset_type="real",
        dataset_name="Test External Incident Log"
    )

    assert os.path.exists(output_csv)
    assert len(df_clean) > 0
    assert "incident_id" in df_clean.columns
    assert "timestamp" in df_clean.columns
    assert "sector_id" in df_clean.columns
    assert "zone_key" in df_clean.columns

    # Verify metadata
    assert meta["dataset_type"] == "real"
    assert meta["raw_records"] == 12
    assert meta["usable_records"] == 12
    assert meta["dropped_records"] == 0

def test_unsupported_format_rejection(tmp_path):
    engine = DatasetIngestionEngine()
    dummy_txt = str(tmp_path / "invalid.txt")
    with open(dummy_txt, "w") as f:
        f.write("hello world")

    with pytest.raises(ValueError, match="Unsupported file format"):
        engine.load_and_process(dummy_txt, str(tmp_path / "out.csv"))
