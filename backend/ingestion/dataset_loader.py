"""
Configurable Dataset Ingestion Engine for Strata Risk.

Loads external or benchmark incident datasets, validates schemas, audits data quality,
normalizes timestamps and coordinates, maps to canonical lattice, and serializes
provenance metadata.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from backend.ingestion.schema_mapper import ColumnMapping, SpatialLatticeCentroids, CANONICAL_COLUMNS
from backend.ingestion.quality_auditor import DataQualityAuditor

class DatasetIngestionEngine:
    def __init__(
        self,
        mapping: Optional[ColumnMapping] = None,
        auditor: Optional[DataQualityAuditor] = None
    ):
        self.mapping = mapping or ColumnMapping()
        self.auditor = auditor or DataQualityAuditor()

    def load_and_process(
        self,
        file_path: str,
        output_path: str,
        dataset_type: str = "real",
        dataset_name: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads an external tabular dataset, audits data quality, maps columns to canonical schema,
        and saves validated processed data and ingestion metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source incident dataset file not found: {file_path}")

        # Support CSV initially, with design extensible to Parquet
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, comment="#")
        elif file_path.endswith(".parquet"):
            df = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format for {file_path}. Supported: .csv, .parquet")

        m = self.mapping

        # 1. Audit raw dataset
        audit_report = self.auditor.audit_raw_dataset(
            df=df,
            time_col=m.timestamp,
            lat_col=m.latitude,
            lon_col=m.longitude,
            id_col=m.incident_id
        )

        # 2. Extract and validate required columns
        if m.timestamp not in df.columns or m.latitude not in df.columns or m.longitude not in df.columns:
            raise KeyError(
                f"Dataset missing required mapped columns. Expected timestamp='{m.timestamp}', "
                f"latitude='{m.latitude}', longitude='{m.longitude}'. Found columns: {list(df.columns)}"
            )

        processed_df = pd.DataFrame()

        # Parse timestamps
        parsed_times = pd.to_datetime(df[m.timestamp], errors="coerce")
        lats = pd.to_numeric(df[m.latitude], errors="coerce")
        lons = pd.to_numeric(df[m.longitude], errors="coerce")

        # Filter valid rows
        valid_mask = (
            parsed_times.notnull() &
            lats.between(self.auditor.lat_bounds[0], self.auditor.lat_bounds[1]) &
            lons.between(self.auditor.lon_bounds[0], self.auditor.lon_bounds[1])
        )

        clean_df = df[valid_mask].copy()
        clean_times = parsed_times[valid_mask]
        clean_lats = lats[valid_mask]
        clean_lons = lons[valid_mask]

        # Deduplicate records by incident_id if available, or (timestamp, lat, lon)
        if m.incident_id in clean_df.columns:
            clean_df = clean_df.drop_duplicates(subset=[m.incident_id])
            clean_times = pd.to_datetime(clean_df[m.timestamp])
            clean_lats = pd.to_numeric(clean_df[m.latitude])
            clean_lons = pd.to_numeric(clean_df[m.longitude])
            processed_df["incident_id"] = clean_df[m.incident_id].astype(str)
        else:
            clean_df = clean_df.drop_duplicates(subset=[m.timestamp, m.latitude, m.longitude])
            clean_times = pd.to_datetime(clean_df[m.timestamp])
            clean_lats = pd.to_numeric(clean_df[m.latitude])
            clean_lons = pd.to_numeric(clean_df[m.longitude])
            processed_df["incident_id"] = [f"INC-EXT-{i+1}" for i in range(len(clean_df))]

        processed_df["timestamp"] = clean_times.dt.strftime("%Y-%m-%d %H:%M:%S")
        processed_df["latitude"] = clean_lats.round(6)
        processed_df["longitude"] = clean_lons.round(6)

        # Map or classify sector and zone
        if m.sector_id and m.sector_id in clean_df.columns:
            processed_df["sector_id"] = clean_df[m.sector_id].astype(str)
        elif "sector_id" in clean_df.columns:
            processed_df["sector_id"] = clean_df["sector_id"].astype(str)
        else:
            # Spatial classification via centroids
            sec_and_zones = [
                SpatialLatticeCentroids.assign_sector_and_zone(lat, lon)
                for lat, lon in zip(clean_lats, clean_lons)
            ]
            processed_df["sector_id"] = [sz[0] for sz in sec_and_zones]

        if m.zone_key and m.zone_key in clean_df.columns:
            processed_df["zone_key"] = clean_df[m.zone_key].astype(str)
        elif "zone_key" in clean_df.columns:
            processed_df["zone_key"] = clean_df["zone_key"].astype(str)
        else:
            if "zone_key" not in processed_df.columns:
                sec_and_zones = [
                    SpatialLatticeCentroids.assign_sector_and_zone(lat, lon)
                    for lat, lon in zip(clean_lats, clean_lons)
                ]
                processed_df["zone_key"] = [sz[1] for sz in sec_and_zones]

        # Incident type
        if m.incident_type and m.incident_type in clean_df.columns:
            processed_df["incident_type"] = clean_df[m.incident_type].fillna("general_incident").astype(str)
        else:
            processed_df["incident_type"] = "general_incident"

        # Severity score
        if m.severity_score and m.severity_score in clean_df.columns:
            processed_df["severity_score"] = pd.to_numeric(clean_df[m.severity_score], errors="coerce").fillna(1.0)
        else:
            processed_df["severity_score"] = 1.0

        # Arrest made (law enforcement outcome)
        if hasattr(m, "arrest_made") and m.arrest_made and m.arrest_made in clean_df.columns:
            processed_df["arrest_made"] = pd.to_numeric(clean_df[m.arrest_made], errors="coerce").fillna(0).astype(int)
        elif "arrest" in clean_df.columns:
            processed_df["arrest_made"] = clean_df["arrest"].fillna(False).astype(int)
        else:
            processed_df["arrest_made"] = 0

        # Sensor witnessed (automated IoT acoustic/CCTV detection)
        if m.sensor_witnessed and m.sensor_witnessed in clean_df.columns and m.sensor_witnessed != "arrest":
            processed_df["sensor_witnessed"] = pd.to_numeric(clean_df[m.sensor_witnessed], errors="coerce").fillna(0).astype(int)
        else:
            processed_df["sensor_witnessed"] = 0

        # Save processed dataset
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        processed_df.to_csv(output_path, index=False)

        # Provenance metadata
        meta = {
            "dataset_type": dataset_type,  # 'real' or 'synthetic'
            "dataset_name": dataset_name or os.path.basename(file_path),
            "source_file": file_path,
            "processed_file": output_path,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "raw_records": len(df),
            "usable_records": len(processed_df),
            "dropped_records": len(df) - len(processed_df),
            "quality_audit": audit_report,
            "sectors_represented": list(processed_df["sector_id"].unique()),
            "zones_represented": list(processed_df["zone_key"].unique())
        }

        meta_path = os.path.splitext(output_path)[0] + "_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return processed_df, meta
