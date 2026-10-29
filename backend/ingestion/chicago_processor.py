"""
Chicago Crimes Data Processor and Schema Mapper.

Maps official City of Chicago crime records (Socrata ijzp-q8t2) into
the canonical Spatio-Temporal Risk Forecaster schema.
Applies data-cleaning rules, deduplication, geographic coordinate validation,
and generates a machine-readable data quality report.
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List

# Official CPD District to Strata Risk Operational Sector mapping
CPD_DISTRICT_TO_SECTOR = {
    1: "zone-04",    # Central / Downtown Metro (The Loop)
    18: "zone-02",   # Near North / Magnificent Mile / River North
    19: "zone-09",   # Town Hall / Lakeview / Lincoln Park / Lakefront
    9: "zone-12",    # Deering / Bridgeport / Back of the Yards (Industrial South)
    12: "zone-07",   # Near West / Medical District / UIC
}

# Empirical centroids for CPD Districts in WGS84
CHICAGO_DISTRICT_CENTROIDS = {
    "zone-04": {"lat": 41.87186, "lon": -87.62829, "name": "Downtown Metro / Loop (District 001)"},
    "zone-02": {"lat": 41.90029, "lon": -87.63355, "name": "Central Transit Loop / Near North (District 018)"},
    "zone-09": {"lat": 41.94803, "lon": -87.65940, "name": "Lakefront Esplanade / Town Hall (District 019)"},
    "zone-12": {"lat": 41.81686, "lon": -87.66516, "name": "Industrial South Yards / Deering (District 009)"},
    "zone-07": {"lat": 41.88067, "lon": -87.66871, "name": "University & Medical Quarter (District 012)"},
}

# Sub-zone micro-cell offsets (approx 250m - 500m displacement in degrees: ~0.003 deg)
CHICAGO_ZONE_OFFSETS = {
    "market": {"lat_off": 0.0022, "lon_off": -0.0018, "name": "Commercial Corridor"},
    "central": {"lat_off": -0.0010, "lon_off": 0.0010, "name": "Transit Station Hub"},
    "riverside": {"lat_off": 0.0035, "lon_off": 0.0030, "name": "Lakefront / Riverfront Corridor"},
    "east": {"lat_off": -0.0035, "lon_off": -0.0030, "name": "Logistics & Peripheral Yards"},
}

SEVERITY_WEIGHTS = {
    "homicide": 3.0,
    "robbery": 3.0,
    "assault": 3.0,
    "battery": 3.0,
    "weapons violation": 3.0,
    "burglary": 2.0,
    "theft": 2.0,
    "motor vehicle theft": 2.0,
    "criminal damage": 1.5,
    "criminal trespass": 1.0,
    "deceptive practice": 1.0,
    "narcotics": 1.5,
    "other offense": 1.0,
}

CHICAGO_BOUNDS = {
    "lat_min": 41.70,
    "lat_max": 42.05,
    "lon_min": -87.80,
    "lon_max": -87.55
}

class ChicagoCrimeProcessor:
    def __init__(self, bounds: Dict[str, float] = CHICAGO_BOUNDS):
        self.bounds = bounds

    def assign_micro_zone(self, lat: float, lon: float, sector_id: str) -> str:
        """
        Assigns coordinate to nearest sub-zone micro-cell within the sector.
        """
        sec_center = CHICAGO_DISTRICT_CENTROIDS.get(sector_id, CHICAGO_DISTRICT_CENTROIDS["zone-04"])
        s_lat, s_lon = sec_center["lat"], sec_center["lon"]

        best_zone = "market"
        best_dist = float("inf")
        for z_key, z_off in CHICAGO_ZONE_OFFSETS.items():
            t_lat = s_lat + z_off["lat_off"]
            t_lon = s_lon + z_off["lon_off"]
            dist = (lat - t_lat) ** 2 + (lon - t_lon) ** 2
            if dist < best_dist:
                best_dist = dist
                best_zone = z_key
        return best_zone

    def process_raw_dataset(
        self,
        raw_csv_path: str,
        output_csv_path: str = "data/processed_chicago_crimes.csv",
        report_output_path: str = "backend/artifacts/chicago_data_quality_report.json"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Process raw downloaded Chicago dataset into canonical schema and output quality report.
        """
        if not os.path.exists(raw_csv_path):
            raise FileNotFoundError(f"Raw Chicago dataset not found: {raw_csv_path}")

        print(f"[PROCESS] Reading raw Chicago dataset from: {raw_csv_path}")
        raw_df = pd.read_csv(raw_csv_path)
        total_raw = len(raw_df)

        # 1. Audit missing values
        missing_lat = int(raw_df["latitude"].isnull().sum())
        missing_lon = int(raw_df["longitude"].isnull().sum())
        missing_coords = max(missing_lat, missing_lon)

        raw_df["parsed_date"] = pd.to_datetime(raw_df["date"], errors="coerce")
        missing_dates = int(raw_df["parsed_date"].isnull().sum())

        # 2. Exclude missing coordinates and unparseable dates
        valid_mask = raw_df["latitude"].notnull() & raw_df["longitude"].notnull() & raw_df["parsed_date"].notnull()
        clean_df = raw_df[valid_mask].copy()

        # 3. Coordinate bounding box validation
        lats = clean_df["latitude"].astype(float)
        lons = clean_df["longitude"].astype(float)

        in_bounds_mask = (
            (lats >= self.bounds["lat_min"]) & (lats <= self.bounds["lat_max"]) &
            (lons >= self.bounds["lon_min"]) & (lons <= self.bounds["lon_max"])
        )
        out_of_bounds_count = int((~in_bounds_mask).sum())
        clean_df = clean_df[in_bounds_mask].copy()

        # 4. Deduplication
        dup_count = int(clean_df.duplicated(subset=["id"]).sum())
        clean_df = clean_df.drop_duplicates(subset=["id"]).copy()

        # 5. Sector and zone mapping
        clean_df["district_num"] = clean_df["district"].astype(int)
        clean_df["sector_id"] = clean_df["district_num"].map(CPD_DISTRICT_TO_SECTOR)

        # Drop any records with districts outside the 5 study districts
        unmapped_districts = int(clean_df["sector_id"].isnull().sum())
        clean_df = clean_df.dropna(subset=["sector_id"]).copy()

        # Assign micro-zones
        micro_zones = [
            self.assign_micro_zone(lat, lon, sec)
            for lat, lon, sec in zip(clean_df["latitude"], clean_df["longitude"], clean_df["sector_id"])
        ]
        clean_df["zone_key"] = micro_zones

        # Format canonical columns
        clean_df["incident_id"] = clean_df["id"].astype(str)
        clean_df["timestamp"] = clean_df["parsed_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        clean_df["latitude"] = clean_df["latitude"].round(6)
        clean_df["longitude"] = clean_df["longitude"].round(6)
        clean_df["incident_type"] = clean_df["primary_type"].fillna("other offense").str.lower()

        # Calculate severity score
        clean_df["severity_score"] = clean_df["incident_type"].map(SEVERITY_WEIGHTS).fillna(1.0)

        # Preserve CPD source meaning: 'arrest' indicates whether law enforcement made an arrest
        clean_df["arrest_made"] = clean_df["arrest"].fillna(False).astype(int)
        # Note: The City of Chicago crime portal (ijzp-q8t2) does not contain automated acoustic/CCTV sensor telemetry
        clean_df["sensor_witnessed"] = 0

        # Select canonical schema columns
        canonical_cols = [
            "incident_id",
            "timestamp",
            "sector_id",
            "zone_key",
            "latitude",
            "longitude",
            "incident_type",
            "severity_score",
            "arrest_made",
            "sensor_witnessed"
        ]
        processed_df = clean_df[canonical_cols].sort_values("timestamp").reset_index(drop=True)

        # Save processed dataset
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
        processed_df.to_csv(output_csv_path, index=False)
        print(f"[SAVED] Processed canonical dataset written to {output_csv_path} ({len(processed_df)} records)")

        # Compile Data Quality Report
        min_date = processed_df["timestamp"].min()
        max_date = processed_df["timestamp"].max()
        duration_days = (pd.to_datetime(max_date) - pd.to_datetime(min_date)).days

        type_dist = processed_df["incident_type"].value_counts().head(10).to_dict()
        sector_dist = processed_df["sector_id"].value_counts().to_dict()
        zone_dist = processed_df["zone_key"].value_counts().to_dict()

        quality_report = {
            "dataset_name": "Official Chicago Crimes (ijzp-q8t2)",
            "proxy_dataset": True,
            "provenance": "City of Chicago Open Data Portal via Socrata Open Data API",
            "raw_record_count": total_raw,
            "processed_record_count": len(processed_df),
            "excluded_record_count": total_raw - len(processed_df),
            "missing_coordinates_count": missing_coords,
            "out_of_bounds_count": out_of_bounds_count,
            "duplicate_records_count": dup_count,
            "unmapped_districts_count": unmapped_districts,
            "date_range": {
                "start": min_date,
                "end": max_date,
                "duration_days": duration_days
            },
            "geographic_extent": {
                "lat_min": round(float(processed_df["latitude"].min()), 4),
                "lat_max": round(float(processed_df["latitude"].max()), 4),
                "lon_min": round(float(processed_df["longitude"].min()), 4),
                "lon_max": round(float(processed_df["longitude"].max()), 4)
            },
            "top_incident_types": type_dist,
            "sector_distribution": sector_dist,
            "zone_distribution": zone_dist,
            "warnings": [
                f"{missing_coords} records excluded due to missing spatial coordinates",
                f"{out_of_bounds_count} records excluded outside Chicago bounding box",
                "Chicago crime data is an empirical proxy benchmark and does not reflect another city's local conditions"
            ]
        }

        os.makedirs(os.path.dirname(report_output_path), exist_ok=True)
        with open(report_output_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)

        print(f"[SAVED] Data quality report written to {report_output_path}")
        return processed_df, quality_report

if __name__ == "__main__":
    processor = ChicagoCrimeProcessor()
    raw_path = "data/raw/chicago_crimes_2023-01-01_2023-12-31_5dist_25000.csv"
    processor.process_raw_dataset(raw_path)
