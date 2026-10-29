"""
Baseline Models for Spatio-Temporal Risk Forecasting.

Implements two domain baselines:
1. Historical Spatial Baseline (Empirical Spatial Rate with Empirical Bayes Shrinkage)
2. Temporal Cyclical Baseline (Hour-of-day & Day-of-week Historical Activity Rate)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

class HistoricalSpatialBaseline:
    """
    Baseline A: Estimates risk strictly from historical spatial incident density.
    Uses Empirical Bayes shrinkage to avoid unstable estimates in sparse cells.
    """
    def __init__(self, prior_weight: float = 5.0):
        self.prior_weight = prior_weight
        self.global_rate: float = 0.5
        self.cell_rates: Dict[Tuple[str, str], float] = {}

    def fit(self, train_df: pd.DataFrame, target_col: str = "target_event") -> "HistoricalSpatialBaseline":
        self.global_rate = float(train_df[target_col].mean())
        grouped = train_df.groupby(["sector_id", "zone_key"])[target_col].agg(["sum", "count"])

        for (sector_id, zone_key), row in grouped.iterrows():
            n = row["count"]
            k = row["sum"]
            # Empirical Bayes smoothed rate: (k + m * global_rate) / (n + m)
            shrunk_rate = (k + self.prior_weight * self.global_rate) / (n + self.prior_weight)
            self.cell_rates[(sector_id, zone_key)] = float(shrunk_rate)

        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        probs = []
        for _, row in df.iterrows():
            key = (row["sector_id"], row["zone_key"])
            p = self.cell_rates.get(key, self.global_rate)
            probs.append(p)
        return np.array(probs, dtype=float)

    def predict(self, df: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(df) >= threshold).astype(int)


class TemporalCyclicalBaseline:
    """
    Baseline B: Estimates risk from historical temporal patterns (hour-of-day,
    day-of-week, zone), accounting for diurnal commuting and evening surges.
    """
    def __init__(self, prior_weight: float = 3.0):
        self.prior_weight = prior_weight
        self.global_rate: float = 0.5
        self.temporal_rates: Dict[Tuple[int, int, str], float] = {}

    def fit(self, train_df: pd.DataFrame, target_col: str = "target_event") -> "TemporalCyclicalBaseline":
        self.global_rate = float(train_df[target_col].mean())
        grouped = train_df.groupby(["hour_of_day", "is_weekend", "zone_key"])[target_col].agg(["sum", "count"])

        for (h, wk, zk), row in grouped.iterrows():
            n = row["count"]
            k = row["sum"]
            shrunk_rate = (k + self.prior_weight * self.global_rate) / (n + self.prior_weight)
            self.temporal_rates[(int(h), int(wk), str(zk))] = float(shrunk_rate)

        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        probs = []
        for _, row in df.iterrows():
            key = (int(row["hour_of_day"]), int(row["is_weekend"]), str(row["zone_key"]))
            p = self.temporal_rates.get(key, self.global_rate)
            probs.append(p)
        return np.array(probs, dtype=float)

    def predict(self, df: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(df) >= threshold).astype(int)
