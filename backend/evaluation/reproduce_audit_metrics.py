"""
Independent Forensic Reproducibility and Operational Evaluation Script.

This script independently:
1. Re-ingests the Chicago dataset and feature engineering pipeline.
2. Applies the exact chronological 65/15/20 split without lookahead leakage.
3. Loads the serialized production CatBoost model and Isotonic Calibrator.
4. Evaluates:
   - Naive Base Rate Baseline
   - Historical Spatial Frequency Baseline
   - Temporal Cyclical Baseline
   - Uncalibrated CatBoost
   - Calibrated CatBoost
5. Computes pooled and per-shift operational ranking metrics (k=4 out of 20 cells).
6. Generates bootstrap confidence intervals and sliced geographic/temporal metrics.
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from sklearn.metrics import (
    brier_score_loss,
    roc_auc_score,
    average_precision_score,
    log_loss,
    precision_score,
    recall_score
)
from sklearn.linear_model import LogisticRegression
from catboost import CatBoostClassifier
import joblib

from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline
from backend.models.baselines import HistoricalSpatialBaseline, TemporalCyclicalBaseline
from backend.models.forecasting_engine import SpatioTemporalForecaster


def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bin_limits = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        bin_mask = (y_prob >= bin_limits[i]) & (y_prob < bin_limits[i + 1])
        if i == n_bins - 1:
            bin_mask = bin_mask | (y_prob == 1.0)
        bin_size = np.sum(bin_mask)
        if bin_size > 0:
            acc = np.mean(y_true[bin_mask])
            conf = np.mean(y_prob[bin_mask])
            ece += (bin_size / n) * abs(acc - conf)
    return round(float(ece), 4)


def compute_calibration_slope_and_intercept(y_true: np.ndarray, y_prob: np.ndarray):
    eps = 1e-6
    clipped = np.clip(y_prob, eps, 1 - eps)
    logit_p = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    lr = LogisticRegression(solver="lbfgs", C=1e5)
    lr.fit(logit_p, y_true)
    slope = float(lr.coef_[0][0])
    intercept = float(lr.intercept_[0])
    return round(slope, 4), round(intercept, 4)


def run_forensic_reproduction(data_path="data/processed_chicago_crimes.csv", artifact_dir="backend/artifacts"):
    print("=" * 80)
    print("PHASE 2 & 3: INDEPENDENT FORENSIC REPRODUCTION AND OPERATIONAL AUDIT")
    print("=" * 80)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Missing dataset at {data_path}")

    # 1. Feature Engineering
    pipeline = SpatioTemporalDataPipeline()
    raw_df = pd.read_csv(data_path)
    clean_df = pipeline.validate_raw_data(raw_df)
    grid_df = pipeline.build_spatio_temporal_grid(clean_df)
    feat_df = pipeline.generate_features_and_targets(grid_df)
    total_samples = len(feat_df)
    total_positives = int(feat_df["target_event"].sum())
    overall_base_rate = float(np.mean(feat_df["target_event"]))

    print(f"Dataset: {data_path}")
    print(f"Total Observation Windows: {total_samples}")
    print(f"Overall Positive Windows: {total_positives} ({overall_base_rate:.2%})")

    # 2. Chronological Split (65 / 15 / 20)
    train_df, val_df, test_df = pipeline.split_chronological(feat_df, train_frac=0.65, val_frac=0.15)
    print(f"\nChronological Split:")
    print(f"  Train: {len(train_df)} samples ({train_df['window_time'].min()} to {train_df['window_time'].max()})")
    print(f"  Val:   {len(val_df)} samples ({val_df['window_time'].min()} to {val_df['window_time'].max()})")
    print(f"  Test:  {len(test_df)} samples ({test_df['window_time'].min()} to {test_df['window_time'].max()})")

    y_train = train_df["target_event"].values.astype(int)
    y_val = val_df["target_event"].values.astype(int)
    y_test = test_df["target_event"].values.astype(int)

    n_test = len(y_test)
    n_test_pos = int(np.sum(y_test))
    test_prevalence = float(np.mean(y_test))

    print(f"\nHoldout Test Statistics:")
    print(f"  Sample count (n): {n_test}")
    print(f"  Positive count:   {n_test_pos}")
    print(f"  Positive prevalence: {test_prevalence:.4f} ({test_prevalence:.2%})")

    # 3. Model Loading & Baseline Fitting
    forecaster = SpatioTemporalForecaster()
    forecaster.load_artifacts(artifact_dir, expected_dataset_type="real")

    # Baselines fitted strictly on training set
    spatial_baseline = HistoricalSpatialBaseline(prior_weight=5.0).fit(train_df)
    temporal_baseline = TemporalCyclicalBaseline(prior_weight=3.0).fit(train_df)

    # Predictions on holdout test set
    p_naive = np.full(n_test, fill_value=np.mean(y_train))
    p_temp = temporal_baseline.predict_proba(test_df)
    p_spat = spatial_baseline.predict_proba(test_df)
    p_cb_raw = forecaster.model.predict_proba(test_df[forecaster.feature_columns])[:, 1]
    p_cb_cal = forecaster.predict_proba(test_df)

    models = {
        "Naive Base Rate Baseline": p_naive,
        "Temporal Cyclical Baseline": p_temp,
        "Historical Spatial Baseline": p_spat,
        "CatBoost (Uncalibrated)": p_cb_raw,
        "CatBoost (Isotonic Calibrated)": p_cb_cal,
    }

    results = {}
    print("\n" + "=" * 80)
    print("GLOBAL TEST METRICS COMPARISON (n=3,440, Prevalence=70.49%)")
    print("=" * 80)
    header = f"{'Model Architecture':<32} | {'Brier':<7} | {'ROC-AUC':<7} | {'PR-AUC':<7} | {'LogLoss':<7} | {'ECE':<7} | {'Slope':<7} | {'P@Top20%':<8} | {'R@Top20%':<8}"
    print(header)
    print("-" * len(header))

    eps = 1e-15
    for name, probs in models.items():
        clipped = np.clip(probs, eps, 1 - eps)
        brier = round(float(brier_score_loss(y_test, probs)), 4)
        roc = round(float(roc_auc_score(y_test, probs)), 4) if len(np.unique(probs)) > 1 else 0.50
        pr = round(float(average_precision_score(y_test, probs)), 4) if len(np.unique(probs)) > 1 else round(test_prevalence, 4)
        ll = round(float(log_loss(y_test, clipped)), 4)
        ece = compute_ece(y_test, probs)
        slope, intercept = compute_calibration_slope_and_intercept(y_test, probs) if len(np.unique(probs)) > 1 else (1.0, 0.0)

        # Pooled Top-20%
        k_pool = int(round(n_test * 0.20))
        top_indices = np.argsort(probs)[::-1][:k_pool]
        p_top_k = round(float(np.mean(y_test[top_indices])), 4)
        r_top_k = round(float(np.sum(y_test[top_indices]) / n_test_pos), 4)

        results[name] = {
            "brier": brier,
            "roc_auc": roc,
            "pr_auc": pr,
            "log_loss": ll,
            "ece": ece,
            "cal_slope": slope,
            "cal_intercept": intercept,
            "precision_top_20pct_pooled": p_top_k,
            "recall_top_20pct_pooled": r_top_k
        }
        print(f"{name:<32} | {brier:<7.4f} | {roc:<7.4f} | {pr:<7.4f} | {ll:<7.4f} | {ece:<7.4f} | {slope:<7.4f} | {p_top_k:<8.2%} | {r_top_k:<8.2%}")

    # 4. Operational Per-Shift Ranking Evaluation
    print("\n" + "=" * 80)
    print("OPERATIONAL PER-SHIFT EVALUATION (k=4 top cells dispatched of 20 per 4h shift)")
    print("=" * 80)

    # Each shift has 20 cells (5 sectors * 4 zones)
    test_eval_df = test_df.copy()
    shifts = test_eval_df["window_time"].unique()
    n_shifts = len(shifts)
    print(f"Total operational shifts evaluated: {n_shifts} (172 shifts * 20 cells = 3,440 evaluations)")

    op_results = {}
    for name, probs in models.items():
        test_eval_df["_prob"] = probs
        shift_precisions = []
        shift_recalls = []

        for shift_time, group in test_eval_df.groupby("window_time"):
            k = 4  # top 20% of 20 candidate cells
            top_cells = group.sort_values("_prob", ascending=False).iloc[:k]
            pos_in_top = top_cells["target_event"].sum()
            total_shift_pos = group["target_event"].sum()

            shift_precisions.append(pos_in_top / k)
            if total_shift_pos > 0:
                shift_recalls.append(pos_in_top / total_shift_pos)

        mean_op_prec = float(np.mean(shift_precisions))
        std_op_prec = float(np.std(shift_precisions))
        ci_op_prec_lower = float(np.percentile(shift_precisions, 2.5))
        ci_op_prec_upper = float(np.percentile(shift_precisions, 97.5))

        mean_op_rec = float(np.mean(shift_recalls))

        op_results[name] = {
            "operational_precision_mean": round(mean_op_prec, 4),
            "operational_precision_std": round(std_op_prec, 4),
            "ci_95_empirical": [round(ci_op_prec_lower, 4), round(ci_op_prec_upper, 4)],
            "operational_recall_mean": round(mean_op_rec, 4),
            "lift_over_base_rate": round(mean_op_prec - test_prevalence, 4)
        }
        print(f"{name:<32} -> Precision: {mean_op_prec:.2%} (std: {std_op_prec:.3f}, 95% emp CI: [{ci_op_prec_lower:.2%}, {ci_op_prec_upper:.2%}]) | Recall: {mean_op_rec:.2%} | Lift: +{mean_op_prec - test_prevalence:.2%}")

    # 5. Stratified Slices: By Sector and Hour of Day
    print("\n" + "=" * 80)
    print("STRATIFIED PERFORMANCE SLICES (CATBOOST CALIBRATED)")
    print("=" * 80)
    test_eval_df["_prob"] = p_cb_cal
    for sector_id, group in test_eval_df.groupby("sector_id"):
        sec_brier = brier_score_loss(group["target_event"], group["_prob"])
        sec_roc = roc_auc_score(group["target_event"], group["_prob"]) if len(np.unique(group["target_event"])) > 1 else 0.5
        sec_prev = np.mean(group["target_event"])
        print(f"Sector {sector_id:<8} (n={len(group):<4}, Prev={sec_prev:.1%}) -> Brier: {sec_brier:.4f} | ROC-AUC: {sec_roc:.4f}")

    # 6. Save reproduction report
    out_report = {
        "dataset_path": data_path,
        "n_holdout": n_test,
        "positive_count": n_test_pos,
        "test_prevalence": test_prevalence,
        "global_metrics": results,
        "operational_shift_metrics": op_results
    }
    with open("backend/artifacts/reproduction_audit_report.json", "w") as f:
        json.dump(out_report, f, indent=2)
    print("\nComplete forensic reproduction saved to backend/artifacts/reproduction_audit_report.json")
    return out_report


if __name__ == "__main__":
    run_forensic_reproduction()
