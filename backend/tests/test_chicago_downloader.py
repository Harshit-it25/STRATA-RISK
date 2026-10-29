"""
Unit tests for official Chicago Crimes Socrata Downloader.
"""

import os
import pytest
from backend.ingestion.chicago_downloader import ChicagoDatasetDownloader, SOCRATA_ENDPOINT

def test_downloader_initialization():
    downloader = ChicagoDatasetDownloader(cache_dir="data/test_raw_cache")
    assert downloader.endpoint == SOCRATA_ENDPOINT
    assert os.path.exists("data/test_raw_cache")

def test_downloader_uses_existing_cache(tmp_path):
    # Pre-populate raw CSV and meta
    cache_dir = str(tmp_path)
    downloader = ChicagoDatasetDownloader(cache_dir=cache_dir)

    start = "2023-01-01"
    end = "2023-01-02"
    districts = ["001"]
    max_rec = 100

    fname = f"chicago_crimes_{start}_{end}_{len(districts)}dist_{max_rec}.csv"
    csv_file = os.path.join(cache_dir, fname)
    meta_file = os.path.join(cache_dir, f"{fname}.meta.json")

    with open(csv_file, "w") as f:
        f.write("id,date,latitude,longitude\n1,2023-01-01T08:00:00,41.88,-87.62\n")

    import json
    with open(meta_file, "w") as f:
        json.dump({"raw_rows_downloaded": 1, "is_proxy_dataset": True}, f)

    # Calling download_records without force_refresh should hit cache without network calls
    path, meta = downloader.download_records(
        start_date=start,
        end_date=end,
        districts=districts,
        max_records=max_rec,
        force_refresh=False
    )

    assert path == csv_file
    assert meta["raw_rows_downloaded"] == 1
    assert meta["is_proxy_dataset"] is True
