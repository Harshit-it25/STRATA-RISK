"""
Process raw Chicago Crimes dataset into canonical format.
"""

from backend.ingestion.chicago_processor import ChicagoCrimeProcessor

def main():
    raw_path = "data/raw/chicago_crimes_2023-01-01_2023-12-31_5dist_25000.csv"
    processor = ChicagoCrimeProcessor()
    df, report = processor.process_raw_dataset(
        raw_csv_path=raw_path,
        output_csv_path="data/processed_chicago_crimes.csv",
        report_output_path="backend/artifacts/chicago_data_quality_report.json"
    )
    print("\n--- DATA QUALITY REPORT SUMMARY ---")
    print("Raw Records Ingested:", report["raw_record_count"])
    print("Clean Usable Records:", report["processed_record_count"])
    print("Excluded Records:", report["excluded_record_count"])
    print("Missing Coordinates:", report["missing_coordinates_count"])
    print("Date Range:", report["date_range"]["start"], "to", report["date_range"]["end"], f"({report['date_range']['duration_days']} days)")
    print("Districts / Sectors:", list(report["sector_distribution"].keys()))
    print("Top Incident Types:", list(report["top_incident_types"].keys())[:5])

if __name__ == "__main__":
    main()
