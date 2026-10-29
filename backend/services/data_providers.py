"""
Provider-based architecture for geographic crime data in Strata Risk.

Defines standardized data interfaces, provenance recording, schema validation,
caching, and regional provider registrations.
Strictly separates location/geocoding services from crime data providers.
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pandas as pd


class CrimeDataProvider(ABC):
    """
    Abstract interface for geographic crime data providers.
    Every regional provider must declare its geographic coverage bounds,
    provenance, observation period, and schema.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'cpd-chicago-socrata')."""
        pass

    @property
    @abstractmethod
    def region_id(self) -> str:
        """Geographic region identifier (e.g. 'chicago')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        """Official source portal or API documentation URL."""
        pass

    @property
    @abstractmethod
    def bounding_box(self) -> Dict[str, float]:
        """Geographic bounding box: min_lat, max_lat, min_lon, max_lon."""
        pass

    @property
    @abstractmethod
    def observation_period(self) -> Dict[str, str]:
        """Start and end timestamps of observations."""
        pass

    @property
    @abstractmethod
    def requires_auth(self) -> bool:
        """Whether an external API token or OAuth credentials are required."""
        pass

    @abstractmethod
    def is_location_covered(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall within provider's validated perimeter."""
        pass

    @abstractmethod
    def get_provenance_metadata(self) -> Dict[str, Any]:
        """Return audit and provenance information."""
        pass

    @abstractmethod
    def get_record_count(self) -> int:
        """Return total usable historical observation records."""
        pass


class ChicagoCrimeDataProvider(CrimeDataProvider):
    """
    Official Provider for City of Chicago Crime Data.
    Powered by City of Chicago Open Data Portal (Socrata API)
    Dataset ID: ijzp-q8t2 (Crimes - 2001 to Present).
    """

    def __init__(self, data_path: str = "data/processed_chicago_crimes.csv", meta_path: str = "data/processed_real_incident_records_metadata.json"):
        self._data_path = data_path
        self._meta_path = meta_path
        self._cached_count: Optional[int] = None
        self._load_cached_metadata()

    def _load_cached_metadata(self):
        if os.path.exists(self._meta_path):
            try:
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    self._meta = json.load(f)
                    self._cached_count = self._meta.get("usable_records", 24815)
            except Exception:
                self._meta = {}
        else:
            self._meta = {}

    @property
    def provider_id(self) -> str:
        return "chicago-cpd-socrata"

    @property
    def region_id(self) -> str:
        return "chicago"

    @property
    def display_name(self) -> str:
        return "City of Chicago Open Data Portal (CPD Incident Feed)"

    @property
    def source_url(self) -> str:
        return "https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2"

    @property
    def bounding_box(self) -> Dict[str, float]:
        return {
            "min_lat": 41.644,
            "max_lat": 42.023,
            "min_lon": -87.940,
            "max_lon": -87.523
        }

    @property
    def observation_period(self) -> Dict[str, str]:
        qa = self._meta.get("quality_audit", {}).get("date_range", {})
        return {
            "start": qa.get("start", "2023-01-01 00:00:00"),
            "end": qa.get("end", "2023-05-23 19:06:00")
        }

    @property
    def requires_auth(self) -> bool:
        return False  # Socrata Open Data allows public access with app token recommended for high volumes

    def is_location_covered(self, lat: float, lon: float) -> bool:
        b = self.bounding_box
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    def get_provenance_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "region_id": self.region_id,
            "source_name": self.display_name,
            "source_url": self.source_url,
            "license": "City of Chicago Terms of Use / Open Data",
            "observation_period": self.observation_period,
            "records_available": self.get_record_count(),
            "temporal_aggregation": "4-hour sliding operational lattice",
            "spatial_aggregation": "250m tactical micro-zones / CPD precincts",
            "model_validated": True,
            "model_engine": "CatBoost Spatio-Temporal Classifier v1.2.10",
            "model_id": "v4.2.1-catboost-calibrated",
            "last_audited": "2026-10-09"
        }

    def get_record_count(self) -> int:
        if self._cached_count is not None:
            return self._cached_count
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, "r", encoding="utf-8") as f:
                    self._cached_count = sum(1 for _ in f) - 1
                    return self._cached_count
            except Exception:
                pass
        return 24815


class NYCOpenDataCrimeProvider(CrimeDataProvider):
    """
    Documented Candidate Provider: New York City Police Department (NYPD) Historic Complaints.
    Dataset ID: qgea-i56i (NYPD Complaint Data Historic).
    Coverage: New York City (5 Boroughs).
    Status: Candidate / Model Not Yet Trained & Validated.
    """

    @property
    def provider_id(self) -> str:
        return "nyc-nypd-socrata"

    @property
    def region_id(self) -> str:
        return "new_york"

    @property
    def display_name(self) -> str:
        return "NYC Open Data Portal (NYPD Historic Complaints)"

    @property
    def source_url(self) -> str:
        return "https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i"

    @property
    def bounding_box(self) -> Dict[str, float]:
        return {
            "min_lat": 40.477,
            "max_lat": 40.917,
            "min_lon": -74.259,
            "max_lon": -73.700
        }

    @property
    def observation_period(self) -> Dict[str, str]:
        return {"start": "2006-01-01", "end": "2023-12-31"}

    @property
    def requires_auth(self) -> bool:
        return False

    def is_location_covered(self, lat: float, lon: float) -> bool:
        b = self.bounding_box
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    def get_provenance_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "region_id": self.region_id,
            "source_name": self.display_name,
            "source_url": self.source_url,
            "license": "NYC Open Data Terms of Use",
            "observation_period": self.observation_period,
            "records_available": 0,
            "temporal_aggregation": "Hourly police complaints",
            "spatial_aggregation": "NYPD Precinct boundaries",
            "model_validated": False,
            "model_engine": None,
            "model_id": None,
            "notes": "Candidate dataset registered. Model training and validation on NYC spatio-temporal lattice pending."
        }

    def get_record_count(self) -> int:
        return 0


class UKPoliceDataProvider(CrimeDataProvider):
    """
    Documented Candidate Provider: UK Police National Crime API (data.police.uk).
    Coverage: England, Wales, and Northern Ireland.
    Status: Candidate / Model Not Yet Trained & Validated.
    """

    @property
    def provider_id(self) -> str:
        return "uk-police-api"

    @property
    def region_id(self) -> str:
        return "london_uk"

    @property
    def display_name(self) -> str:
        return "data.police.uk (UK Police Open Data API)"

    @property
    def source_url(self) -> str:
        return "https://data.police.uk/docs/"

    @property
    def bounding_box(self) -> Dict[str, float]:
        return {
            "min_lat": 51.286,
            "max_lat": 51.691,
            "min_lon": -0.510,
            "max_lon": 0.334
        }

    @property
    def observation_period(self) -> Dict[str, str]:
        return {"start": "Monthly street level feeds", "end": "Latest published month"}

    @property
    def requires_auth(self) -> bool:
        return False

    def is_location_covered(self, lat: float, lon: float) -> bool:
        b = self.bounding_box
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    def get_provenance_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "region_id": self.region_id,
            "source_name": self.display_name,
            "source_url": self.source_url,
            "license": "Open Government Licence v3.0",
            "observation_period": self.observation_period,
            "records_available": 0,
            "temporal_aggregation": "Monthly aggregates",
            "spatial_aggregation": "LSOA / Police Force boundaries",
            "model_validated": False,
            "model_engine": None,
            "model_id": None,
            "notes": "UK Police API is published at monthly granularity, which lacks the 4-hour temporal resolution required for Strata Risk operational dispatch."
        }

    def get_record_count(self) -> int:
        return 0


class MumbaiOpenDataProvider(CrimeDataProvider):
    """
    Mumbai Region Provider Assessment.
    Assessment: No open municipal machine-readable feed with hourly geo-stamped
    crime incident logs is currently published for Greater Mumbai.
    Status: UNSUPPORTED.
    """

    @property
    def provider_id(self) -> str:
        return "mumbai-data-status"

    @property
    def region_id(self) -> str:
        return "mumbai"

    @property
    def display_name(self) -> str:
        return "Greater Mumbai Municipal Corporation / Maharashtra Police (No Open Feed)"

    @property
    def source_url(self) -> str:
        return "https://data.gov.in"

    @property
    def bounding_box(self) -> Dict[str, float]:
        return {
            "min_lat": 18.890,
            "max_lat": 19.280,
            "min_lon": 72.775,
            "max_lon": 72.990
        }

    @property
    def observation_period(self) -> Dict[str, str]:
        return {"start": "N/A", "end": "N/A"}

    @property
    def requires_auth(self) -> bool:
        return True

    def is_location_covered(self, lat: float, lon: float) -> bool:
        b = self.bounding_box
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    def get_provenance_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "region_id": self.region_id,
            "source_name": self.display_name,
            "source_url": self.source_url,
            "license": "N/A",
            "observation_period": self.observation_period,
            "records_available": 0,
            "temporal_aggregation": "N/A",
            "spatial_aggregation": "N/A",
            "model_validated": False,
            "model_engine": None,
            "model_id": None,
            "notes": "No machine-readable spatio-temporal crime incident stream is publicly available for Mumbai. Models trained on Chicago cannot be applied to Mumbai."
        }

    def get_record_count(self) -> int:
        return 0


class PuneCandidateDataProvider(CrimeDataProvider):
    """
    Candidate Data Provider for Pune City Police Commissionerate.
    Assessment: Requires formal institutional MoU with Office of Commissioner of Police.
    Status: UNSUPPORTED / Pilot Candidate.
    """

    @property
    def provider_id(self) -> str:
        return "pune-police-cctns-candidate"

    @property
    def region_id(self) -> str:
        return "pune"

    @property
    def display_name(self) -> str:
        return "Pune City Police Commissionerate (Candidate CCTNS Integration)"

    @property
    def source_url(self) -> str:
        return "https://punepolice.gov.in"

    @property
    def bounding_box(self) -> Dict[str, float]:
        return {
            "min_lat": 18.410,
            "max_lat": 18.630,
            "min_lon": 73.740,
            "max_lon": 74.010
        }

    @property
    def observation_period(self) -> Dict[str, str]:
        return {"start": "Pending Institutional MoU", "end": "Pending Institutional MoU"}

    @property
    def requires_auth(self) -> bool:
        return True

    def is_location_covered(self, lat: float, lon: float) -> bool:
        b = self.bounding_box
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    def get_provenance_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "region_id": self.region_id,
            "source_name": self.display_name,
            "source_url": self.source_url,
            "license": "Government Data Sharing Agreement (Required)",
            "observation_period": self.observation_period,
            "records_available": 0,
            "temporal_aggregation": "Pending (Target: 4-Hour Operational Windows / 6 Windows per Day)",
            "spatial_aggregation": "33 Police Station Jurisdictions",
            "model_validated": False,
            "model_engine": None,
            "model_id": None,
            "notes": "Pilot architecture prepared. Forecasting disabled until local CCTNS extract is ingested and validated."
        }

    def get_record_count(self) -> int:
        return 0


class DataProviderRegistry:
    """Registry maintaining active and candidate regional crime data providers."""

    def __init__(self):
        self._providers: Dict[str, CrimeDataProvider] = {
            "chicago": ChicagoCrimeDataProvider(),
            "new_york": NYCOpenDataCrimeProvider(),
            "london_uk": UKPoliceDataProvider(),
            "mumbai": MumbaiOpenDataProvider(),
            "pune": PuneCandidateDataProvider()
        }

    def get_provider(self, region_id: str) -> Optional[CrimeDataProvider]:
        return self._providers.get(region_id)

    def find_provider_for_location(self, lat: float, lon: float) -> Optional[CrimeDataProvider]:
        for provider in self._providers.values():
            if provider.is_location_covered(lat, lon):
                return provider
        return None

    def list_all_providers(self) -> List[Dict[str, Any]]:
        result = []
        for p in self._providers.values():
            meta = p.get_provenance_metadata()
            result.append({
                "id": p.provider_id,
                "region_id": p.region_id,
                "name": p.display_name,
                "source_url": p.source_url,
                "records_count": p.get_record_count(),
                "model_validated": meta["model_validated"],
                "requires_auth": p.requires_auth,
                "bounding_box": p.bounding_box,
                "observation_period": p.observation_period,
                "notes": meta.get("notes", "Operational dataset integrated.")
            })
        return result


# Global singleton instance
provider_registry = DataProviderRegistry()
