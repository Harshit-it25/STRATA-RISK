"""
Schema Mapping Configuration for External Datasets.

Defines canonical schema contracts and column name mappings to transform
arbitrary external municipal, dispatch, or crime incident tabular datasets
into the Strata Risk canonical schema.
"""

import math
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

# Canonical internal schema columns
CANONICAL_COLUMNS = [
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

class ColumnMapping(BaseModel):
    incident_id: str = "incident_id"
    timestamp: str = "timestamp"
    latitude: str = "latitude"
    longitude: str = "longitude"
    incident_type: Optional[str] = "incident_type"
    severity_score: Optional[str] = "severity_score"
    arrest_made: Optional[str] = "arrest"
    sensor_witnessed: Optional[str] = "sensor_witnessed"
    sector_id: Optional[str] = None
    zone_key: Optional[str] = None

class SpatialLatticeCentroids:
    """
    Reference centroids for operational sectors and micro-zones.
    Used for spatial nearest-centroid classification when external datasets
    do not contain pre-assigned sector_id or zone_key.
    """
    SECTOR_CENTROIDS = {
        "zone-04": (41.8818, -87.6231),  # Downtown Metro
        "zone-02": (41.8781, -87.6298),  # Central Transit Loop
        "zone-09": (41.8890, -87.6350),  # Riverside Esplanade
        "zone-12": (41.8650, -87.6050),  # Industrial East Logistics
        "zone-07": (41.8700, -87.6500),  # University Health Quarter
    }

    ZONE_OFFSETS = {
        "market": (0.0020, -0.0015),    # Commercial corridor
        "central": (-0.0010, 0.0010),   # Station hub
        "riverside": (0.0035, 0.0025),  # Waterfront corridor
        "east": (-0.0040, -0.0030),     # Logistics fringe
    }

    @classmethod
    def assign_sector_and_zone(cls, lat: float, lon: float) -> Tuple[str, str]:
        """
        Classifies geographic coordinates (lat, lon) to nearest operational sector
        and sub-zone micro-cell using Euclidean Euclidean distance in local projection.
        """
        # Find closest sector
        best_sector = "zone-04"
        best_sec_dist = float("inf")
        for s_id, (s_lat, s_lon) in cls.SECTOR_CENTROIDS.items():
            dist = (lat - s_lat) ** 2 + (lon - s_lon) ** 2
            if dist < best_sec_dist:
                best_sec_dist = dist
                best_sector = s_id

        # Find closest zone relative to chosen sector centroid
        s_lat, s_lon = cls.SECTOR_CENTROIDS[best_sector]
        best_zone = "market"
        best_z_dist = float("inf")
        for z_key, (o_lat, o_lon) in cls.ZONE_OFFSETS.items():
            target_lat = s_lat + o_lat
            target_lon = s_lon + o_lon
            dist = (lat - target_lat) ** 2 + (lon - target_lon) ** 2
            if dist < best_z_dist:
                best_z_dist = dist
                best_zone = z_key

        return best_sector, best_zone
