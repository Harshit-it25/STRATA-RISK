"""
Command-line runner for downloading the official Chicago Crimes dataset.
"""

import sys
import argparse
from backend.ingestion.chicago_downloader import ChicagoDatasetDownloader

def main():
    parser = argparse.ArgumentParser(description="Download official Chicago Crimes dataset (ijzp-q8t2)")
    parser.add_argument("--start-date", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2023-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--max-records", type=int, default=25000, help="Maximum records to retrieve")
    parser.add_argument("--page-size", type=int, default=10000, help="Batch limit per request")
    parser.add_argument("--force-refresh", action="store_true", help="Force re-download ignoring cache")
    args = parser.parse_args()

    downloader = ChicagoDatasetDownloader()
    path, meta = downloader.download_records(
        start_date=args.start_date,
        end_date=args.end_date,
        max_records=args.max_records,
        page_size=args.page_size,
        force_refresh=args.force_refresh
    )
    print(f"\n[DONE] Downloaded: {meta['raw_rows_downloaded']} records to {path}")
    print(f"Date Range: {meta['start_date']} to {meta['end_date']}")
    print(f"Fields: {meta['fields_available']}")

if __name__ == "__main__":
    main()
