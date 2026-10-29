"""
Data Quality Auditor for External Incident Datasets.

Evaluates raw incoming tabular datasets for completeness, coordinate bounding box
conformity, timestamp integrity, duplicate records, and category distributions.
Generates structured data-quality metrics and actionable validation warnings.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

class DataQualityAuditor:
    def __init__(
        self,
        min_records_threshold: int = 100,
        min_days_threshold: int = 7,
        lat_bounds: tuple = (41.5, 42.2),
        lon_bounds: tuple = (-88.0, -87.4)
    ):
        self.min_records_threshold = min_records_threshold
        self.min_days_threshold = min_days_threshold
        self.lat_bounds = lat_bounds
        self.lon_bounds = lon_bounds

    def audit_raw_dataset(self, df: pd.DataFrame, time_col: str, lat_col: str, lon_col: str, id_col: str) -> Dict[str, Any]:
        """
        Runs comprehensive data quality verification on raw tabular dataframe.
        """
        total_rows = len(df)
        warnings: List[str] = []

        # 1. Missing values check
        missing_counts = df.isnull().sum().to_dict()
        parsed_times = pd.to_datetime(df[time_col], errors="coerce") if time_col in df.columns else pd.Series([], dtype="datetime64[ns]")
        missing_time = int(parsed_times.isnull().sum()) if time_col in df.columns else total_rows
        missing_lat = int(df[lat_col].isnull().sum()) if lat_col in df.columns else total_rows
        missing_lon = int(df[lon_col].isnull().sum()) if lon_col in df.columns else total_rows
        missing_id = int(df[id_col].isnull().sum()) if id_col in df.columns else total_rows

        if missing_time > 0:
            warnings.append(f"{missing_time} records with null or unparseable timestamps ({missing_time/max(total_rows,1):.1%})")
        if missing_lat > 0 or missing_lon > 0:
            warnings.append(f"{max(missing_lat, missing_lon)} records with missing spatial coordinates")

        # 2. Timestamp parseability & temporal range
        parsed_times = pd.to_datetime(df[time_col], errors="coerce") if time_col in df.columns else pd.Series([], dtype="datetime64[ns]")
        valid_times = parsed_times.dropna()
        valid_time_count = len(valid_times)

        date_range = {"start": "N/A", "end": "N/A", "duration_days": 0}
        if valid_time_count > 0:
            min_date = valid_times.min()
            max_date = valid_times.max()
            duration_days = (max_date - min_date).days
            date_range = {
                "start": min_date.strftime("%Y-%m-%d %H:%M:%S"),
                "end": max_date.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_days": duration_days
            }
            if duration_days < self.min_days_threshold:
                warnings.append(f"Insufficient temporal coverage: {duration_days} days observed (minimum threshold is {self.min_days_threshold} days)")

        # 3. Coordinate validation & Bounding Box
        out_of_bounds_count = 0
        null_island_count = 0
        if lat_col in df.columns and lon_col in df.columns:
            lats = pd.to_numeric(df[lat_col], errors="coerce")
            lons = pd.to_numeric(df[lon_col], errors="coerce")

            # Null island (0, 0)
            null_island_mask = (lats.abs() < 0.001) & (lons.abs() < 0.001)
            null_island_count = int(null_island_mask.sum())

            # Regional bounding box
            in_bounds_mask = (
                (lats >= self.lat_bounds[0]) & (lats <= self.lat_bounds[1]) &
                (lons >= self.lon_bounds[0]) & (lons <= self.lon_bounds[1])
            )
            out_of_bounds_count = int((~in_bounds_mask & lats.notnull() & lons.notnull()).sum())
            if out_of_bounds_count > 0:
                warnings.append(f"{out_of_bounds_count} coordinates fall outside the regional monitoring bounding box")
            if null_island_count > 0:
                warnings.append(f"{null_island_count} coordinates are at (0, 0) Null Island")

        # 4. Duplicate records
        dup_count = 0
        if id_col in df.columns and df[id_col].notnull().any():
            dup_count = int(df.duplicated(subset=[id_col]).sum())
        elif lat_col in df.columns and lon_col in df.columns and time_col in df.columns:
            dup_count = int(df.duplicated(subset=[time_col, lat_col, lon_col]).sum())

        if dup_count > 0:
            warnings.append(f"{dup_count} duplicate incident records detected")

        # 5. Usable records count
        usable_count = 0
        if time_col in df.columns and lat_col in df.columns and lon_col in df.columns:
            valid_mask = (
                parsed_times.notnull() &
                pd.to_numeric(df[lat_col], errors="coerce").between(self.lat_bounds[0], self.lat_bounds[1]) &
                pd.to_numeric(df[lon_col], errors="coerce").between(self.lon_bounds[0], self.lon_bounds[1])
            )
            usable_count = int(valid_mask.sum())

        if usable_count < self.min_records_threshold:
            warnings.append(f"Insufficient usable volume: {usable_count} clean records (minimum threshold {self.min_records_threshold})")

        quality_score = max(0, min(100, int(round((usable_count / max(total_rows, 1)) * 100 - len(warnings) * 5))))

        return {
            "total_raw_records": total_rows,
            "usable_records": usable_count,
            "dropped_records": total_rows - usable_count,
            "quality_score_pct": quality_score,
            "date_range": date_range,
            "missing_timestamps": missing_time,
            "missing_coordinates": max(missing_lat, missing_lon),
            "out_of_bounds_coordinates": out_of_bounds_count,
            "null_island_coordinates": null_island_count,
            "duplicate_records": dup_count,
            "data_sufficiency": "SUFFICIENT" if usable_count >= self.min_records_threshold and date_range["duration_days"] >= self.min_days_threshold else "INSUFFICIENT",
            "warnings": warnings
        }
