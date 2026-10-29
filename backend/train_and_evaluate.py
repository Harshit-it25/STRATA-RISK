"""
Reproducible Training and Benchmark Evaluation Orchestrator for Strata Risk.

Supports both:
1. Synthetic Functional Benchmark Dataset (default CI/testing).
2. User-Supplied External Real-World Datasets with column mapping and quality audits.
"""

import os
import json
import argparse
import pandas as pd
from typing import Optional

from backend.pipeline.dataset_generator import generate_synthetic_incidents
from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline
from backend.ingestion.dataset_loader import DatasetIngestionEngine
from backend.ingestion.schema_mapper import ColumnMapping
from backend.models.baselines import HistoricalSpatialBaseline, TemporalCyclicalBaseline
from backend.models.forecasting_engine import SpatioTemporalForecaster
from backend.evaluation.benchmark_runner import BenchmarkRunner

def run_benchmark_orchestration(
    dataset_path: str = "data/synthetic_incident_records.csv",
    dataset_type: str = "synthetic",
    dataset_name: Optional[str] = None,
    artifact_dir: str = "backend/artifacts",
    mapping_config: Optional[ColumnMapping] = None
):
    print("=" * 75)
    print("STRATA RISK: REAL-DATA VALIDATION & BENCHMARKING ENGINE")
    print("=" * 75)

    # 1. Dataset Verification or Ingestion
    if dataset_type == "synthetic" and not os.path.exists(dataset_path):
        print(f"[DATASET] Synthetic benchmark not found at {dataset_path}. Generating...")
        generate_synthetic_incidents(output_path=dataset_path, num_days=60, random_seed=42)

    # Use ingestion engine to audit and load data
    processed_dest = f"data/processed_{dataset_type}_incident_records.csv"
    ingestion = DatasetIngestionEngine(mapping=mapping_config)

    print(f"\n[INGESTION] Ingesting {dataset_type.upper()} dataset from: {dataset_path}")
    clean_raw_df, dataset_meta = ingestion.load_and_process(
        file_path=dataset_path,
        output_path=processed_dest,
        dataset_type=dataset_type,
        dataset_name=dataset_name or os.path.basename(dataset_path)
    )

    print(f"[QUALITY AUDIT] Raw records: {dataset_meta['raw_records']} | Usable: {dataset_meta['usable_records']}")
    print(f"[QUALITY AUDIT] Sufficiency status: {dataset_meta['quality_audit']['data_sufficiency']}")
    if dataset_meta['quality_audit']['warnings']:
        print(f"[QUALITY AUDIT] Warnings ({len(dataset_meta['quality_audit']['warnings'])}):")
        for w in dataset_meta['quality_audit']['warnings'][:4]:
            print(f"  - {w}")

    # 2. Spatio-Temporal Grid Pipeline
    pipeline = SpatioTemporalDataPipeline(time_interval_hours=4, forecast_horizon_hours=4)
    validated_df = pipeline.validate_raw_data(clean_raw_df)
    print(f"[PIPELINE] Grid validation: {len(validated_df)} records")

    grid_df = pipeline.build_spatio_temporal_grid(validated_df)
    feat_df = pipeline.generate_features_and_targets(grid_df)
    print(f"[PIPELINE] Built lattice: {len(grid_df)} intervals | Generated {len(pipeline.feature_columns)} features")

    # 3. Chronological Train / Val / Test Partitioning
    train_df, val_df, test_df = pipeline.split_chronological(feat_df, train_frac=0.65, val_frac=0.15)
    print(f"[SPLIT] Chronological partition: Train={len(train_df)} | Val={len(val_df)} | Holdout Test={len(test_df)}")

    # 4. Fit Baseline Models
    print("\n[TRAINING] Fitting Historical Spatial Baseline...")
    spatial_baseline = HistoricalSpatialBaseline(prior_weight=5.0).fit(train_df)

    print("[TRAINING] Fitting Temporal Cyclical Baseline...")
    temporal_baseline = TemporalCyclicalBaseline(prior_weight=3.0).fit(train_df)

    # 5. Fit Candidate CatBoost Forecaster
    print("[TRAINING] Fitting Candidate CatBoost Forecaster...")
    forecaster = SpatioTemporalForecaster(iterations=250, learning_rate=0.06, depth=5, random_seed=42)
    forecaster.fit(
        train_df,
        val_df,
        feature_cols=pipeline.feature_columns,
        target_col="target_event",
        dataset_type=dataset_type,
        dataset_name=dataset_name or os.path.basename(dataset_path)
    )

    # 6. Execute Rigorous Comparative Benchmark
    print("\n[BENCHMARK] Executing Multi-Model Chronological Benchmark...")
    runner = BenchmarkRunner(artifact_dir=artifact_dir)
    benchmark_results = runner.run_full_benchmark(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        candidate_model=forecaster,
        spatial_baseline=spatial_baseline,
        temporal_baseline=temporal_baseline,
        dataset_meta=dataset_meta,
        output_metrics_file="validation_metrics.json"
    )

    # 7. Execute Rolling-Origin Evaluation
    print("[BENCHMARK] Running Rolling-Origin Walk-Forward Temporal Splits...")
    rolling_results = runner.run_rolling_origin_evaluation(
        full_df=feat_df,
        candidate_model_class=SpatioTemporalForecaster,
        feature_cols=pipeline.feature_columns,
        n_splits=3
    )
    benchmark_results["rolling_origin_evaluations"] = rolling_results

    # Save complete benchmark artifact
    with open(os.path.join(artifact_dir, "benchmark_comparison.json"), "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)

    # 8. Save model weights and feature importances
    forecaster.save_artifacts(artifact_dir=artifact_dir)
    fi = forecaster.get_feature_importances()
    with open(os.path.join(artifact_dir, "feature_importance.json"), "w", encoding="utf-8") as f:
        json.dump(fi, f, indent=2)

    print("\n" + "=" * 75)
    print("BENCHMARK SUMMARY (HOLDOUT TEST SET):")
    print(f"Dataset Type: {dataset_type.upper()} ({dataset_meta['dataset_name']})")
    cand = benchmark_results["baseline_comparison"]["candidate_catboost"]
    spat = benchmark_results["baseline_comparison"]["historical_spatial_baseline"]
    temp = benchmark_results["baseline_comparison"]["temporal_cyclical_baseline"]

    print(f"CatBoost Forecaster   -> Brier: {cand['brier_score']} | ROC-AUC: {cand['roc_auc']} | ECE: {cand['ece']} | Precision@Top20%: {cand['precision_top_20pct']}")
    print(f"Spatial Baseline     -> Brier: {spat['brier_score']} | ROC-AUC: {spat['roc_auc']} | ECE: {spat['ece']} | Precision@Top20%: {spat['precision_top_20pct']}")
    print(f"Temporal Baseline    -> Brier: {temp['brier_score']} | ROC-AUC: {temp['roc_auc']} | ECE: {temp['ece']} | Precision@Top20%: {temp['precision_top_20pct']}")
    print("=" * 75)

    return benchmark_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strata Risk Benchmark Runner")
    parser.add_argument("--dataset-path", default="data/synthetic_incident_records.csv", help="Path to CSV dataset")
    parser.add_argument("--dataset-type", choices=["real", "synthetic"], default="synthetic", help="Type of dataset")
    parser.add_argument("--dataset-name", default=None, help="Display name for dataset")
    parser.add_argument("--artifact-dir", default="backend/artifacts", help="Directory to save artifacts")
    args = parser.parse_args()

    run_benchmark_orchestration(
        dataset_path=args.dataset_path,
        dataset_type=args.dataset_type,
        dataset_name=args.dataset_name,
        artifact_dir=args.artifact_dir
    )
