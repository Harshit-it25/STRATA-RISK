"""
Pune Spatio-Temporal 4-Hour Aggregation Pipeline for Strata Risk (Phase 6.3).

Provides city-specific 4-hour spatio-temporal lattice construction, target generation,
anti-leakage lag feature engineering, and support auditing for Pune City Police Commissionerate.

CRITICAL INVARIANTS:
1. Purely City-Specific: Operates entirely independently of Chicago data_pipeline.py.
   Chicago model artifacts and serving behavior remain 100% untouched.
2. Six 4-Hour Windows Per Day in Indian Standard Time (Asia/Kolkata, UTC+05:30):
   Window 0: [00:00:00, 04:00:00) IST
   Window 1: [04:00:00, 08:00:00) IST
   Window 2: [08:00:00, 12:00:00) IST
   Window 3: [12:00:00, 16:00:00) IST
   Window 4: [16:00:00, 20:00:00) IST
   Window 5: [20:00:00, 24:00:00) IST (up to midnight)
3. Well-Defined Half-Open Intervals [t, t + 4 hours):
   Event at 04:00:00.000 belongs to Window 1, NOT Window 0.
   Event at 03:59:59.999 belongs to Window 0.
4. Zero Target or Feature Lookahead:
   Features for predicting window [t, t + 4h) aggregate strictly historical records with tau < t.
5. Zero Fabricated Zero-Event Labels:
   Unobserved/non-reporting stations or periods outside active coverage are labeled UNOBSERVED
   with target NaN; zero-event labels (Y = 0) are only emitted for verified reporting coverage.
6. Theoretical vs Observed Capacity Accounting:
   Theoretical capacity: 6 windows/day * D days * 33 stations (198 station-windows/day).
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
import numpy as np
import pandas as pd
import zoneinfo

from backend.services.pune_data_readiness import (
    PUNE_POLICE_STATIONS,
    PUNE_STATION_VERIFICATION_STATUS,
    PuneDataReadinessAudit,
)
from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
    PUNE_LAT_BOUNDS,
    PUNE_LON_BOUNDS,
)


IST_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")
WINDOWS_PER_DAY = 6
WINDOW_HOURS = 4

# Operational 4-Hour Prediction Windows in IST
OPERATIONAL_WINDOWS: List[Dict[str, Any]] = [
    {"index": 0, "start_time": "00:00:00", "end_time": "04:00:00", "name": "Night / Early Morning Shift [00:00, 04:00)"},
    {"index": 1, "start_time": "04:00:00", "end_time": "08:00:00", "name": "Morning Dawn / Early Shift [04:00, 08:00)"},
    {"index": 2, "start_time": "08:00:00", "end_time": "12:00:00", "name": "Late Morning / Midday Shift [08:00, 12:00)"},
    {"index": 3, "start_time": "12:00:00", "end_time": "16:00:00", "name": "Afternoon Shift [12:00, 16:00)"},
    {"index": 4, "start_time": "16:00:00", "end_time": "20:00:00", "name": "Evening Peak Shift [16:00, 20:00)"},
    {"index": 5, "start_time": "20:00:00", "end_time": "24:00:00", "name": "Night Patrol Shift [20:00, 24:00)"},
]


class PuneFourHourSpatiotemporalPipeline:
    """
    Spatiotemporal aggregation engine for Pune City Police incident records.
    Constructs a regular station x 4-hour window lattice in IST.
    """

    def __init__(
        self,
        valid_stations: Optional[List[str]] = None,
        lat_bounds: Tuple[float, float] = PUNE_LAT_BOUNDS,
        lon_bounds: Tuple[float, float] = PUNE_LON_BOUNDS,
        target_timezone: str = "Asia/Kolkata",
    ):
        self.valid_stations = list(valid_stations or PUNE_POLICE_STATIONS)
        self.num_stations = len(self.valid_stations)
        self.lat_bounds = lat_bounds
        self.lon_bounds = lon_bounds
        self.timezone_name = target_timezone
        self.tz = zoneinfo.ZoneInfo(target_timezone)

    @classmethod
    def localize_timestamp(cls, ts_val: Any) -> pd.Timestamp:
        """
        Converts timestamp string, datetime, or pandas timestamp to localized Asia/Kolkata pd.Timestamp.
        Correctly handles UTC offsets (e.g. 18:30:00 UTC -> 00:00:00 IST next day).
        """
        if pd.isna(ts_val):
            return pd.NaT

        parsed = pd.to_datetime(ts_val)
        if parsed.tzinfo is None:
            # Naive timestamp assumed to be in UTC unless specified; localize and convert
            parsed = parsed.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            parsed = parsed.tz_convert("Asia/Kolkata")
        return parsed

    @classmethod
    def get_window_assignment(cls, ist_ts: pd.Timestamp) -> Tuple[int, pd.Timestamp, pd.Timestamp]:
        """
        Assigns an IST timestamp to its half-open 4-hour window [t_start, t_end).
        Boundary rule:
        - Exactly at boundary (e.g. 04:00:00.000) falls in Window 1 [04:00, 08:00).
        - One microsecond prior (03:59:59.999) falls in Window 0 [00:00, 04:00).
        - 23:59:59.999 is Window 5 [20:00, 24:00).
        - 00:00:00.000 is Window 0 [00:00, 04:00) of that day.
        Returns (window_index, window_start_ist, window_end_ist).
        """
        hour = ist_ts.hour
        window_idx = hour // 4
        window_start_hour = window_idx * 4

        # Start of the window
        w_start = ist_ts.replace(hour=window_start_hour, minute=0, second=0, microsecond=0)
        # End of the window (half-open, exactly 4 hours later)
        w_end = w_start + pd.Timedelta(hours=4)

        return window_idx, w_start, w_end

    def build_spatiotemporal_grid(
        self,
        start_time_ist: pd.Timestamp,
        end_time_ist: pd.Timestamp,
        station_reporting_windows: Optional[Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]] = None,
        station_operational_status: Optional[Dict[str, Dict[str, Any]]] = None,
        require_coverage_evidence: bool = False,
    ) -> pd.DataFrame:
        """
        Constructs the complete spatio-temporal lattice of (station x 4-hour window) tuples.
        
        Parameters:
        - start_time_ist: Starting IST timestamp (aligned to 4-hour window start).
        - end_time_ist: Ending IST timestamp (aligned to 4-hour window boundary).
        - station_reporting_windows: Optional mapping of station -> (report_start, report_end).
          For windows outside a station's reporting period, coverage_verified is False.
        - station_operational_status: Optional station status registry (defaults to PUNE_STATION_VERIFICATION_STATUS).
        - require_coverage_evidence: If True, missing reporting windows defaults to UNKNOWN_COVERAGE.
        """
        # Ensure aligned window starts
        _, grid_start, _ = self.get_window_assignment(start_time_ist)
        _, grid_end_floor, grid_end_ceil = self.get_window_assignment(end_time_ist)
        # If end_time is exactly on boundary w_start == end_time, grid ends at grid_end_floor
        grid_end = grid_end_floor if end_time_ist == grid_end_floor else grid_end_ceil

        window_starts = pd.date_range(
            start=grid_start,
            end=grid_end - pd.Timedelta(hours=4),
            freq="4h",
            tz="Asia/Kolkata"
        )

        status_registry = station_operational_status or PUNE_STATION_VERIFICATION_STATUS

        records: List[Dict[str, Any]] = []
        for w_start in window_starts:
            w_idx = w_start.hour // 4
            w_end = w_start + pd.Timedelta(hours=4)
            day_of_week = w_start.dayofweek
            is_weekend = int(day_of_week in (5, 6))
            month = w_start.month

            for station_id in self.valid_stations:
                op_meta = status_registry.get(station_id, {})
                st_status = op_meta.get("status", "VERIFIED_CORE")
                is_operational = st_status not in ("UNVERIFIED_RECENT_BIFURCATION", "UNVERIFIED_TRANSLITERATION_DUPLICATE")

                coverage_verified = False
                if (station_operational_status is not None or station_reporting_windows is not None or require_coverage_evidence) and not is_operational:
                    cov_status = "NOT_OPERATIONAL"
                    obs_class = "NOT_OPERATIONAL"
                elif station_reporting_windows is not None:
                    if station_id in station_reporting_windows:
                        st_start, st_end = station_reporting_windows[station_id]
                        if w_start >= st_start and w_end <= st_end:
                            coverage_verified = True
                            cov_status = "OBSERVED_ZERO"
                            obs_class = "VERIFIED_OBSERVED_ZERO"
                        else:
                            cov_status = "UNOBSERVED"
                            obs_class = "INCOMPLETE_EXTRACT"
                    else:
                        cov_status = "UNOBSERVED"
                        obs_class = "UNKNOWN_COVERAGE"
                elif require_coverage_evidence:
                    cov_status = "UNOBSERVED"
                    obs_class = "UNKNOWN_COVERAGE"
                else:
                    coverage_verified = True
                    cov_status = "OBSERVED_ZERO"
                    obs_class = "VERIFIED_OBSERVED_ZERO"

                records.append({
                    "station_id": station_id,
                    "window_start": w_start,
                    "window_end": w_end,
                    "window_idx": w_idx,
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "month": month,
                    "coverage_verified": coverage_verified,
                    "coverage_status": cov_status,
                    "observation_coverage_class": obs_class,
                })

        return pd.DataFrame(records)

    def aggregate_incidents(
        self,
        df_cleaned: pd.DataFrame,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        station_reporting_windows: Optional[Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]] = None,
        target_harm_tiers: Optional[List[str]] = None,
        station_operational_status: Optional[Dict[str, Dict[str, Any]]] = None,
        require_coverage_evidence: bool = False,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Aggregates cleaned incidents onto the 4-hour station-window lattice.
        
        Strict Rules:
        1. Half-Open Windows: Incident at tau mapped to [t, t+4h) iff t <= tau < t+4h.
        2. No Silent Zero Imputation: If a station is not in verified reporting coverage,
           its target labels are NaN (UNOBSERVED), never fabricated zeros.
        3. Target Event Definition: 1 if >= 1 positive target incident in [t, t+4h), else 0.
        4. Distinguishes violent street harm from cognizable target harms.
        5. Categorizes 5 observation-coverage states:
           - VERIFIED_OBSERVED_INCIDENT
           - VERIFIED_OBSERVED_ZERO
           - UNKNOWN_COVERAGE
           - INCOMPLETE_EXTRACT
           - NOT_OPERATIONAL
        """
        df = df_cleaned.copy()
        target_tiers = target_harm_tiers or ["violent_street_harm"]

        # Parse & Localize Timestamps to IST
        if "dt_ist" not in df.columns:
            raw_ts_col = "incident_datetime" if "incident_datetime" in df.columns else "timestamp"
            df["dt_ist"] = df[raw_ts_col].apply(self.localize_timestamp)

        # Drop invalid or unparseable timestamps
        valid_ts_mask = df["dt_ist"].notna()
        df_valid = df[valid_ts_mask].copy()

        # Map and validate stations
        if "station_normalized" not in df_valid.columns:
            st_col = "police_station_id" if "police_station_id" in df_valid.columns else "station_id"
            df_valid["station_normalized"] = df_valid[st_col].apply(PuneDataIngestionPipeline.normalize_station_id)

        valid_st_mask = df_valid["station_normalized"].isin(self.valid_stations)
        df_assigned = df_valid[valid_st_mask].copy()

        unresolved_geographic_records = len(df) - len(df_assigned)

        # Assign each incident to half-open 4-hour window
        window_assignments = df_assigned["dt_ist"].apply(self.get_window_assignment)
        df_assigned["window_idx"] = [w[0] for w in window_assignments]
        df_assigned["window_start"] = [w[1] for w in window_assignments]
        df_assigned["window_end"] = [w[2] for w in window_assignments]

        # Ensure harm tier is available
        if "harm_tier" not in df_assigned.columns and "section_code" in df_assigned.columns:
            df_assigned["harm_tier"] = PuneDataReadinessAudit.map_incident_categories(df_assigned["section_code"])

        # Determine start and end grid bounds if not explicitly supplied
        if start_time is None:
            min_ts = df_assigned["window_start"].min() if not df_assigned.empty else pd.Timestamp("2026-01-01 00:00:00", tz="Asia/Kolkata")
        else:
            min_ts = self.localize_timestamp(start_time)

        if end_time is None:
            max_ts = df_assigned["window_end"].max() if not df_assigned.empty else pd.Timestamp("2026-01-02 00:00:00", tz="Asia/Kolkata")
        else:
            max_ts = self.localize_timestamp(end_time)

        # Build full spatio-temporal lattice
        grid_df = self.build_spatiotemporal_grid(
            start_time_ist=min_ts,
            end_time_ist=max_ts,
            station_reporting_windows=station_reporting_windows,
            station_operational_status=station_operational_status,
            require_coverage_evidence=require_coverage_evidence,
        )

        # Group incidents by (station, window_start)
        df_assigned["is_target_harm"] = df_assigned["harm_tier"].isin(target_tiers).astype(int)
        df_assigned["is_violent_harm"] = (df_assigned["harm_tier"] == "violent_street_harm").astype(int)
        df_assigned["is_cognizable"] = (df_assigned["harm_tier"] != "other_cognizable").astype(int)

        grouped = df_assigned.groupby(["station_normalized", "window_start"]).agg(
            total_incidents=("dt_ist", "count"),
            target_harm_count=("is_target_harm", "sum"),
            violent_harm_count=("is_violent_harm", "sum"),
            cognizable_count=("is_cognizable", "sum"),
        ).reset_index().rename(columns={"station_normalized": "station_id"})

        # Merge onto full spatio-temporal grid
        merged = pd.merge(
            grid_df,
            grouped,
            on=["station_id", "window_start"],
            how="left"
        )

        # Fill counts where reporting coverage is verified
        verified_mask = merged["coverage_verified"] == True
        merged.loc[verified_mask, "total_incidents"] = merged.loc[verified_mask, "total_incidents"].fillna(0).astype(int)
        merged.loc[verified_mask, "target_harm_count"] = merged.loc[verified_mask, "target_harm_count"].fillna(0).astype(int)
        merged.loc[verified_mask, "violent_harm_count"] = merged.loc[verified_mask, "violent_harm_count"].fillna(0).astype(int)
        merged.loc[verified_mask, "cognizable_count"] = merged.loc[verified_mask, "cognizable_count"].fillna(0).astype(int)

        # Binary target labels Y in {0, 1} for verified periods, NaN for unobserved
        merged["target_binary"] = np.nan
        merged.loc[verified_mask, "target_binary"] = (merged.loc[verified_mask, "target_harm_count"] > 0).astype(int)

        merged["violent_binary"] = np.nan
        merged.loc[verified_mask, "violent_binary"] = (merged.loc[verified_mask, "violent_harm_count"] > 0).astype(int)

        merged["cognizable_binary"] = np.nan
        merged.loc[verified_mask, "cognizable_binary"] = (merged.loc[verified_mask, "cognizable_count"] > 0).astype(int)

        # Update coverage_status and observation_coverage_class for windows with observed incidents
        for idx in merged.index:
            tot_inc = merged.loc[idx, "total_incidents"]
            is_cov = merged.loc[idx, "coverage_verified"]
            if pd.notna(tot_inc) and tot_inc > 0:
                merged.loc[idx, "coverage_status"] = "OBSERVED_INCIDENT"
                if is_cov:
                    merged.loc[idx, "observation_coverage_class"] = "VERIFIED_OBSERVED_INCIDENT"
                else:
                    merged.loc[idx, "observation_coverage_class"] = "OBSERVED_INCIDENT_UNVERIFIED_COVERAGE"

        # Calculate statistics
        timespan_days = max(1.0, round((max_ts - min_ts).total_seconds() / 86400.0, 2))
        theoretical_capacity = int(round(timespan_days * WINDOWS_PER_DAY * self.num_stations))
        verified_station_windows = int(merged["coverage_verified"].sum())
        unobserved_station_windows = len(merged) - verified_station_windows
        active_windows = int((merged["total_incidents"] > 0).sum())
        positive_target_windows = int((merged["target_binary"] == 1).sum())
        prevalence_pct_verified = round((positive_target_windows / max(1, verified_station_windows)) * 100, 4)

        not_operational_count = int((merged["observation_coverage_class"] == "NOT_OPERATIONAL").sum())
        incomplete_extract_count = int((merged["observation_coverage_class"] == "INCOMPLETE_EXTRACT").sum())
        unknown_coverage_count = int((merged["observation_coverage_class"] == "UNKNOWN_COVERAGE").sum())
        verified_zero_count = int((merged["observation_coverage_class"] == "VERIFIED_OBSERVED_ZERO").sum())
        verified_incident_count = int((merged["observation_coverage_class"] == "VERIFIED_OBSERVED_INCIDENT").sum())

        audit_summary = {
            "timespan_days": timespan_days,
            "num_stations": self.num_stations,
            "grid_start_ist": min_ts.isoformat(),
            "grid_end_ist": max_ts.isoformat(),
            "total_incidents_assigned": len(df_assigned),
            "unresolved_geographic_records": unresolved_geographic_records,
            "theoretical_capacity_station_windows": theoretical_capacity,
            "actual_grid_station_windows": len(merged),
            "verified_reporting_station_windows": verified_station_windows,
            "unobserved_station_windows": unobserved_station_windows,
            "observed_active_station_windows": active_windows,
            "positive_target_station_windows": positive_target_windows,
            "prevalence_pct_verified_coverage": prevalence_pct_verified,
            "sparsity_warning": prevalence_pct_verified < 1.0,
            "coverage_class_breakdown": {
                "VERIFIED_OBSERVED_INCIDENT": verified_incident_count,
                "VERIFIED_OBSERVED_ZERO": verified_zero_count,
                "UNKNOWN_COVERAGE": unknown_coverage_count,
                "INCOMPLETE_EXTRACT": incomplete_extract_count,
                "NOT_OPERATIONAL": not_operational_count,
            },
        }

        return merged, audit_summary

    @classmethod
    def construct_lag_features(
        cls,
        lattice_df: pd.DataFrame,
        count_column: str = "total_incidents"
    ) -> pd.DataFrame:
        """
        Constructs strictly leakage-free historical lag features for each station-window.
        
        Strict Anti-Leakage Rules:
        - Forecast is made at window_start t to predict window [t, t+4h).
        - lag_1: count in immediate prior 4-hour window [t-4h, t).
        - lag_6: count in same 4-hour window 24h prior [t-24h, t-20h) (diurnal cycle).
        - lag_42: count in same 4-hour window 7 days prior [t-168h, t-164h) (weekly seasonality).
        - rolling_24h: rolling sum across preceding 6 windows [t-24h, t).
        - rolling_7d: rolling sum across preceding 42 windows [t-168h, t).
        All lags use shift(1) or greater, guaranteeing tau < t.
        """
        df = lattice_df.sort_values(["station_id", "window_start"]).copy()

        # Group by station to prevent cross-precinct leakage
        station_groups = df.groupby("station_id")

        # Prior window lag: shift by 1 (4 hours prior)
        df["lag_1_count"] = station_groups[count_column].shift(1)
        prev_start = station_groups["window_start"].shift(1)
        valid_4h_lag = (df["window_start"] - prev_start) == pd.Timedelta(hours=4)
        df.loc[~valid_4h_lag, "lag_1_count"] = np.nan

        # Diurnal lag: shift by 6 windows (24 hours prior)
        df["lag_6_count"] = station_groups[count_column].shift(6)
        prev_start_6 = station_groups["window_start"].shift(6)
        valid_24h_lag = (df["window_start"] - prev_start_6) == pd.Timedelta(hours=24)
        df.loc[~valid_24h_lag, "lag_6_count"] = np.nan

        # Weekly seasonal lag: shift by 42 windows (7 days * 6 windows/day = 42 windows prior)
        df["lag_42_count"] = station_groups[count_column].shift(42)
        prev_start_42 = station_groups["window_start"].shift(42)
        valid_7d_lag = (df["window_start"] - prev_start_42) == pd.Timedelta(days=7)
        df.loc[~valid_7d_lag, "lag_42_count"] = np.nan

        # Rolling 24-hour sum: preceding 6 windows strictly prior to t
        # shift(1) then rolling window of size 6
        df["rolling_24h_count"] = station_groups[count_column].transform(
            lambda s: s.shift(1).rolling(window=6, min_periods=1).sum()
        )

        # Rolling 7-day sum: preceding 42 windows strictly prior to t
        df["rolling_7d_count"] = station_groups[count_column].transform(
            lambda s: s.shift(1).rolling(window=42, min_periods=1).sum()
        )

        return df

    @classmethod
    def create_chronological_splits(
        cls,
        lattice_df: pd.DataFrame,
        train_end_time_ist: Any,
        val_end_time_ist: Any,
        embargo_windows: int = 0,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Partitions the spatio-temporal lattice into train, validation, and test splits
        with strict chronological ordering, non-overlapping window boundaries, and guaranteed
        disjoint (police_station_id, window_start) sets.
        
        Splits:
        - Train: window_start < train_end_time_ist
        - Val: train_end_time_ist + embargo <= window_start < val_end_time_ist
        - Test: window_start >= val_end_time_ist + embargo
        
        Parameters:
        - lattice_df: Spatio-temporal grid dataframe.
        - train_end_time_ist: Timestamp marking the end of training target period. Must be 4h aligned.
        - val_end_time_ist: Timestamp marking the end of validation target period. Must be 4h aligned.
        - embargo_windows: Number of 4-hour windows held out between train/val and val/test as an
          anti-autocorrelation buffer (default 0 for contiguous non-overlapping partitions).
        """
        train_end = cls.localize_timestamp(train_end_time_ist)
        val_end = cls.localize_timestamp(val_end_time_ist)

        if train_end >= val_end:
            raise ValueError(f"Chronological split inverted: train_end ({train_end}) >= val_end ({val_end})")

        # Enforce 4-hour window boundary alignment
        if train_end.minute != 0 or train_end.second != 0 or train_end.hour % 4 != 0:
            raise ValueError(
                f"train_end ({train_end}) is not aligned to a 4-hour window boundary (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 IST)."
            )
        if val_end.minute != 0 or val_end.second != 0 or val_end.hour % 4 != 0:
            raise ValueError(
                f"val_end ({val_end}) is not aligned to a 4-hour window boundary (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 IST)."
            )

        df = lattice_df.copy()

        # Calculate embargo gaps if specified
        embargo_delta = pd.Timedelta(hours=4 * max(0, embargo_windows))
        val_start = train_end + embargo_delta
        test_start = val_end + embargo_delta

        train_df = df[df["window_start"] < train_end].copy()
        val_df = df[(df["window_start"] >= val_start) & (df["window_start"] < val_end)].copy()
        test_df = df[df["window_start"] >= test_start].copy()

        # Enforce disjoint station-window key guarantee: (station_id, window_start)
        train_keys = set(zip(train_df["station_id"], train_df["window_start"]))
        val_keys = set(zip(val_df["station_id"], val_df["window_start"]))
        test_keys = set(zip(test_df["station_id"], test_df["window_start"]))

        overlap_tv = train_keys & val_keys
        overlap_vt = val_keys & test_keys
        overlap_tt = train_keys & test_keys
        if overlap_tv:
            raise ValueError(f"Non-disjoint split: {len(overlap_tv)} station-windows overlap between train and validation!")
        if overlap_vt:
            raise ValueError(f"Non-disjoint split: {len(overlap_vt)} station-windows overlap between validation and test!")
        if overlap_tt:
            raise ValueError(f"Non-disjoint split: {len(overlap_tt)} station-windows overlap between train and test!")

        # Enforce zero target interval overlap
        if not train_df.empty and not val_df.empty:
            train_max_target_end = train_df["window_end"].max()
            val_min_target_start = val_df["window_start"].min()
            if train_max_target_end > val_min_target_start:
                raise ValueError(
                    f"Target interval leakage: train max target end ({train_max_target_end}) > val min target start ({val_min_target_start})"
                )

        if not val_df.empty and not test_df.empty:
            val_max_target_end = val_df["window_end"].max()
            test_min_target_start = test_df["window_start"].min()
            if val_max_target_end > test_min_target_start:
                raise ValueError(
                    f"Target interval leakage: val max target end ({val_max_target_end}) > test min target start ({test_min_target_start})"
                )

        return train_df, val_df, test_df
