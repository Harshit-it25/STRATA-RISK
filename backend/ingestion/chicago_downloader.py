"""
Official Chicago Crimes (ijzp-q8t2) Dataset Downloader.

Downloads real incident records from the City of Chicago Open Data Portal
via the official Socrata Open Data API.
Includes:
- Configurable date ranges and district filters.
- Robust pagination with $limit and $offset.
- Exponential backoff retries for rate limits and transient network errors.
- Local raw caching to prevent redundant downloads.
- Metadata serialization documenting provenance, retrieval timestamp, and row counts.
"""

import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

SOCRATA_ENDPOINT = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"

DEFAULT_DISTRICTS = ["001", "018", "012", "009", "019"]

class ChicagoDatasetDownloader:
    def __init__(
        self,
        endpoint: str = SOCRATA_ENDPOINT,
        cache_dir: str = "data/raw",
        app_token: Optional[str] = None
    ):
        self.endpoint = endpoint
        self.cache_dir = cache_dir
        self.app_token = app_token or os.environ.get("SOCRATA_APP_TOKEN")
        os.makedirs(self.cache_dir, exist_ok=True)

    def download_records(
        self,
        start_date: str = "2023-01-01",
        end_date: str = "2023-12-31",
        districts: Optional[List[str]] = None,
        max_records: int = 30000,
        page_size: int = 5000,
        force_refresh: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Download real incident records with pagination, rate limit retries, and local caching.
        Returns the path to the cached raw CSV file and the retrieval metadata dictionary.
        """
        districts = districts or DEFAULT_DISTRICTS
        dist_str = ",".join([f"'{d}'" for d in districts])

        # Deterministic cache filename based on query parameters
        cache_filename = f"chicago_crimes_{start_date}_{end_date}_{len(districts)}dist_{max_records}.csv"
        raw_csv_path = os.path.join(self.cache_dir, cache_filename)
        meta_path = os.path.join(self.cache_dir, f"{cache_filename}.meta.json")

        # Return from cache if available and force_refresh is False
        if not force_refresh and os.path.exists(raw_csv_path) and os.path.exists(meta_path):
            print(f"[CACHE] Using existing cached raw dataset from {raw_csv_path}")
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return raw_csv_path, meta

        print(f"[DOWNLOAD] Fetching Chicago Crime records from Socrata API ({SOCRATA_ENDPOINT})...")
        print(f"[DOWNLOAD] Query parameters: {start_date} to {end_date} | Districts: {districts} | Cap: {max_records}")

        where_clause = (
            f"date >= '{start_date}T00:00:00.000' and "
            f"date <= '{end_date}T23:59:59.000' and "
            f"district in({dist_str})"
        )

        all_records: List[Dict[str, Any]] = []
        offset = 0

        while len(all_records) < max_records:
            current_limit = min(page_size, max_records - len(all_records))
            params = {
                "$limit": current_limit,
                "$offset": offset,
                "$where": where_clause,
                "$order": "date ASC"
            }

            url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "StrataRisk-Forecaster/4.2.1")
            req.add_header("Accept", "application/json")
            if self.app_token:
                req.add_header("X-App-Token", self.app_token)

            # Retry logic with exponential backoff
            records = None
            max_retries = 4
            for attempt in range(max_retries):
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        content = resp.read().decode("utf-8")
                        records = json.loads(content)
                        break
                except urllib.error.HTTPError as he:
                    if he.code in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                        wait = (attempt + 1) * 3
                        print(f"[RETRY] HTTP {he.code}. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise RuntimeError(f"Socrata API failed with status {he.code}: {he.reason}")
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 3
                        print(f"[RETRY] Request error: {e}. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise RuntimeError(f"Network error downloading Chicago crimes: {e}")

            if not records:
                break

            all_records.extend(records)
            print(f"[PROGRESS] Downloaded {len(all_records)} / {max_records} records (offset {offset})...")

            if len(records) < current_limit:
                # Reached end of available records
                break

            offset += current_limit
            # Cooperative rate pacing
            time.sleep(0.4)

        if not all_records:
            raise RuntimeError(f"No records retrieved from Socrata for query: {where_clause}")

        # Convert to DataFrame and cache to CSV
        raw_df = pd.DataFrame(all_records)
        raw_df.to_csv(raw_csv_path, index=False)
        print(f"[SAVED] Stored {len(raw_df)} raw records to {raw_csv_path}")

        meta = {
            "source_portal": "City of Chicago Open Data Portal",
            "dataset_identifier": "ijzp-q8t2",
            "dataset_name": "Crimes - 2001 to Present",
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
            "query_filter": where_clause,
            "start_date": start_date,
            "end_date": end_date,
            "districts_requested": districts,
            "raw_rows_downloaded": len(raw_df),
            "cached_file_path": raw_csv_path,
            "fields_available": list(raw_df.columns),
            "is_proxy_dataset": True,
            "disclaimer": "Official Chicago Crime Data is used strictly as an empirical proxy benchmark. It does not represent local conditions of other metropolitan jurisdictions."
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return raw_csv_path, meta
