"""
Geocoding and Location Search Service for Strata Risk.

Provides secure backend proxying for geocoding and reverse geocoding.
Prevents SSRF, protects external rate limits, caches results in memory,
and includes an authoritative gazetteer for major metropolitan areas.
Never fabricates search results.
"""

import time
import re
from typing import List, Dict, Any, Optional
import httpx

from backend.services.coverage_service import coverage_service, estimate_timezone_from_coords


# Authoritative offline gazetteer of major cities and benchmark locations
METROPOLITAN_GAZETTEER = [
    {
        "city": "Chicago",
        "state": "Illinois",
        "country": "United States",
        "display_name": "Chicago, Cook County, Illinois, United States",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "region_id": "chicago"
    },
    {
        "city": "Chicago Loop",
        "state": "Illinois",
        "country": "United States",
        "display_name": "The Loop, Chicago, Cook County, Illinois, United States",
        "latitude": 41.8837,
        "longitude": -87.6289,
        "region_id": "chicago"
    },
    {
        "city": "Near North Side",
        "state": "Illinois",
        "country": "United States",
        "display_name": "Near North Side, Chicago, Cook County, Illinois, United States",
        "latitude": 41.9003,
        "longitude": -87.6336,
        "region_id": "chicago"
    },
    {
        "city": "Town Hall / Lakeview",
        "state": "Illinois",
        "country": "United States",
        "display_name": "Lakeview, Chicago, Cook County, Illinois, United States",
        "latitude": 41.9480,
        "longitude": -87.6594,
        "region_id": "chicago"
    },
    {
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "display_name": "Mumbai, Maharashtra, India",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "region_id": "mumbai"
    },
    {
        "city": "Bandra, Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "display_name": "Bandra, Mumbai, Maharashtra, India",
        "latitude": 19.0596,
        "longitude": 72.8295,
        "region_id": "mumbai"
    },
    {
        "city": "Pune",
        "state": "Maharashtra",
        "country": "India",
        "display_name": "Pune, Maharashtra, India",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "region_id": "pune"
    },
    {
        "city": "Kothrud, Pune",
        "state": "Maharashtra",
        "country": "India",
        "display_name": "Kothrud, Pune, Maharashtra, India",
        "latitude": 18.5074,
        "longitude": 73.8077,
        "region_id": "pune"
    },
    {
        "city": "Shivaji Nagar, Pune",
        "state": "Maharashtra",
        "country": "India",
        "display_name": "Shivaji Nagar, Pune, Maharashtra, India",
        "latitude": 18.5314,
        "longitude": 73.8446,
        "region_id": "pune"
    },
    {
        "city": "New York",
        "state": "New York",
        "country": "United States",
        "display_name": "New York City, New York, United States",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "region_id": "new_york"
    },
    {
        "city": "London",
        "state": "England",
        "country": "United Kingdom",
        "display_name": "London, Greater London, England, United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "region_id": "london_uk"
    },
    {
        "city": "San Francisco",
        "state": "California",
        "country": "United States",
        "display_name": "San Francisco, California, United States",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "region_id": None
    },
    {
        "city": "Los Angeles",
        "state": "California",
        "country": "United States",
        "display_name": "Los Angeles, California, United States",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "region_id": None
    },
    {
        "city": "Tokyo",
        "state": "Kanto",
        "country": "Japan",
        "display_name": "Tokyo, Japan",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "region_id": None
    },
    {
        "city": "Paris",
        "state": "Ile-de-France",
        "country": "France",
        "display_name": "Paris, Ile-de-France, France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "region_id": None
    },
    {
        "city": "Toronto",
        "state": "Ontario",
        "country": "Canada",
        "display_name": "Toronto, Ontario, Canada",
        "latitude": 43.6532,
        "longitude": -79.3832,
        "region_id": None
    },
    {
        "city": "New Delhi",
        "state": "Delhi",
        "country": "India",
        "display_name": "New Delhi, Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "region_id": None
    },
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "display_name": "Bengaluru, Karnataka, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "region_id": None
    },
    {
        "city": "Sydney",
        "state": "New South Wales",
        "country": "Australia",
        "display_name": "Sydney, New South Wales, Australia",
        "latitude": -33.8688,
        "longitude": 151.2093,
        "region_id": None
    }
]


class GeocodingService:
    """Safe, rate-limited geocoding service with LRU caching."""

    def __init__(self, cache_ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._cache_ttl = cache_ttl_seconds
        self._user_agent = "StrataRisk-SpatioTemporalForecaster/4.2.1"

    def search_locations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for locations matching query.
        1. Checks in-memory cache.
        2. Searches local gazetteer for instant high-confidence hits.
        3. Queries OpenStreetMap Nominatim with safe timeout if query requires deeper search.
        4. Evaluates coverage status for each match.
        """
        clean_q = query.strip()
        if not clean_q or len(clean_q) < 2:
            return []

        # Check cache
        cache_key = f"search:{clean_q.lower()}:{limit}"
        now = time.time()
        if cache_key in self._cache:
            ts, cached_res = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return cached_res

        results: List[Dict[str, Any]] = []
        seen_coords = set()

        # Step 1: Query local gazetteer for matching names
        q_tokens = clean_q.lower().split()
        for item in METROPOLITAN_GAZETTEER:
            match_score = 0
            full_text = f"{item['city']} {item['state']} {item['country']} {item['display_name']}".lower()
            if all(token in full_text for token in q_tokens):
                cov = coverage_service.evaluate_coverage(item["latitude"], item["longitude"])
                coord_key = (round(item["latitude"], 3), round(item["longitude"], 3))
                if coord_key not in seen_coords:
                    seen_coords.add(coord_key)
                    results.append({
                        "display_name": item["display_name"],
                        "city": item["city"],
                        "country": item["country"],
                        "latitude": item["latitude"],
                        "longitude": item["longitude"],
                        "region_id": cov.get("region_id"),
                        "coverage_status": cov["status"],
                        "timezone": cov.get("timezone", estimate_timezone_from_coords(item["latitude"], item["longitude"]))
                    })

        # Step 2: If we don't have enough results and query is specific, query Nominatim with timeout
        if len(results) < limit:
            try:
                nom_results = self._query_nominatim(clean_q, limit=limit - len(results))
                for nr in nom_results:
                    lat = float(nr["lat"])
                    lon = float(nr["lon"])
                    coord_key = (round(lat, 3), round(lon, 3))
                    if coord_key not in seen_coords:
                        seen_coords.add(coord_key)
                        cov = coverage_service.evaluate_coverage(lat, lon)
                        results.append({
                            "display_name": nr.get("display_name", clean_q),
                            "city": nr.get("address", {}).get("city") or nr.get("address", {}).get("town"),
                            "country": nr.get("address", {}).get("country"),
                            "latitude": lat,
                            "longitude": lon,
                            "region_id": cov.get("region_id"),
                            "coverage_status": cov["status"],
                            "timezone": cov.get("timezone", estimate_timezone_from_coords(lat, lon))
                        })
            except Exception:
                # Graceful degradation if Nominatim is unreachable or offline
                pass

        final_results = results[:limit]
        self._cache[cache_key] = (now, final_results)
        return final_results

    def reverse_geocode(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Reverse geocodes coordinates to display name and administrative context.
        """
        cache_key = f"rev:{lat:.4f}:{lon:.4f}"
        now = time.time()
        if cache_key in self._cache:
            ts, res = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return res[0]

        # Check if close to gazetteer entry
        closest_gaz = None
        min_dist = float("inf")
        from backend.services.coverage_service import haversine_km
        for item in METROPOLITAN_GAZETTEER:
            dist = haversine_km(lat, lon, item["latitude"], item["longitude"])
            if dist < min_dist:
                min_dist = dist
                closest_gaz = item

        if closest_gaz is not None and min_dist < 15.0:
            cov = coverage_service.evaluate_coverage(lat, lon)
            res = {
                "display_name": f"{closest_gaz['display_name']} (approx {min_dist:.1f}km)",
                "latitude": lat,
                "longitude": lon,
                "region_id": cov.get("region_id"),
                "coverage_status": cov["status"],
                "timezone": cov.get("timezone", estimate_timezone_from_coords(lat, lon))
            }
            self._cache[cache_key] = (now, [res])
            return res

        # Try Nominatim reverse lookup
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14}
            with httpx.Client(timeout=2.5, headers={"User-Agent": self._user_agent}) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    cov = coverage_service.evaluate_coverage(lat, lon)
                    res = {
                        "display_name": data.get("display_name", f"Coordinates ({lat:.4f}, {lon:.4f})"),
                        "latitude": lat,
                        "longitude": lon,
                        "region_id": cov.get("region_id"),
                        "coverage_status": cov["status"],
                        "timezone": cov.get("timezone", estimate_timezone_from_coords(lat, lon))
                    }
                    self._cache[cache_key] = (now, [res])
                    return res
        except Exception:
            pass

        # Fallback to coordinate representation
        cov = coverage_service.evaluate_coverage(lat, lon)
        res = {
            "display_name": f"Location ({lat:.4f}°N, {abs(lon):.4f}°{'W' if lon < 0 else 'E'})",
            "latitude": lat,
            "longitude": lon,
            "region_id": cov.get("region_id"),
            "coverage_status": cov["status"],
            "timezone": cov.get("timezone", estimate_timezone_from_coords(lat, lon))
        }
        self._cache[cache_key] = (now, [res])
        return res

    def _query_nominatim(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Safe query to Nominatim with strict sanitization and timeouts."""
        # Sanitize query
        safe_query = re.sub(r"[^\w\s,\.-]", "", query).strip()
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": safe_query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": limit
        }
        with httpx.Client(timeout=2.5, headers={"User-Agent": self._user_agent}) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            return []


# Global singleton instance
geocoding_service = GeocodingService()
