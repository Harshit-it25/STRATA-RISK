"""
Synthetic Spatio-Temporal Incident Dataset Generator for Strata Risk.

IMPORTANT:
[SYNTHETIC BENCHMARK DATASET - FOR SOFTWARE FUNCTIONALITY & PIPELINE TESTING ONLY]
This module generates a reproducible, realistic spatio-temporal dataset simulating
urban incident logs across geographic sectors, 250m grid cells, and temporal cycles.
It is never presented as real-world operational crime or emergency data.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_synthetic_incidents(
    output_path: str = "data/synthetic_incident_records.csv",
    start_date: str = "2026-08-01",
    num_days: int = 60,
    random_seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic incident records across 5 sectors and 4 primary sub-zones per sector.
    Includes temporal patterns (diurnal peak, weekend shifts), spatial clusters,
    and realistic incident metadata.
    """
    np.random.seed(random_seed)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    sectors = {
        "zone-04": {"name": "Downtown Metro", "center_lat": 41.8818, "center_lon": -87.6231, "base_rate": 1.4},
        "zone-02": {"name": "Central Transit Loop", "center_lat": 41.8781, "center_lon": -87.6298, "base_rate": 1.2},
        "zone-09": {"name": "Riverside Esplanade", "center_lat": 41.8890, "center_lon": -87.6350, "base_rate": 0.5},
        "zone-12": {"name": "Industrial East Logistics", "center_lat": 41.8650, "center_lon": -87.6050, "base_rate": 0.25}, # Sparse zone
        "zone-07": {"name": "University Health Quarter", "center_lat": 41.8700, "center_lon": -87.6500, "base_rate": 0.8},
    }

    sub_zones = {
        "market": {"name": "Commercial Corridor", "offset_lat": 0.0020, "offset_lon": -0.0015, "weight": 1.5, "peak_hour": 20},
        "central": {"name": "Transit Station Hub", "offset_lat": -0.0010, "offset_lon": 0.0010, "weight": 1.3, "peak_hour": 8},
        "riverside": {"name": "Recreation Waterfront", "offset_lat": 0.0035, "offset_lon": 0.0025, "weight": 0.6, "peak_hour": 14},
        "east": {"name": "Logistics & Fringe Yards", "offset_lat": -0.0040, "offset_lon": -0.0030, "weight": 0.2, "peak_hour": 2}, # Intentionally sparse
    }

    incident_types = [
        "theft_larceny",
        "public_disturbance",
        "traffic_obstruction",
        "property_damage",
        "suspicious_activity",
        "medical_assist"
    ]

    records = []
    incident_counter = 100000

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    total_hours = num_days * 24

    for h_idx in range(total_hours):
        current_time = start_dt + timedelta(hours=h_idx)
        hour = current_time.hour
        day_of_week = current_time.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0

        for sec_id, sec_info in sectors.items():
            for z_key, z_info in sub_zones.items():
                # Diurnal temporal multiplier
                peak_h = z_info["peak_hour"]
                # Gaussian-like diurnal distance
                hour_diff = min(abs(hour - peak_h), 24 - abs(hour - peak_h))
                temporal_factor = np.exp(- (hour_diff ** 2) / (2 * 4.0 ** 2)) * 1.8 + 0.3

                # Weekend factor
                weekend_factor = 1.3 if (is_weekend and z_key in ["market", "riverside"]) else 0.85 if is_weekend else 1.0

                # Expected Poisson lambda for incidents in this cell-hour
                expected_rate = sec_info["base_rate"] * z_info["weight"] * temporal_factor * weekend_factor * 0.25

                # Sparse zone simulation
                if sec_id == "zone-12" or z_key == "east":
                    expected_rate *= 0.25 # high probability of zero incidents

                num_incidents = np.random.poisson(expected_rate)

                for _ in range(num_incidents):
                    incident_counter += 1
                    # Jitter within 250m (approx 0.0022 deg lat/lon)
                    lat = sec_info["center_lat"] + z_info["offset_lat"] + np.random.normal(0, 0.0006)
                    lon = sec_info["center_lon"] + z_info["offset_lon"] + np.random.normal(0, 0.0006)
                    inc_type = np.random.choice(incident_types)
                    severity = np.random.choice([1, 2, 3], p=[0.6, 0.3, 0.1])

                    records.append({
                        "incident_id": f"INC-{incident_counter}",
                        "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "sector_id": sec_id,
                        "zone_key": z_key,
                        "latitude": round(lat, 6),
                        "longitude": round(lon, 6),
                        "incident_type": inc_type,
                        "severity_score": severity,
                        "sensor_witnessed": 1 if np.random.rand() > 0.3 else 0
                    })

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} synthetic incident records saved to {output_path}")
    return df

if __name__ == "__main__":
    generate_synthetic_incidents()
