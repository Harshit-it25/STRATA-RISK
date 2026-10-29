"""
Spatio-Temporal Data Pipeline for Strata Risk.

Ingests raw incident records, validates spatial coordinates and timestamps,
constructs a regular spatio-temporal grid lattice (250m / operational zones),
builds strictly leakage-free historical lag features, and performs chronological train/val/test splits.
"""

import os
import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, List, Optional

SECTOR_METADATA = {
    "zone-04": {"name": "Downtown Metro / Loop (District 001)", "code": "CPD-01", "center_lat": 41.8719, "center_lon": -87.6283},
    "zone-02": {"name": "Central Transit Loop / Near North (District 018)", "code": "CPD-18", "center_lat": 41.9003, "center_lon": -87.6336},
    "zone-09": {"name": "Lakefront Esplanade / Town Hall (District 019)", "code": "CPD-19", "center_lat": 41.9480, "center_lon": -87.6594},
    "zone-12": {"name": "Industrial South Yards / Deering (District 009)", "code": "CPD-09", "center_lat": 41.8169, "center_lon": -87.6652},
    "zone-07": {"name": "University & Medical Quarter (District 012)", "code": "CPD-12", "center_lat": 41.8807, "center_lon": -87.6687},
}

ZONE_METADATA = {
    "market": {"name": "Commercial Retail Corridor", "code": "CPD-COMM", "tag": "COMMERCIAL RETAIL CORRIDOR • SEC-MKT", "coords": {"x": 22, "y": 18}},
    "central": {"name": "Central Station Transit Hub", "code": "CPD-TRN", "tag": "CENTRAL TRANSIT HUB • SEC-CTR", "coords": {"x": 74, "y": 36}},
    "riverside": {"name": "Lakefront & Riverfront Esplanade", "code": "CPD-RIV", "tag": "LAKEFRONT ESPLANADE • SEC-RIV", "coords": {"x": 14, "y": 72}},
    "east": {"name": "Logistics & Peripheral Yards", "code": "CPD-IND", "tag": "LOGISTICS FREIGHT YARDS • SEC-IND", "coords": {"x": 78, "y": 68}},
}

class SpatioTemporalDataPipeline:
    def __init__(self, time_interval_hours: int = 4, forecast_horizon_hours: int = 4):
        self.interval_hours = time_interval_hours
        self.horizon_hours = forecast_horizon_hours
        self.feature_columns: List[str] = []

    def validate_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate timestamps, required columns, and geographic coordinate bounds."""
        required_cols = ["incident_id", "timestamp", "sector_id", "zone_key", "latitude", "longitude"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required dataset column: {col}")

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp", "latitude", "longitude", "sector_id", "zone_key"])

        # Spatial bounding box validation (Chicago metro bounds approx 41.5 to 42.2 Lat, -88.0 to -87.4 Lon)
        valid_geo = (
            (df["latitude"] >= 41.5) & (df["latitude"] <= 42.2) &
            (df["longitude"] >= -88.0) & (df["longitude"] <= -87.4)
        )
        df = df[valid_geo]

        # Valid sector and zone filters
        df = df[df["sector_id"].isin(SECTOR_METADATA.keys())]
        df = df[df["zone_key"].isin(ZONE_METADATA.keys())]

        return df

    def build_spatio_temporal_grid(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates raw event point logs into regular spatio-temporal lattice:
        (sector_id, zone_key, window_start_time).
        Computes incident counts and severity within each interval window.
        """
        df = df.copy()
        # Round timestamp down to nearest operational window (e.g., 0, 4, 8, 12, 16, 20)
        df["window_time"] = df["timestamp"].dt.floor(f"{self.interval_hours}h")

        # Aggregate counts
        agg = df.groupby(["window_time", "sector_id", "zone_key"]).agg(
            incident_count=("incident_id", "count"),
            mean_severity=("severity_score", "mean") if "severity_score" in df.columns else ("incident_id", lambda x: 1.0),
            arrest_count=("arrest_made", "sum") if "arrest_made" in df.columns else ("incident_id", lambda x: 0),
            sensor_witness_sum=("sensor_witnessed", "sum") if "sensor_witnessed" in df.columns else ("incident_id", lambda x: 0)
        ).reset_index()

        # Build full Cartesian product grid lattice so zero-incident intervals are explicitly represented
        all_times = pd.date_range(
            start=df["window_time"].min(),
            end=df["window_time"].max(),
            freq=f"{self.interval_hours}h"
        )
        all_sectors = list(SECTOR_METADATA.keys())
        all_zones = list(ZONE_METADATA.keys())

        idx = pd.MultiIndex.from_product(
            [all_times, all_sectors, all_zones],
            names=["window_time", "sector_id", "zone_key"]
        )
        grid_df = pd.DataFrame(index=idx).reset_index()

        # Merge aggregates onto full lattice
        merged = pd.merge(grid_df, agg, on=["window_time", "sector_id", "zone_key"], how="left")
        merged["incident_count"] = merged["incident_count"].fillna(0).astype(int)
        merged["mean_severity"] = merged["mean_severity"].fillna(1.0)
        merged["arrest_count"] = merged["arrest_count"].fillna(0).astype(int)
        merged["sensor_witness_sum"] = merged["sensor_witness_sum"].fillna(0)

        # Sort chronologically and by location
        merged = merged.sort_values(["sector_id", "zone_key", "window_time"]).reset_index(drop=True)
        return merged

    def generate_features_and_targets(self, grid_df: pd.DataFrame) -> pd.DataFrame:
        """
        Constructs strictly time-lagged historical features and future forecast target.
        Guarantees zero future information leakage.
        """
        df = grid_df.copy()

        # 1. Target variables: NEXT interval's incident count and occurrence
        # Shift -1 within each (sector_id, zone_key) group
        df["target_count"] = df.groupby(["sector_id", "zone_key"])["incident_count"].shift(-1)
        df["target_event"] = (df["target_count"] > 0).astype(int)

        # 2. Temporal Cyclical & Calendar Features
        hours = df["window_time"].dt.hour
        days = df["window_time"].dt.dayofweek
        df["hour_of_day"] = hours
        df["day_of_week"] = days
        df["is_weekend"] = (days >= 5).astype(int)
        df["sin_hour"] = np.sin(2 * np.pi * hours / 24.0)
        df["cos_hour"] = np.cos(2 * np.pi * hours / 24.0)
        df["sin_day"] = np.sin(2 * np.pi * days / 7.0)
        df["cos_day"] = np.cos(2 * np.pi * days / 7.0)

        # 3. Strictly Lagged Historical Activity Features (only t, t-1, t-2...)
        # Lag 1 = current interval's count (observed up to forecast time t)
        df["lag_1_count"] = df["incident_count"]
        # Lag 2 = prior interval
        df["lag_2_count"] = df.groupby(["sector_id", "zone_key"])["incident_count"].shift(1).fillna(0)
        # Lag 6 = 24h ago
        df["lag_6_count"] = df.groupby(["sector_id", "zone_key"])["incident_count"].shift(6).fillna(0)
        # Lag 42 = 7 days ago
        df["lag_42_count"] = df.groupby(["sector_id", "zone_key"])["incident_count"].shift(42).fillna(0)

        # Rolling statistics using strictly past observations (closed='left' or shifting 1)
        # 24h rolling sum & mean
        df["rolling_24h_sum"] = df.groupby(["sector_id", "zone_key"])["incident_count"].transform(
            lambda s: s.rolling(window=6, min_periods=1).sum()
        )
        df["rolling_7d_mean"] = df.groupby(["sector_id", "zone_key"])["incident_count"].transform(
            lambda s: s.rolling(window=42, min_periods=1).mean()
        )

        # 4. Spatial Neighboring Activity
        # Average incident count in other zones within the same sector during interval t
        sector_totals = df.groupby(["window_time", "sector_id"])["incident_count"].transform("sum")
        df["sector_other_zones_count"] = (sector_totals - df["incident_count"]) / (len(ZONE_METADATA) - 1)

        # 5. Historical Cell Baseline (Empirical Bayes Smoothed Prior)
        # Cumulative historical mean up to window t
        cum_sum = df.groupby(["sector_id", "zone_key"])["incident_count"].cumsum() - df["incident_count"]
        cum_count = df.groupby(["sector_id", "zone_key"]).cumcount()
        # Smooth with global prior (alpha=2, mean=0.5)
        df["empirical_cell_rate"] = (cum_sum + 1.0) / (cum_count + 2.0)

        # Drop the last interval per group because target is NaN (future window not yet observed)
        df = df.dropna(subset=["target_count"]).reset_index(drop=True)
        df["target_count"] = df["target_count"].astype(int)

        self.feature_columns = [
            "sector_id",
            "zone_key",
            "hour_of_day",
            "day_of_week",
            "is_weekend",
            "sin_hour",
            "cos_hour",
            "sin_day",
            "cos_day",
            "lag_1_count",
            "lag_2_count",
            "lag_6_count",
            "lag_42_count",
            "rolling_24h_sum",
            "rolling_7d_mean",
            "sector_other_zones_count",
            "empirical_cell_rate"
        ]

        return df

    def split_chronological(
        self,
        df: pd.DataFrame,
        train_frac: float = 0.65,
        val_frac: float = 0.15
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Chronological out-of-time train/val/test split.
        Ensures test set is strictly in the future relative to train and val.
        """
        unique_times = df["window_time"].drop_duplicates().sort_values().reset_index(drop=True)
        n_times = len(unique_times)

        train_cutoff_idx = int(n_times * train_frac)
        val_cutoff_idx = int(n_times * (train_frac + val_frac))

        train_cutoff = unique_times.iloc[train_cutoff_idx]
        val_cutoff = unique_times.iloc[val_cutoff_idx]

        train_df = df[df["window_time"] < train_cutoff].copy()
        val_df = df[(df["window_time"] >= train_cutoff) & (df["window_time"] < val_cutoff)].copy()
        test_df = df[df["window_time"] >= val_cutoff].copy()

        return train_df, val_df, test_df
